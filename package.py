import json
import logging
import os
import shutil
from time import time
from zipfile import ZipFile, BadZipfile

from os.path import join as path_join, getmtime

import collections
import requests
import yaml

import task_queue
from tuples import Package
from workdir import internal_path


class PackageLoadError(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def prune_unused_packages():
    packages_dir = internal_path('packages')

    # if package cache doesn't exist yet then we don't care
    if not os.path.isdir(packages_dir):
        return

    for dir in os.listdir(packages_dir):
        path = path_join(packages_dir, dir)

        if getmtime(path) + 60*60 < time():
            logging.info('Removing unused package: {}'.format(dir))
            shutil.rmtree(path)


def download_package_from_url(url, dest):
    logging.info('Attempting to download missing package from: ' + url)
    tmp_path = internal_path("work/dl_package.zip")

    try:
        req = requests.get(url, stream=True, timeout=10)

        if req.status_code == 200:
            with open(tmp_path, 'wb') as tmp_file:
                req.raw.decode_content = True
                shutil.copyfileobj(req.raw, tmp_file)
        else:
            raise PackageLoadError('Package download failed, server said: {} {}'.format(req.status_code, req.reason))
    except (RuntimeError, IOError) as e:
        raise PackageLoadError('Package download failed due to an error') from e

    logging.info('Extracting package...')
    try:
        with ZipFile(tmp_path, "r") as z:
            z.extractall(dest)
    except BadZipfile as e:
        raise PackageLoadError('Malformed package zip file') from e

    os.remove(tmp_path)


def get_package(name, version, url=None):
    """
    Fetch package with matching name and version.
    If it is not possible, package will be fetched from given url.
    """
    prune_unused_packages()

    file_name = name + "-v" + str(version)
    path = internal_path(os.path.join('packages', file_name))

    if not os.path.isdir(path):
        if url:
            download_package_from_url(url, path)
        else:
            task_queue.download_package(name, version, path)
    else:
        os.utime(path, None)

    yml_file = os.path.join(path, 'config.yml')
    json_file = os.path.join(path, 'config.json')

    if os.path.exists(yml_file):
        config_format = 'yml'
        config_fname = yml_file
    elif os.path.exists(json_file):
        config_format = 'json'
        config_fname = json_file
    else:
        raise PackageLoadError('No configuration file found inside package, tried config.yml and config.json.')

    config = None

    with open(os.path.join(path, config_fname), 'r') as config_file:
        try:
            if config_format == 'yml':
                config = yaml.load(config_file)
            elif config_format == 'json':
                config = json.load(config_file)
            else:
                raise RuntimeError('Invalid value provided in `config_format`.')
        except (IOError, ValueError, yaml.YAMLError, json.JSONDecodeError) as e:
            raise PackageLoadError('Failed to load package config.yml') from e

    return Package(file_name, path, raw_config=config, config=None)


def deep_update(source, overrides):
    # from http://stackoverflow.com/a/30655448

    for key, value in overrides.items():
        if isinstance(value, collections.Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]

    return source


def parse_config(pack, config_name=None):
    try:
        conf = pack.raw_config['configs']['_base']
    except KeyError:
        conf = {}

    if config_name:
        try:
            deep_update(conf, pack.raw_config['configs'][config_name])
        except KeyError:
            pass

    return Package(pack.file_name, pack.path, pack.raw_config, conf)
