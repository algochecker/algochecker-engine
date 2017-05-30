from os import path, listdir, chmod, walk, makedirs
from os.path import splitext

from shutil import rmtree, copytree

from tuples import TestUnit
from workdir import internal_path


class EnvConfigurationError(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def do_create_test_units(submission, env_conf, pack):
    test_units = []

    if path.exists(path.join(pack.path, 'input')):
        # deprecated method, to be removed in the future
        for test_file in sorted(listdir(path.join(pack.path, 'input'))):
            if test_file.startswith('.'):
                continue

            test_name = splitext(test_file)[0]
            test_meta = {
                "input_file": path.join(pack.path, 'input', test_file),
                "output_file": path.join(pack.path, 'output', test_file),
            }

            try:
                test_meta["options"] = pack.config['env']['tests'][test_name]
            except KeyError:
                test_meta["options"] = {}

            test_units.append(TestUnit(name=test_name, runner_meta=test_meta))

        if not len(test_units):
            msg = 'No files were found in the "input" directory, expected at least one.'
            raise EnvConfigurationError(msg)
    elif path.exists(path.join(pack.path, 'tests')):
        for test_file in sorted(listdir(path.join(pack.path, 'tests'))):
            if not test_file.startswith('in-'):
                continue

            in_prefix, test_name = splitext(test_file)[0].split('-', 1)
            test_meta = {
                "input_file": path.join(pack.path, 'tests', test_file),
                "output_file": path.join(pack.path, 'tests', 'out-' + test_file.split('-', 1)[1]),
            }

            try:
                test_meta["options"] = pack.config['env']['tests'][test_name]
            except KeyError:
                test_meta["options"] = {}

            test_units.append(TestUnit(name=test_name, runner_meta=test_meta))

        if not len(test_units):
            msg = 'No files with "in-" prefix were found in the "tests" directory, expected at least one.'
            raise EnvConfigurationError(msg)
    else:
        raise EnvConfigurationError('Neither "tests" nor "input" directory was found in the package.')

    return test_units


def copy_data_directory(pack, test_unit):
    rmtree(internal_path('work/run/data'))

    if path.exists(path.join(pack.path, 'data', test_unit.name)):
        copytree(path.join(pack.path, 'data', test_unit.name), internal_path('work/run/data'))
    else:
        makedirs(internal_path('work/run/data'))

    # give permissions for data directory
    chmod(internal_path('work/run/data'), 0o777)

    for root, dirs, files in walk(internal_path('work/run/data')):
        for entry in dirs:
            chmod(path.join(root, entry), 0o777)
        for entry in files:
            chmod(path.join(root, entry), 0o666)

