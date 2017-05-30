#!/usr/bin/env python3
import argparse
import os
import sys

import redis

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
from worker_conf import REDIS_CONF

parser = argparse.ArgumentParser(prog='queue.py')
args = parser.parse_args()

rs = redis.Redis(**REDIS_CONF)

for priority in ['high', 'medium', 'low']:
    print('> Priority {}'.format(priority))
    print('> Real length: {}'.format(rs.llen('queue:{}'.format(priority))))
    queue_order = rs.zrange('queue:{}:order'.format(priority), 0, -1, desc=False, withscores=True)

    for queue_item in queue_order:
        print('#{}: {}'.format(int(queue_item[1]), queue_item[0].decode('utf-8')))
