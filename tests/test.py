import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from contrib.submit import upload_submission
from contrib.collect import fetch_evaluation, convert_test_list


def test_file_good():
    uuid = upload_submission({
        "uuid": None,
        "package": {
            "name": "test-file",
            "version": 1455108897,
            "url": "http://127.0.0.1:5000/repo/test-file.zip"
        },
        "config": "gcc-cpp",
        "features": ["async_report"]
    }, 'contrib/submission/test-file-good/')

    evl = fetch_evaluation(uuid)
    tests = convert_test_list(evl['tests'])
    print(json.dumps(evl, indent=4))

    assert evl['status'] == 'ok'
    assert evl['score'] == 25
    assert tests['test1']['status'] == 'ok'
    assert tests['test2']['status'] == 'bad_answer'
    assert tests['test3']['status'] == 'hard_timeout'
    assert tests['test4']['status'] == 'soft_timeout'


def test_file_bad():
    uuid = upload_submission({
        "uuid": None,
        "package": {
            "name": "test-file",
            "version": 1455108897,
            "url": "http://127.0.0.1:5000/repo/test-file.zip"
        },
        "config": "gcc-cpp",
        "features": ["async_report"]
    }, 'contrib/submission/test-file-bad/')

    evl = fetch_evaluation(uuid)
    tests = convert_test_list(evl['tests'])
    print(json.dumps(evl, indent=4))

    assert evl['status'] == 'compile_error'
    assert evl['score'] == 0
    assert evl['tests'] == []
    assert 'nonexistent_method' in evl['message']
    assert 'not declared' in evl['message']


def test_pipe():
    uuid = upload_submission({
        "uuid": None,
        "package": {
            "name": "test-pipe",
            "version": 1455108897,
            "url": "http://127.0.0.1:5000/repo/test-pipe.zip"
        },
        "config": "gcc-cpp",
        "features": ["async_report"]
    }, 'contrib/submission/test-pipe/')

    evl = fetch_evaluation(uuid)
    tests = convert_test_list(evl['tests'])
    print(json.dumps(evl, indent=4))

    assert evl['score'] == 100

    assert tests['test1']['status'] == 'ok'
    assert tests['test1']['points'] == 6
    assert tests['test1']['max_points'] == 6

    assert tests['test2']['status'] == 'ok'
    assert tests['test2']['points'] == 6
    assert tests['test2']['max_points'] == 6


def test_pipe_timeout():
    uuid = upload_submission({
        "uuid": None,
        "package": {
            "name": "test-pipe",
            "version": 1455108897,
            "url": "http://127.0.0.1:5000/repo/test-pipe.zip"
        },
        "config": "gcc-cpp",
        "features": ["async_report"]
    }, 'contrib/submission/test-pipe-timeout/')

    evl = fetch_evaluation(uuid)
    tests = convert_test_list(evl['tests'])
    print(json.dumps(evl, indent=4))

    assert evl['score'] == 0

    assert tests['test1']['status'] == 'hard_timeout'
    assert tests['test1']['time'] == 1500
    assert tests['test1']['timeout'] == 1000
    assert tests['test1']['points'] == 0
    assert tests['test1']['max_points'] == 1

    assert tests['test2']['status'] == 'hard_timeout'
    assert tests['test2']['time'] == 1500
    assert tests['test2']['timeout'] == 1000
    assert tests['test2']['points'] == 0
    assert tests['test2']['max_points'] == 1


def test_pipe_wrong_result():
    uuid = upload_submission({
        "uuid": None,
        "package": {
            "name": "test-pipe",
            "version": 1455108897,
            "url": "http://127.0.0.1:5000/repo/test-pipe.zip"
        },
        "config": "gcc-cpp",
        "features": ["async_report"]
    }, 'contrib/submission/test-pipe-wrong-result/')

    evl = fetch_evaluation(uuid)
    tests = convert_test_list(evl['tests'])
    print(json.dumps(evl, indent=4))

    assert evl['score'] == 83

    assert tests['test1']['status'] == 'ok'
    assert tests['test1']['points'] == 5
    assert tests['test1']['max_points'] == 6

    assert tests['test2']['status'] == 'ok'
    assert tests['test2']['points'] == 5
    assert tests['test2']['max_points'] == 6


test_file_bad()
test_file_good()
test_pipe()
test_pipe_timeout()
test_pipe_wrong_result()
