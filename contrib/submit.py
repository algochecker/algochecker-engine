#!/usr/bin/env python3
import os
import sys
import uuid
import json
import argparse

import redis

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
from worker_conf import REDIS_CONF


rs = redis.Redis(**REDIS_CONF)


def upload_submission(data, content_dirname, debug=False):
    data['uuid'] = str(uuid.uuid4())

    if debug:
        print('Submission UUID: ' + str(data['uuid']))

    for project_file in os.listdir(content_dirname):
        if debug:
            print('Uploading file: ' + project_file)

        with open(content_dirname + '/' + project_file, 'r') as project_fh:
            rs.hset("submission:" + data['uuid'], "file:" + project_file, project_fh.read())

    queue_priority = "medium"
    seq_number = rs.incrby("queue:{}:counter".format(queue_priority), 1)
    rs.zadd("queue:{}:order".format(queue_priority), data['uuid'], seq_number)
    position = rs.rpush("queue:{}".format(queue_priority), json.dumps(data))

    if debug:
        print('Submission sequence number: ' + str(seq_number))
        print('Current position in queue: ' + str(position))

    return data['uuid']


def standalone_main():
    parser = argparse.ArgumentParser(prog='submit.py')
    parser.add_argument('example_name', help='for instance: cpp')
    args = parser.parse_args()

    with open('submission/' + args.example_name + '.json', 'r') as submission_file:
        json_data = json.load(submission_file)

    upload_submission(json_data, 'submission/' + args.example_name + '/', debug=True)

if __name__ == "__main__":
    standalone_main()
