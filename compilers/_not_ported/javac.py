from compilers.common import *
from container import make_container

image_name = "java:openjdk-8"


def make_command():
    in_files = list(pick_compilation_units(['.java']))

    return ["javac"] + in_files + ["-d", "/mnt/out"]


def do_prepare():
    common_prepare()


def do_compile(package_config):
    container = make_container(image_name, make_command(), common_binds(), common_host_config(package_config))
    return common_compile(container, package_config)


__plugin__ = {
    "required_images": [image_name]
}
