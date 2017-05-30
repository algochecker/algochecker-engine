#!/usr/bin/env python3
import logging
import signal
import sys
import traceback
from os import makedirs, walk
from os.path import join, basename
from shutil import make_archive
from traceback import format_exc

import time

import datetime
from requests import ConnectionError

from container import docker_cli, check_lost_containers, check_image_dependencies, PluginError, check_leftover_networks
from logo import print_header
from container import shrink_logs, safe_plugin_call
from package import get_package, prune_unused_packages, parse_config
import plugin_loader
import task_queue
from tuples import FinalResult
from workdir import internal_path, recreate_workdir
from worker_conf import INSTANCE_NAME, DEBUG_MODE, LOG_FORMAT, LOG_DATEFMT


def setup_logging():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATEFMT)


def sigterm_handler(signum, frame):
    logging.warning('Received {}, will terminate soon after finishing current job.'.format(signal.Signals(signum).name))
    task_queue.interrupted = True


def check_connections():
    logging.info('Checking connectivity with Docker...')
    try:
        docker_cli.ping()
    except ConnectionError:
        logging.exception('Connection to Docker has failed.')
        return False

    logging.info('Checking connectivity with Redis...')
    if not task_queue.safe_ping():
        logging.error('Connection to Redis has failed.')
        return False

    return True


def perform_compilation(s_data, pack):
    """
    Run compiler plugin
    """
    compiler, compiler_conf = plugin_loader.get('compilers', pack.config['compiler']['name'], pack.config['compiler'])
    safe_plugin_call(compiler, lambda: compiler.do_prepare())

    task_queue.download_project(s_data['uuid'], internal_path('work/compile/in'))
    task_queue.report_status(s_data['uuid'], 'compiling', 0)

    logging.info('Compiling the code...')
    compile_res = safe_plugin_call(compiler, lambda: compiler.do_compile(compiler_conf, pack))

    compile_success = compile_res.status == 'ok'

    if not compile_success:
        task_queue.report_status(s_data['uuid'], 'done', 100)

    return compile_success, compile_res.message


def perform_run(s_data, pack):
    """
    Run all tests via env provider plugin and evaluate them
    """
    envpr, envpr_conf = plugin_loader.get('env_provider', pack.config['env']['name'], pack.config['env'])
    evaluator, evaluator_conf = plugin_loader.get('evaluators',
                                                  pack.config['evaluator']['name'], pack.config['evaluator'])

    test_units = safe_plugin_call(envpr, lambda: envpr.do_create_test_units(s_data, envpr_conf, pack))
    results = []

    for test_unit in test_units:
        logging.info('Processing test ' + test_unit.name + '...')

        task_queue.report_status(s_data['uuid'], 'testing', 20 + int(len(results) * 80 / len(test_units)))

        test_res = safe_plugin_call(envpr, lambda: envpr.do_run_test(s_data, envpr_conf, pack, test_unit))
        results.append(test_res._asdict())

        if DEBUG_MODE:
            logging.info('Finished test {}'.format(test_unit.name))
            logging.info('Result: {}'.format(test_res._asdict()))
            input('Press <ENTER> to continue.')

    score, results = safe_plugin_call(evaluator, lambda: evaluator.do_process_results(evaluator_conf, results))
    return score, results


def process_submission(s_data):
    """
    Process given submission (s_data) and return final assessment result.
    """
    s_uuid = s_data['uuid']

    logging.info('Received new task: {}'.format(s_uuid))

    task_queue.report_status(s_uuid, 'preparing', 0)
    recreate_workdir()

    pack = get_package(**s_data['package'])
    pack = parse_config(pack, s_data['config'] if 'config' in s_data else None)

    compile_result, logs = perform_compilation(s_data, pack)

    if logs:
        logs = shrink_logs(logs)
    else:
        logs = ''

    if not compile_result:
        return FinalResult("compile_error", uuid=s_data['uuid'], message=logs)

    score, results = perform_run(s_data, pack)

    logging.info('Processing done.')
    task_queue.report_status(s_uuid, 'done', 100)

    return FinalResult(
        status="ok",
        uuid=s_uuid,
        message=logs,
        score=score,
        tests=results
    )


def check_ptrace_scope():
    try:
        with open('/proc/sys/kernel/yama/ptrace_scope', 'r') as f:
            content = f.read()

            if int(content) < 2:
                logging.warning('ATTENTION! Found out that ptrace_scope is set to the value lower than 2. '
                                + 'This may affect security of processes inside containers.')
    except IOError:
        logging.warning('ATTENTION! Failed to check /proc/sys/kernel/yama/ptrace_scope due to file access error.')
    except ValueError:
        logging.warning('ATTENTION! Failed to check /proc/sys/kernel/yama/ptrace_scope because it contains invalid '
                        + 'value (expected number).')


def check_cr_shell_endings():
    for root, dirs, files in walk("."):
        for file in files:
            if file.endswith(".sh"):
                with open(join(root, file), 'rb') as f:
                    if f.read().find(b'\r') != -1:
                        logging.warning(('ATTENTION! Found shell script containing CR character at {}. '
                                        + 'This may be a mistake during deployment.').format(join(root, file)))


def main():
    setup_logging()
    print_header()

    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    plugin_loader.load_namespace('compilers')
    plugin_loader.load_namespace('env_provider')
    plugin_loader.load_namespace('runners')
    plugin_loader.load_namespace('evaluators')

    if not check_connections():
        logging.error('Failed to establish the connections, exiting...')
        sys.exit(2)

    check_lost_containers()
    check_leftover_networks()
    check_image_dependencies()
    prune_unused_packages()

    # write the random UUID of current instance to the instance lock
    # if it would be overridden during worker execution, then it means
    # that the second worker was started with the same instance name
    task_queue.set_instance_lock(False)

    check_ptrace_scope()
    check_cr_shell_endings()

    logging.info('Ready! Starting worker...')

    while True:
        if DEBUG_MODE:
            logging.warning('This worker is running in debug mode. Please disable it if this worker '
                            + 'is running on the production environment.')

        try:
            s_data = task_queue.fetch_submission()
        except KeyboardInterrupt as e:
            logging.warning('Program interrupted, will now stop.')
            sys.exit(0)

        started_time = int(time.time() * 1000)

        try:
            res = process_submission(s_data)
        except PluginError as e:
            logging.error('--- PLUGIN FAILURE NOTICE ---')
            trace_str = traceback.format_exc(20)
            logging.exception('A plugin failure occurred while processing the submission.')

            try:
                makedirs(internal_path('error_report'))
            except FileExistsError:
                pass

            saved_reports = [basename(p) for p in check_lost_containers(no_header=True)]
            now = datetime.datetime.now()
            report_name = 'plugin_error_{}_{}'.format(now.strftime('%Y%m%d_%H%M%S'), s_data['uuid'])
            report_log = report_name + '.log'
            full_report_path = join(internal_path('error_report'), report_log)

            with open(full_report_path, 'w') as report_f:
                report_f.write('Report about plugin failure\n')
                report_f.write('Offending plugin: {}\n'.format(e.plugin_path))
                report_f.write('Generated on: {}\n'.format(now.isoformat()))
                report_f.write('Attached workdir dump: {}.zip\n'.format(report_name))
                report_f.write('Related lost container reports: {}\n'.format(", ".join(saved_reports)))
                report_f.write('\n=== Traceback (length: {}) ===\n'.format(len(trace_str)))
                report_f.write(trace_str)
                report_f.write('\n=== End of report ===\n')

            res = FinalResult("internal_error", uuid=s_data['uuid'], message=trace_str)
            logging.error('IMPORTANT! In order to find out what happened, please refer to the '
                          + 'plugin failure report stored at: {}'.format(full_report_path))
            make_archive(join(internal_path('error_report'), report_name), 'zip', internal_path('work'))
            logging.error('IMPORTANT! Work directory was archived in order to allow further inspection.')
            logging.error('-----------------------------')
        except RuntimeError:
            trace_str = format_exc(20)
            logging.exception('An error occurred while processing submission.')
            # if an error was caused inside docker container, then we
            # need to perform a cleanup or we'll leak the container otherwise
            check_lost_containers()
            res = FinalResult("internal_error", uuid=s_data['uuid'], message=trace_str)

        finished_time = int(time.time() * 1000)

        res = res._replace(
            checked_by=INSTANCE_NAME,
            time_stats={
                "started_ms": started_time,
                "finished_ms": finished_time,
                "took_time_ms": finished_time - started_time
            })

        if 'async_report' in s_data['features']:
            task_queue.send_report_async(res)
        else:
            logging.error('Synchronous result reporting is not longer supported. Failed to send report.')


if __name__ == "__main__":
    main()
