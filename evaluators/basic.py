import logging
from os.path import join, exists
from filecmp import cmp

import task_queue
from tuples import EvalStatus
from workdir import internal_path


class EvaluatorConfigurationError(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def extract_group(full_name):
    """
    If the test name is like gr1-test1 then we treat the part before dash
    as the group and the rest as test name.
    """
    if '-' in full_name:
        return full_name.split('-', 1)
    else:
        return None, full_name


def do_process_results(evaluator_conf, results, **kwargs):
    passed_test_groups = {}

    # 1st iteration: check if all tests in particular group were passed
    for result in results:
        group, name = extract_group(result['name'])

        if group:
            if group not in passed_test_groups:
                # create key if it doesn't exist
                passed_test_groups[group] = True

            if result['points'] <= 0:
                # set the test group as failed
                passed_test_groups[group] = False

    # 2nd iteration: grab points from all tests in the group if any test was failed
    total_points = 0
    max_points = 0

    for result in results:
        max_points += result['max_points']
        group, name = extract_group(result['name'])

        if group:
            if not passed_test_groups[group]:
                result['points'] = 0
            elif result['timeout'] * evaluator_conf['slow_program_threshold'] < result['time']:
                # subtract some fraction of points if the program nearly hit the timeout
                # according to what was configured
                threshold_val = result['timeout'] * evaluator_conf['slow_program_threshold']
                threshold_sub = result['time'] - threshold_val
                threshold_max = result['timeout'] - threshold_val

                if evaluator_conf['slow_program_scale'] == "linear":
                    subtract_percent = min(threshold_sub / threshold_max, 1) * evaluator_conf['slow_program_penalty']
                    result['points'] -= result['max_points'] * subtract_percent
                elif evaluator_conf['slow_program_scale'] == "constant":
                    result['points'] -= evaluator_conf['slow_program_penalty']
                else:
                    raise EvaluatorConfigurationError('Invalid value in "slow_program_scale" parameter.')

        # normalize any values below 0.0 or above `max_points`
        result['points'] = max(min(result['points'], result['max_points']), 0)

        total_points += result['points']

    return int(total_points * 100 / max_points), results

__plugin__ = {}
