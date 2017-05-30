import os

from container import make_container, create_network, get_endpoint_config
from runners.common import *


image_name = "gcc:latest"
cli_wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin-network", "run-client.sh")
srv_wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin-network", "run-server.sh")





def do_create_test_units(env_conf, pack):
    # TODO: enumerate test units from the package and create metadata
    pass


def do_run_test(env_conf, pack, test_unit):
    # TODO: fetch runner from the plugin manager
    # TODO: configure runner appropriately
    # TODO: set-up the environment for the test
    # TODO: invoke runner
    # TODO: grab results and return ExecRes
    pass











def base_binds():
    return {
        internal_path("work/run/scripts"): {
            "bind": "/mnt/scripts",
            "mode": "ro"
        },
        internal_path("work/run/shared"): {
            "bind": "/mnt/shared",
            "mode": "rw"
        }
    }


def client_binds():
    binds = base_binds()
    binds.update({
        internal_path("work/run/client"): {
            "bind": "/mnt/client",
            "mode": "rw"
        }
    })
    return binds


def server_binds():
    binds = base_binds()
    binds.update({
        internal_path("work/run/server"): {
            "bind": "/mnt/server",
            "mode": "rw"
        }
    })
    return binds


def do_create_test_units(runner_conf, pack):
    return common_create_test_units(runner_conf, pack)


def do_prepare(runner_conf, test_unit, pack):
    rmtree(internal_path('work/run'), ignore_errors=True)

    copytree(internal_path('work/compile/out'), internal_path('work/run/client'))

    makedirs(internal_path('work/run/server'))
    makedirs(internal_path('work/run/scripts'))
    makedirs(internal_path('work/run/shared'))

    copy(srv_wrapper_path, internal_path('work/run/scripts/run-server.sh'))
    copy(cli_wrapper_path, internal_path('work/run/scripts/run-client.sh'))

    if not runner_conf['server']['file']:
        raise RunnerConfigurationError('Configuration key server.file was not provided!')

    copy(os.path.join(pack.path, runner_conf['server']['file']), internal_path('work/run/server/server'))

    chmod(internal_path('work/run/scripts/run-server.sh'), 0o555)
    chmod(internal_path('work/run/scripts/run-client.sh'), 0o555)

    chown_recursive(internal_path('work/run'), DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP)


def do_run(runner_conf, test_unit, pack):
    network_id = create_network()

    srv_container = make_container(
        runner_conf['server']['image'],
        ['/mnt/scripts/run-server.sh'],
        server_binds(),
        common_host_config(runner_conf),
        networking_config=get_endpoint_config('server')
    )

    docker_cli.start(srv_container)

    cli_container = make_container(
        runner_conf['client']['image'],
        ['/mnt/scripts/run-client.sh'],
        client_binds(),
        common_host_config(runner_conf),
        networking_config=get_endpoint_config('client')
    )

    docker_cli.start(cli_container)

    if not file_spinlock(internal_path('work/run/client/ready'), 1.0):
        raise RuntimeError('Client\'s wrapper script did not unlock "ready" lock within 1 second.')

    reset_memory_peak(cli_container)

    if not file_spinlock(internal_path('work/run/server/ready'), 1.0):
        raise RuntimeError('Server\'s wrapper script did not unlock "ready" lock within 1 second.')

    open(internal_path('work/run/client/ready_ok'), 'w').close()

    test_limit_sec = (float(runner_conf['limits']['timeout']) / 1000.0) + 0.5
    test_finished = file_spinlock(internal_path('work/run/client/finished'), test_limit_sec)

    server_finished = file_spinlock(internal_path('work/run/server/finished'), 1.0)

    try:
        stats = quickly_get_stats(cli_container)
    except QuickStatsNotAvailable:
        stats = docker_cli.stats(container=cli_container, decode=True, stream=False)

    used_memory = stats['memory_stats']['max_usage']

    srv_stdout, srv_stderr = destroy_container(srv_container)
    cli_stdout, cli_stderr = destroy_container(cli_container)
    docker_cli.remove_network(network_id)
    del network_id

    logging.info('Cli stdout: {}'.format(cli_stdout))
    logging.info('Cli stderr: {}'.format(cli_stderr))
    logging.info('Srv stdout: {}'.format(srv_stdout))
    logging.info('Srv stderr: {}'.format(srv_stderr))

    if not test_finished:
        return ExecStatus('hard_timeout', timeout=runner_conf['limits']['timeout'],
                          exec_time=runner_conf['limits']['timeout'] + 500)

    if not server_finished:
        logging.warning('Server failed to finish correctly')
        # TODO define behaviour in case of server failing to exit

    # TODO define in config which output to store (server and/or client and/or with/without error)

    fnames = [internal_path('work/run/client/output.txt'), internal_path('work/run/client/error.txt'),
              internal_path('work/run/server/output.txt'), internal_path('work/run/server/error.txt')]

    with open(internal_path('work/run/common-output.txt'), 'w') as co:
        for file in fnames:
            with open(file, 'r') as f:
                co.write("file: {}\n\n".format(file))
                co.write(f.read())

    try:
        # TODO detect malformed JSON, bad exit code, timeout etc.
        data = json.loads(cli_stdout)
    except ValueError:
        # FOR DEBUG:
        return ExecStatus('debug', 4000, '0', '0', used_memory, internal_path('work/run/common-output.txt'))
        # raise RuntimeError('Unable to decode the output from stdout')

    status = 'ok'

    if data['exit_code'] != 0:
        status = 'bad_exit_code'

    return ExecStatus(status, runner_conf['limits']['timeout'], data['exit_code'], data['exec_time'], used_memory,
                      internal_path('work/run/common-output.txt'))


__plugin__ = {
    "required_images": [image_name]
}
