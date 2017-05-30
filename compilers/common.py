from os import makedirs, listdir
from os.path import join as path_join
from shutil import rmtree
from requests.exceptions import ReadTimeout
from tuples import CompileStatus
from workdir import internal_path
from container import chown_recursive, docker_cli, destroy_container
from worker_conf import DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP


class CompilerConfigurationError(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def common_binds():
    return {
        internal_path("work/compile/in"): {
            "bind": "/mnt/in",
            "mode": "ro"
        },
        internal_path("work/compile/work"): {
            "bind": "/mnt/work",
            "mode": "rw"
        },
        internal_path("work/compile/out"): {
            "bind": "/mnt/out",
            "mode": "rw"
        }
    }


def common_host_config(package_conf):
    return {
        "mem_limit": package_conf['limits']['max_memory'],
        "cpu_quota": package_conf['limits']['cpu_quota'],
        "cpu_period": package_conf['limits']['cpu_period'],
        "network_mode": "none"
    }


def common_prepare():
    rmtree(internal_path('work/compile'), ignore_errors=True)

    makedirs(internal_path('work/compile/in'))
    makedirs(internal_path('work/compile/out'))
    makedirs(internal_path('work/compile/work'))

    chown_recursive(internal_path('work/compile'), DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP)


def common_compile(container, package_config):
    docker_cli.start(container)

    timeout = int(package_config['limits']['timeout'] / 1000)

    try:
        code = docker_cli.wait(container, timeout=timeout)
    except ReadTimeout:
        status = 'timeout'
    else:
        if code == 0:
            status = 'ok'
        else:
            status = 'error'

    stdout, stderr = destroy_container(container)
    return CompileStatus(status, stderr + stdout)


def pick_compilation_units(extensions):
    for project_file in listdir(internal_path("work/compile/in")):
        for ext in extensions:
            if project_file.endswith(ext):
                yield path_join('/mnt/in', project_file)
