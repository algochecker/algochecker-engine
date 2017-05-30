from itertools import cycle, chain
import json
import logging

import inspect
import datetime
import docker
import sys

from docker import utils as docker_utils
from docker.errors import APIError
from time import sleep, time
from os import walk, chown, makedirs
from os.path import exists as path_exists, join as path_join
from shutil import getpwnam, getgrnam
import plugin_loader
from worker_conf import DOCKER_CONF, DOCKER_CONTAINER_USER, INSTANCE_NAME, NETWORKING_CONF

from workdir import internal_path

"""
Global instance of Docker client.
"""
docker_cli = docker.Client(**DOCKER_CONF)

"""
Global network name
"""
network_name = "{}-{}".format(INSTANCE_NAME, NETWORKING_CONF['network_name'])


class PluginError(RuntimeError):
    def __init__(self, message, plugin_path, **kwargs):
        RuntimeError.__init__(self, message, **kwargs)

        self.plugin_path = plugin_path


class QuickStatsNotAvailable(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def make_container(image, command, binds, host_config, **kwargs):
    return docker_cli.create_container(
        image=image,
        command=command,
        user=DOCKER_CONTAINER_USER,
        host_config=docker_cli.create_host_config(
            binds=binds,
            **host_config
        ),
        labels=["algochecker-{}".format(INSTANCE_NAME)],
        **kwargs
    )


def inspect_container(container):
    return docker_cli.inspect_container(container)


def destroy_container(container):
    docker_cli.stop(container, timeout=0)

    stdout = docker_cli.logs(container, stdout=True, stderr=False, stream=False, timestamps=False).decode('utf-8')
    stderr = docker_cli.logs(container, stdout=False, stderr=True, stream=False, timestamps=False).decode('utf-8')

    docker_cli.remove_container(container, force=True)

    return stdout, stderr


def safe_plugin_call(plugin, func):
    try:
        return func()
    except Exception as e:
        plugin_path = inspect.getfile(plugin)
        raise PluginError('Failed inside plugin code', plugin_path) from e


def save_leak_report(container):
    inspect_data = json.dumps(docker_cli.inspect_container(container), indent=4, separators=(',', ': '))
    logs = docker_cli.logs(container, stdout=True, stderr=True, stream=False, timestamps=True).decode('utf-8')

    try:
        makedirs(internal_path('error_report'))
    except FileExistsError:
        pass

    now = datetime.datetime.now()

    report_name = 'container_leak_{}_{}.log'.format(now.strftime('%Y%m%d_%H%M%S'), container)
    full_report_path = internal_path(path_join('error_report', report_name))

    with open(full_report_path, 'w') as report_f:
        report_f.write('Report about leaked container {}\n'.format(container))
        report_f.write('Generated on: {}\n'.format(now.isoformat()))
        report_f.write('\n=== Inspection data (length: {}) ===\n'.format(len(inspect_data)))
        report_f.write(inspect_data)
        report_f.write('\n=== Container logs (length: {}) ===\n'.format(len(logs)))
        report_f.write(logs)
        report_f.write('\n=== End of report ===\n')

    return full_report_path


def check_lost_containers(no_header=False):
    logging.info('Checking lost containers...')
    algo_label = 'algochecker-{}'.format(INSTANCE_NAME)

    lost = (container['Id'] for container in docker_cli.containers(all=True, filters={"label": algo_label}))
    saved_reports = []

    for container in lost:
        if not no_header:
            logging.error('--- LOST CONTAINER NOTICE ---')
        logging.error('Found lost container: {}. Container leak report will be generated.'.format(container))
        report_path = save_leak_report(container)
        saved_reports.append(report_path)
        logging.error('IMPORTANT! In order to find out the details about this leaked container '
                      + 'please refer to the report stored at: {}'
                      .format(report_path))
        logging.error('Destroying the container...')
        docker_cli.remove_container(container, force=True)
        if not no_header:
            logging.error('-----------------------------')

    return saved_reports


def download_image(image_name):
    spinner = cycle(['oO', 'Oo'])
    last_update = 0
    sys.stdout.write("Please wait, working... " + next(spinner))
    sys.stdout.flush()

    for line in docker_cli.pull(image_name, stream=True):
        info = json.loads(line.decode('utf-8'))

        if 'error' in info:
            logging.error("Failed to download docker image {}".format(image_name))
            logging.error(info['error'])
            raise RuntimeError("Failed to download docker image {}".format(image_name))

        current = time()

        if current - last_update > 1.0:
            last_update = current

            sys.stdout.write("\b\b" + next(spinner))
            sys.stdout.flush()

    sys.stdout.write("\n")
    sys.stdout.flush()

    print("Docker image was fetched successfully.")


def check_image_dependencies():
    logging.info('Checking image dependencies...')

    owned = set(chain.from_iterable(el['RepoTags'] for el in docker_cli.images()))
    required = set()

    for module in plugin_loader.get_all('compilers').values():
        required.update(module.__plugin__['required_images'])

    for module in plugin_loader.get_all('runners').values():
        required.update(module.__plugin__['required_images'])

    for image_name in required:
        if image_name not in owned:
            logging.warning('Docker image {} was not found. Attempting to download it.'.format(image_name))
            download_image(image_name)

    logging.info('Found all {:d} required images.'.format(len(required)))


def file_spinlock(file_name, timeout, step=0.01):
    """
    Run a spinlock, which will last until file with name `file_name` is created.
    Maximal waiting time is determined by `timeout` argument (in seconds).
    File existence will be checked every `step` seconds.
    :return True if spinlock was unlocked; False if timeout occurred
    """
    elapsed = 0.0

    while elapsed < timeout:
        if path_exists(file_name):
            return True

        elapsed += step
        sleep(step)

    return False


def quickly_get_stats(container):
    """
    Cheat method which returns partial stats in the Docker's format without
    using docker.stats() call which has time overhead of few seconds.
    Good alternative to call if the runner would be satisfied with concise stats.
    :param container: Docker container object.
    :return Incomplete statistics in docker.stats() format as described in docker-py docs.
    """
    if type(container) is dict:
        container = container['Id']

    file_name = '/sys/fs/cgroup/memory/docker/{}/memory.max_usage_in_bytes'.format(container)

    # TODO read /var/lib/docker/containers/{}/config.v2.json - exit code, start time and finish time are there

    try:
        with open(file_name, 'r') as f:
            memory_max_usage = int(f.read())
    except IOError:
        logging.exception('Failed to quickly get container stats. Peak memory usage is not available.')
        raise QuickStatsNotAvailable()

    return {
        "memory_stats": {
            "max_usage": memory_max_usage
        }
    }


def reset_memory_peak(container):
    if type(container) is dict:
        container = container['Id']

    file_name = '/sys/fs/cgroup/memory/docker/{}/memory.max_usage_in_bytes'.format(container)

    with open(file_name, 'w') as f:
        f.write('0')


def chown_recursive(path, user, group):
    uid = getpwnam(user).pw_uid
    gid = getgrnam(group).gr_gid

    for root, dirs, files in walk(path):
        for dir_name in dirs:
            chown(path_join(root, dir_name), uid, gid)

        for file_name in files:
            chown(path_join(root, file_name), uid, gid)


def shrink_logs(logs, max_lines=250, max_bytes=12288):
    log_parts = logs.split("\n")
    log_size = len(logs)
    logs = "\n".join(log_parts[:max_lines])

    if log_size > max_bytes:
        logs = logs[:max_bytes]
        logs += "\n\n(algochecker: truncated the rest of output, {} bytes in total)".format(log_size)
    elif len(log_parts) > max_lines:
        logs += "\n\n(algochecker: truncated the rest of output, {} lines in total)".format(len(log_parts))

    return logs


# network

def create_network():
    ipam_config = docker_utils.create_ipam_config(
        pool_configs=[docker_utils.create_ipam_pool(
            subnet=NETWORKING_CONF['ipam']['subnet'],
            iprange=NETWORKING_CONF['ipam']['iprange']
        )]
    )

    network = docker_cli.create_network(
        name=network_name,
        driver=NETWORKING_CONF['network_driver'],
        ipam=ipam_config,
        internal=NETWORKING_CONF['internal']
    )

    return network.get('Id')


def get_endpoint_config(e_type):
    return docker_cli.create_networking_config({
        network_name: docker_cli.create_endpoint_config(
            ipv4_address=NETWORKING_CONF['endpoints']['client_ip' if e_type == 'client' else 'server_ip']
        )
    })


def check_leftover_networks():
    logging.info("Checking leftover networks...")
    try:
        networks = docker_cli.networks(names=["{}-{}".format(INSTANCE_NAME, NETWORKING_CONF['network_name'])])
        for network in networks:
            docker_cli.remove_network(network['Id'])

        if len(networks) > 0:
            logging.info("Removed {} leftover network(s)".format(len(networks)))
    except (APIError, KeyError):
        logging.error("Unable to check for leftover networks")
