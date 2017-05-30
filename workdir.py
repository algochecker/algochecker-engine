from os.path import join as path_join
from os import makedirs
from shutil import rmtree
from worker_conf import INSTANCE_NAME


def internal_path(sub_path):
    return path_join('/tmp/algochecker', INSTANCE_NAME, sub_path)


def recreate_workdir():
    rmtree(internal_path('work'), ignore_errors=True)
    makedirs(internal_path('work'))
