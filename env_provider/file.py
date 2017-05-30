import logging
from filecmp import cmp
from os import chmod, path, walk

from shutil import rmtree, copytree, copy

import plugin_loader
import task_queue
from tuples import TestStatus
from workdir import internal_path
import env_provider.common as common


def do_create_test_units(submission, env_conf, pack):
    return common.do_create_test_units(submission, env_conf, pack)


def copy_data_directory(pack, test_unit):
    if path.exists(path.join(pack.path, 'data', test_unit.name)):
        rmtree(internal_path('work/run/data'))
        copytree(path.join(pack.path, 'data', test_unit.name), internal_path('work/run/data'))

    # give permissions for data directory
    chmod(internal_path('work/run/data'), 0o777)

    for root, dirs, files in walk(internal_path('work/run/data')):
        for entry in dirs:
            chmod(path.join(root, entry), 0o777)
        for entry in files:
            chmod(path.join(root, entry), 0o666)


def compare(fname1, fname2, binary_mode=False):
    if binary_mode:
        return cmp(fname1, fname2, shallow=False)

    f1 = open(fname1, 'r')
    f2 = open(fname2, 'r')

    while True:
        line1 = f1.readline()
        line2 = f2.readline()

        # if one of files had already ended then for sure it's not equal
        if not line1 and line2 or line1 and not line2:
            return False

        # if both files ended at the same time then these are equal
        if not line1 and not line2:
            return True

        # if given line doesn't match then files are not equal
        if line1.strip() != line2.strip():
            return False


def do_run_test(submission, env_conf, pack, test_unit):
    runner, runner_conf = plugin_loader.get('runners', pack.config['runner']['name'], pack.config['runner'])

    runner.do_prepare(runner_conf)
    # input everything which was outputted from the compilation
    rmtree(internal_path('work/run/in'))
    copytree(internal_path('work/compile/out'), internal_path(path.join('work/run/in')))

    copy_data_directory(pack, test_unit)

    # upload input file for the test for the runner
    copy(test_unit.runner_meta['input_file'], internal_path('work/run/in/input.txt'))

    prog_container = runner.do_run(runner_conf)
    exc_res = runner.do_wait(runner_conf, prog_container)
    cmp_res = compare(internal_path('work/run/out/output.txt'), test_unit.runner_meta['output_file'])

    try:
        if test_unit.runner_meta['options']['store_output'] != 'none':
            logging.info('Storing output for the test {}'.format(test_unit.name))
            with open(test_unit.runner_meta['output_file'], 'r', encoding='utf-8') as output_file:
                task_queue.upload_test_output(submission['uuid'], test_unit.name, output_file.read(), test_unit.runner_meta['store_output'])
    except KeyError:
        pass

    points = 0.0

    try:
        max_points = test_unit.runner_meta['options']['points']
    except KeyError:
        max_points = 1.0

    if exc_res.status != 'ok':
        status = exc_res.status
    elif not cmp_res:
        status = 'bad_answer'
    else:
        status = 'ok'
        points = max_points

    return TestStatus(name=test_unit.name, status=status, time=exc_res.exec_time,
                      timeout=exc_res.timeout, memory=exc_res.memory, points=points, max_points=max_points)

__plugin__ = {}
