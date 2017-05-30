import os

from container import make_container, inspect_container
from runners.common import *

prog_image_name = "gcc:latest"
wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin-interact", "run-test.sh")
svc_wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin-interact", "run-service.sh")


def do_create_test_units(runner_conf, pack):
    return common_create_test_units(runner_conf, pack)


def do_prepare(runner_conf, test_unit, pack):
    rmtree(internal_path('work/run'), ignore_errors=True)

    copytree(internal_path('work/compile/out'), internal_path('work/run/in'))
    makedirs(internal_path('work/run/service'))
    copy(test_unit.runner_meta['input_file'], internal_path('work/run/service/svc-input.txt'))

    makedirs(internal_path('work/run/scripts'))
    copy(wrapper_path, internal_path('work/run/scripts/run-test.sh'))
    copy(svc_wrapper_path, internal_path('work/run/scripts/run-service.sh'))

    if not runner_conf['service']['command']:
        raise RunnerConfigurationError('Configuration key service.command was not provided!')

    copy(os.path.join(pack.path, runner_conf['service']['command']), internal_path('work/run/service/service'))

    chmod(internal_path('work/run/scripts/run-test.sh'), 0o500)
    chmod(internal_path('work/run/scripts/run-service.sh'), 0o500)

    chown_recursive(internal_path('work/run'), DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP)


def binds():
    return {
        internal_path("work/run/service"): {
            "bind": "/mnt/service",
            "mode": "rw"
        },
        internal_path("work/run/scripts"): {
            "bind": "/mnt/scripts",
            "mode": "ro"
        },
        internal_path("work/run/in"): {
            "bind": "/mnt/in",
            "mode": "rw"
        }
    }


def do_run(runner_conf, test_unit, pack):
    prog_container = make_container(
        prog_image_name, ['/mnt/scripts/run-test.sh'], binds(), common_host_config(runner_conf))
    service_container = make_container(
        runner_conf['service']['image'], ['/mnt/scripts/run-service.sh'], binds(), common_host_config(runner_conf))

    docker_cli.start(service_container)
    docker_cli.start(prog_container)

    limit_sec = (float(runner_conf['limits']['timeout']) / 1000.0) + 0.5
    test_finished = file_spinlock(internal_path('work/run/in/finished'), limit_sec)
    service_finished = file_spinlock(internal_path('work/run/in/svc-finished'), 1.0)

    service_info = inspect_container(service_container)

    serv_stdout, serv_stderr = destroy_container(service_container)
    prog_stdout, prog_stderr = destroy_container(prog_container)

    error_reason = None

    if not service_info['State']['Running'] and service_info['State']['ExitCode'] != 0:
        error_reason = "service crashed (exit code: {})".format(service_info['State']['ExitCode'])
    elif serv_stderr:
        error_reason = "stderr of the service is not empty"

    if error_reason:
        try:
            with open(internal_path('work/run/service/svc-output.txt'), 'r') as f:
                result_file_content = f.read()
        except IOError as e:
            result_file_content = "(failed to load)"

        raise RunnerConfigurationError('Service container failed. '
                                       + 'Exit code: ' + str(service_info['State']['ExitCode']) + '\n\n'
                                       + '--- SERVICE CONTAINER STDOUT ---\n'
                                       + serv_stdout + '\n\n'
                                       + '--- SERVICE CONTAINER STDERR ---\n'
                                       + serv_stderr + '\n\n'
                                       + '--- SERVICE CONTAINER RESULT FILE ---\n'
                                       + result_file_content)

    logging.info('Prog stdout: {}'.format(prog_stdout))
    logging.info('Prog stderr: {}'.format(prog_stderr))
    logging.info('Serv stdout: {}'.format(serv_stdout))
    logging.info('Serv stderr: {}'.format(serv_stderr))

    if not test_finished or not service_finished:
        return ExecStatus('hard_timeout', timeout=runner_conf['limits']['timeout'],
                          exec_time=runner_conf['limits']['timeout'] + 500)

    data = json.loads(prog_stdout)

    status = 'ok'

    if data['exit_code'] != 0:
        status = 'bad_exit_code'
    elif int(data['exec_time']) > runner_conf['limits']['timeout']:
        status = 'soft_timeout'

    return ExecStatus(status, runner_conf['limits']['timeout'], data['exit_code'], data['exec_time'], None,
                      internal_path('work/run/service/svc-output.txt'))


__plugin__ = {
    "required_images": [prog_image_name]
}
