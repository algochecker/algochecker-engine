import os
from container import make_container
from runners.common import *

image_name = "java:openjdk-8"
wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "java", "run-java.sh")


def do_create_test_units(runner_conf, pack):
    return common_create_test_units(runner_conf, pack)


def do_prepare(runner_conf, test_unit, pack):
    common_prepare(pack, wrapper_path, test_unit.runner_meta['input_file'])


def do_run(runner_conf, test_unit, pack):
    container = make_container(image_name, common_command(), common_binds(), common_host_config(runner_conf))
    return common_run(container, runner_conf)


__plugin__ = {
    "required_images": [image_name]
}
