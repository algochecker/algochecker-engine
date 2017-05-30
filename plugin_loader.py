import logging
import os
from os.path import join

import yaml

_plugins = {}


class PluginLoaderError(RuntimeError):
    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)


def load(namespace, dir):
    dirs = os.listdir(dir)

    if namespace not in _plugins:
        _plugins[namespace] = {}

    for file in dirs:
        if file != '__init__.py' and file.endswith(".py"):
            plugin_name = os.path.splitext(file)[0]
            module_name = '{}.{}'.format(namespace, plugin_name)
            module = __import__(module_name, globals(), locals(), ['*'])

            if hasattr(module, "__plugin__"):
                _plugins[namespace][plugin_name] = module

    return list(_plugins[namespace].keys())


def load_namespace(namespace):
    loaded = load(namespace, '{}/'.format(namespace))
    loaded_str = ', '.join(loaded)
    logging.info('Loaded {}: {}'.format(namespace, loaded_str))


def get(namespace, plugin_name, custom_options=None):
    if namespace not in _plugins:
        raise PluginLoaderError('Namespace not loaded: "{}"'.format(namespace))

    if plugin_name not in _plugins[namespace]:
        raise PluginLoaderError('No such plugin: "{}" in namespace "{}"'.format(plugin_name, namespace))

    if custom_options:
        custom_config = get_custom_config(namespace, plugin_name, custom_options)
    else:
        custom_config = None

    return _plugins[namespace][plugin_name], custom_config


def get_default_config(namespace, plugin_name):
    config_name = join(namespace, plugin_name + '.yml')

    with open(config_name, 'r') as config_file:
        try:
            return yaml.load(config_file)
        except (IOError, OSError, yaml.YAMLError) as e:
            raise PluginLoaderError('Failed to load default plugin configuration file "{}"'.format(config_name)) from e


def get_custom_config(namespace, plugin_name, custom_options):
    config = get_default_config(namespace, plugin_name)
    config.update(custom_options)

    return config


def get_all(namespace):
    return dict(_plugins[namespace])
