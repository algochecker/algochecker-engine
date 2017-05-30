import json
import os

from shutil import rmtree, copy

from os import path, makedirs, chmod, walk

from container import make_container, chown_recursive, docker_cli, file_spinlock, reset_memory_peak, quickly_get_stats, \
    QuickStatsNotAvailable, destroy_container
from tuples import ExecStatus
from workdir import internal_path
from worker_conf import DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP

wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin", "run-bin.sh")


def command():
    return ['/mnt/scripts/run.sh']


def binds(real_location, additional_binds=None):
    base_binds = {
        internal_path(os.path.join(real_location, "scripts")): {
            "bind": "/mnt/scripts",
            "mode": "ro"
        },
        internal_path(os.path.join(real_location, "in")): {
            "bind": "/mnt/in",
            "mode": "ro"
        },
        internal_path(os.path.join(real_location, "out")): {
            "bind": "/mnt/out",
            "mode": "rw"
        },
        internal_path(os.path.join(real_location, "data")): {
            "bind": "/mnt/data",
            "mode": "rw"
        }
    }

    if additional_binds:
        base_binds.update(additional_binds)

    return base_binds


def host_config(package_config):
    return {
        "mem_limit": package_config['limits']['max_memory'],
        "cpu_quota": package_config['limits']['cpu_quota'],
        "cpu_period": package_config['limits']['cpu_period'],
        "network_mode": "none"
    }


def do_prepare(runner_conf):
    real_location = runner_conf['location']

    rmtree(internal_path(real_location), ignore_errors=True)

    # create working directory "data"
    makedirs(internal_path(os.path.join(real_location, 'data')))

    # create the directory for runner's input and output
    makedirs(internal_path(os.path.join(real_location, 'in')))
    makedirs(internal_path(os.path.join(real_location, 'out')))

    # create the directory for all necessary scripts
    makedirs(internal_path(os.path.join(real_location, 'scripts')))
    # copy the wrapper script which would be used as container's starting command
    copy(wrapper_path, internal_path(os.path.join(real_location, 'scripts/run.sh')))

    # make sure that the container starting command is executable
    chmod(internal_path(os.path.join(real_location, 'scripts/run.sh')), 0o500)
    # ensure that exec_user will have the proper permissions
    chown_recursive(internal_path(real_location), DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP)


def do_run(runner_conf, additional_binds=None):
    real_location = runner_conf['location']

    container = make_container(runner_conf['image'], command(), binds(real_location, additional_binds), host_config(runner_conf))
    docker_cli.start(container)

    # wait until runner says it's ready
    if not file_spinlock(internal_path(os.path.join(real_location, 'out/ready')), 1.0):
        raise RuntimeError('Runner\'s wrapper script had not unlocked "ready" lock within 1 second.')

    # bare initialization of docker container would bring memory peak usage indicator
    # to the value of 7-10 MB (at least), we need to reset the counter to zero after
    # the container has initialized in order to have more reliable measurement
    reset_memory_peak(container)

    # tell runner that it can begin the test
    open(internal_path(os.path.join(real_location, 'in/ready_ok')), 'w').close()
    return container


def do_wait(runner_conf, container, max_time=None):
    real_location = runner_conf['location']

    # wait (timeout + 0.2) seconds for the runner to indicate that the work is finished
    # if it would not finish within that time, we destroy the container and say that
    # this test is hitting "hard_timeout"
    limit_sec = (float(runner_conf['limits']['timeout']) / 1000.0) + 0.5

    if max_time:
        limit_sec = min(limit_sec, max_time)

    test_finished = file_spinlock(internal_path(os.path.join(real_location, 'out/finished')), limit_sec)

    # collect the statistics of the container before stopping it
    # (after stopping docker would not allow to collect stats anymore)
    try:
        stats = quickly_get_stats(container)
    except QuickStatsNotAvailable:
        stats = docker_cli.stats(container=container, decode=True, stream=False)

    stdout, stderr = destroy_container(container)
    return make_result(runner_conf, stdout, stderr, stats, test_finished)


def make_result(runner_conf, stdout, stderr, stats, test_finished):
    used_memory = stats['memory_stats']['max_usage'] if stats else None
    timeout_ms = int(runner_conf['limits']['timeout'])

    # the test was interrupted after exceeding the allowed time
    if not test_finished:
        exec_limit_ms = timeout_ms + 500
        return ExecStatus('hard_timeout', timeout=timeout_ms, exec_time=exec_limit_ms, memory=used_memory)

    # load the JSON which wrapper script should basically output to its' stdout
    res = json.loads(stdout)

    if res['exit_code'] == 0 and res['exec_time'] < timeout_ms:
        status = 'ok'
    elif res['exit_code'] != 0:
        status = 'bad_exit_code'
    else:
        status = 'soft_timeout'

    return ExecStatus(status, timeout_ms, res['exit_code'], res['exec_time'], used_memory)


__plugin__ = {
    "required_images": []
}
