import os
from shutil import copy

from compilers.common import *
from container import make_container

image_name = "gcc:latest"
wrapper_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "gcc", "gcc.sh")


def do_prepare():
    common_prepare()

    makedirs(internal_path('work/compile/work/opt'))
    makedirs(internal_path('work/compile/work/src'))
    makedirs(internal_path('work/compile/work/obj'))
    makedirs(internal_path('work/compile/work/inject'))

    copy(wrapper_path, internal_path('work/compile/work/gcc.sh'))
    os.chmod(internal_path('work/compile/work/gcc.sh'), 0o500)
    chown_recursive(internal_path('work/compile'), DOCKER_CONTAINER_USER, DOCKER_CONTAINER_GROUP)


def do_compile(compiler_conf, pack):
    with open(internal_path('work/compile/work/opt/comp_opt'), 'w') as f:
        f.write(compiler_conf['command_line'])

    with open(internal_path('work/compile/work/opt/inject_comp_opt'), 'w') as f:
        f.write(compiler_conf['inject_command_line'])

    with open(internal_path('work/compile/work/opt/link_opt'), 'w') as f:
        f.write(compiler_conf['link_command_line'])

    with open(internal_path('work/compile/work/opt/strip_opt'), 'w') as f:
        f.write(compiler_conf['strip_command_line'])

    for fname in compiler_conf['inject_files']:
        copy(os.path.join(pack.path, fname), internal_path(os.path.join('work/compile/work/inject', fname)))

    container = make_container(image_name, ['/mnt/work/gcc.sh'], common_binds(), common_host_config(compiler_conf))
    # TODO check exit code to determine possible errors
    return common_compile(container, compiler_conf)


__plugin__ = {
    "required_images": [image_name]
}