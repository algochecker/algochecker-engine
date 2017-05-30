#!/usr/bin/env python3
import os
import sys
import argparse

import redis
from os.path import relpath, join

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
from worker_conf import REDIS_CONF

parser = argparse.ArgumentParser(prog='dynamic_package.py')
parser.add_argument('example_directory', help='for instance: avl')
parser.add_argument('package_name', help='what package name should be registered in Redis')
parser.add_argument('package_version', help='what package version should be registered in Redis')
args = parser.parse_args()

rs = redis.Redis(**REDIS_CONF)

package_key = 'package:{}:{}'.format(args.package_name, args.package_version)
package_path = 'package/' + args.example_directory + '/'

print('Uploading package to key: {}'.format(package_key))
rs.delete(package_key)

for root, dirs, files in os.walk(package_path):
    for file_name in files:
        full_path = join(root, file_name)
        rel_path = relpath(full_path, package_path)
        with open(full_path, 'rb') as package_fh:
            print('Uploading file: {}'.format(rel_path))
            rs.hset(package_key, 'file:' + rel_path, package_fh.read())
