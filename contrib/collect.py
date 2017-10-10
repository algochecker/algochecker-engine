#!/usr/bin/env python3
import argparse
import json
import os
import sys
from time import sleep

import redis

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
from worker_conf import REDIS_CONF


class EvaluationFetchTimeout(Exception):
    pass


rs = redis.Redis(**REDIS_CONF)


def fetch_evaluation(uuid=None, timeout=10.0):
    pubsub = rs.pubsub()
    pubsub.subscribe("reports")

    while timeout > 0:
        msg = pubsub.get_message()

        if msg is not None and msg['type'] == 'message':
            data = json.loads(msg['data'].decode('utf8'))

            if uuid is None or ('uuid' in data and data['uuid'] == uuid):
                pubsub.unsubscribe("reports")
                return data

        timeout -= 0.01
        sleep(0.01)

    pubsub.unsubscribe("reports")
    raise EvaluationFetchTimeout('Failed to fetch evaluation within {} seconds.'.format(timeout))


def convert_test_list(data):
    return {test['name']: test for test in data}


def standalone_main():
    parser = argparse.ArgumentParser(prog='collect.py')
    parser.add_argument('--table', help='tabular mode', action='store_true')

    args = parser.parse_args()

    pubsub = rs.pubsub()
    pubsub.subscribe("reports")

    if args.table:
        print('uuid\tstatus\tscore\tchecked by\tstarted\ttook time')

    for data in pubsub.listen():
        if args.table:
            if data['type'] != 'message':
                continue

            report = json.loads(data['data'].decode('utf-8'))
            print('{}\t{}\t{}\t{}\t{}\t{}'.format(
                report['uuid'], report['status'], report['score'], report['checked_by'],
                report['time_stats']['started_ms'], report['time_stats']['took_time_ms']))
        else:
            print(data)

if __name__ == "__main__":
    standalone_main()
