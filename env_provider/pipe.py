import json
import logging
import os
from os import chmod, path, walk, mkfifo

from shutil import rmtree, copytree, copy

import plugin_loader
import task_queue
from container import file_spinlock
from tuples import TestStatus
from workdir import internal_path
import env_provider.common as common


def do_create_test_units(submission, env_conf, pack):
    return common.do_create_test_units(submission, env_conf, pack)


def do_run_test(submission, env_conf, pack, test_unit):
    runner, runner_conf = plugin_loader.get('runners', pack.config['runner']['name'], pack.config['runner'])
    runner_conf['location'] = 'work/run'

    # configure locations of the runners
    srv_runner, srv_runner_conf = plugin_loader.get(
        'runners', pack.config['service_runner']['name'], pack.config['service_runner'])
    srv_runner_conf['location'] = 'work/srv'

    srv_runner.do_prepare(srv_runner_conf)

    runner.do_prepare(runner_conf)
    # input everything which was outputted from the compilation
    rmtree(internal_path('work/run/in'), ignore_errors=True)
    copytree(internal_path('work/compile/out'), internal_path(path.join('work/run/in')))

    common.copy_data_directory(pack, test_unit)

    # upload service program
    rmtree(internal_path('work/srv/in'), ignore_errors=True)
    copytree(path.join(pack.path, 'service'), internal_path(path.join('work/srv/in')))
    chmod(internal_path('work/srv/in/prog'), 0o777)

    # upload input file for the test for service
    copy(test_unit.runner_meta['input_file'], internal_path('work/srv/in/input.txt'))

    # create pipes which will be used for communication
    mkfifo(internal_path('work/run/in/input.txt'))
    mkfifo(internal_path('work/run/out/output.txt'))
    chmod(internal_path('work/run/in/input.txt'), 0o777)
    chmod(internal_path('work/run/out/output.txt'), 0o777)

    srv_container = srv_runner.do_run(srv_runner_conf, additional_binds={
        internal_path(os.path.join("work/run/in")): {
            "bind": "/mnt/prog-in",
            "mode": "rw"
        },
        internal_path(os.path.join("work/run/out")): {
            "bind": "/mnt/prog-out",
            "mode": "rw"
        },
    })

    exc_container = runner.do_run(runner_conf)

    # wait till server is ready
    if not file_spinlock(internal_path('work/srv/out/srv-ready'), 1.0):
        raise RuntimeError('Service didn\'t started within 1 second.')

    # run user's program
    # TODO context manager for containers?
    exc_res = runner.do_wait(runner_conf, exc_container)

    if exc_res.status in ['soft_timeout', 'hard_timeout']:
        # TODO maybe some better solution?
        srv_runner.do_wait(srv_runner_conf, srv_container, max_time=0.0)
        return TestStatus(name=test_unit.name, status='hard_timeout', time=exc_res.exec_time, timeout=exc_res.timeout,
                          points=0, max_points=1)

    svc_res = srv_runner.do_wait(srv_runner_conf, srv_container, max_time=1.0)

    if svc_res.status == 'bad_exit_code':
        # something went wrong with the service, internal error
        raise RuntimeError('Service crashed.')
    elif svc_res.status in ['soft_timeout', 'hard_timeout']:
        return TestStatus(name=test_unit.name, status='hard_timeout', time=svc_res.exec_time, timeout=svc_res.timeout,
                          points=0, max_points=1)

    with open(internal_path('work/srv/out/output.txt'), 'r', encoding='utf-8') as output_file:
        out_data = json.loads(output_file.read())

    try:
        if test_unit.runner_meta['options']['store_output'] != 'none':
            logging.info('Storing output for the test {}'.format(test_unit.name))
            task_queue.upload_test_output(submission['uuid'], test_unit.name,
                                          out_data['message'], test_unit.runner_meta['store_output'])
    except KeyError:
        pass

    if exc_res.status != 'ok':
        status = exc_res.status
    else:
        status = 'ok'

    points = out_data['points']
    max_points = out_data['max_points']

    return TestStatus(name=test_unit.name, status=status, time=exc_res.exec_time,
                      timeout=exc_res.timeout, memory=exc_res.memory, points=points, max_points=max_points)

__plugin__ = {}
