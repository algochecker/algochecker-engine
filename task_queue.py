import logging
import json
from os import makedirs
from time import sleep, time
from re import match
from os.path import join as path_join, abspath as path_abspath
from uuid import uuid4

from redis import Redis, ConnectionError
from shutil import rmtree

from worker_conf import REDIS_CONF, REDIS_QUEUE_KEY, INSTANCE_NAME

"""
Global instance of Redis client.
"""
rs_cli = Redis(**REDIS_CONF)
current_instance_uuid = uuid4()
interrupted = False
interrupt_count = 0


def safe_ping():
    """
    Try to send PING command to Redis and return True in case of success.
    """
    try:
        rs_cli.ping()
    except ConnectionError:
        logging.exception("Failed to issue PING command to Redis.")
        return False

    return True


def _retry_ping():
    """
    Helper method to be called when we loose the connection. Will try to reconnect to Redis
    in 5 second intervals until it succeeds.
    """
    logging.exception('Operation failed due to a connection problem (Redis).')

    while not safe_ping() and not interrupted:
        logging.error('Retrying in 5 seconds...')
        sleep(5)

    if not interrupted:
        logging.info('Connectivity restored, getting back to operation...')


def _compare_instance_key(redis_value, exception_text):
    if redis_value.decode('utf-8') != str(current_instance_uuid):
        raise RuntimeError('Instance lock was stolen by another worker instance. ' +
                           'It looks like two workers are running on the same instance name. ' +
                           exception_text)


def set_instance_lock(fail_on_mismatch=True):
    instance_lock_key = "instance_lock:{}".format(INSTANCE_NAME)

    if fail_on_mismatch:
        prev_uuid = rs_cli.get(instance_lock_key)
        _compare_instance_key(prev_uuid, 'Failed on pre-check before acquiring lock.')

    prev_uuid = rs_cli.getset(instance_lock_key, str(current_instance_uuid))

    if fail_on_mismatch:
        _compare_instance_key(prev_uuid, 'Failed after acquiring lock.')


def send_beat(state, uuid=None):
    # TODO enforce some hard limit for a single test duration
    data = {"state": state, "local_time_ms": int(time() * 1000), "current_uuid": uuid}
    rs_cli.setex(REDIS_QUEUE_KEY + ":alive_workers:{}".format(INSTANCE_NAME), json.dumps(data), 120)


def report_status(uuid, status, progress):
    """
    Report partial status to Redis, according to:
    Protocol: checking status of running job (wiki page)
    """
    try:
        send_beat('checking', uuid)
        data = json.dumps({'status': status, 'progress': progress}).encode('utf-8')
        rs_cli.setex('status:{}'.format(uuid), data, 60)
    except ConnectionError:
        logging.warning('Failed to report partial status due to the problem with Redis connectivity.', exc_info=True)


def fetch_submission():
    """
    Fetch submission from the queue, according to:
    Protocol: uploading submission (wiki page)
    """
    data = None

    while not data and not interrupted:
        try:
            set_instance_lock()
            send_beat('idle')
            keys = [REDIS_QUEUE_KEY + ":high", REDIS_QUEUE_KEY + ":medium", REDIS_QUEUE_KEY + ":low"]
            data = rs_cli.blpop(keys, timeout=5)
        except ConnectionError:
            _retry_ping()

    if interrupted:
        raise KeyboardInterrupt()

    data_decoded = json.loads(data[1].decode('utf-8'))
    s_uuid = str(data_decoded['uuid'])
    queue_key = "{}:order".format(data[0].decode('utf-8'))

    if not rs_cli.zrem(queue_key, s_uuid):
        logging.warning('Failed to remove {} key from {}'.format(s_uuid, queue_key))

    return data_decoded


def download_files(main_key, dest_path):
    """
    Download files stored in Redis key called `main_key` and extract
    them into dest_path.
    """
    try:
        rmtree(dest_path, ignore_errors=True)
        sub_keys = rs_cli.hkeys(main_key)

        if not len(sub_keys):
            logging.error('Failed to download files from Redis, key does not exist.')
            raise KeyError(main_key)

        for key in sub_keys:
            key = key.decode('utf-8')
            m = match(r'^file:(.+)$', key)

            if m:
                path = path_join(dest_path, m.group(1))
                # in case of directories, if path is eg. foo/bar/code.cpp
                try:
                    makedirs(path_abspath(path_join(path, '..')))
                except FileExistsError:
                    pass

                with open(path, 'wb') as source_file:
                    source_file.write(rs_cli.hget(main_key, key))

        if not rs_cli.hget(main_key, 'options:persistent'):
            rs_cli.delete(main_key)
    except ConnectionError as e:
        err = 'Failed to download files from Redis. Connection problem. {}'.format(e.message)
        logging.error(err)
        raise RuntimeError(err)


def download_package(name, version, dest_path):
    """
    Download exercise package, using protocol similar to download_project.
    """
    main_key = 'package:{}:{}'.format(name, version)
    logging.info('Attempting to download missing package from Redis hash.')
    return download_files(main_key, dest_path)


def download_project(uuid, dest_path):
    """
    Download submission project files, according to:
    Protocol: uploading submission (wiki page)
    """
    main_key = 'submission:{}'.format(uuid)
    return download_files(main_key, dest_path)


def upload_test_output(uuid, test_name, output_data, visibility):
    """
    Uploads the output of the program for given test, so the frontend will be able
    to store it or make further analysis. The key will expire 120 seconds after last change.
    """
    evaluation_key = 'evaluation:{}'.format(uuid)

    rs_cli.hset(evaluation_key, 'test_output:{}'.format(test_name), output_data)
    rs_cli.hset(evaluation_key, 'test_output_visibility:{}'.format(test_name), visibility)
    # TODO this should ba handled differently(?)
    rs_cli.expire(evaluation_key, 120)


def send_report_async(res):
    """
    Asynchronous reporting of final processing result. Turns `res` into JSON string and then
    adds to the bottom (right) of the report_queue.
    """
    out = json.dumps(res._asdict(), indent=4, sort_keys=True)
    logging.info('Sending final report:\n%s', out)
    count = rs_cli.publish("reports", out.encode('utf-8'))

    if not count:
        logging.error('Final report was published but no clients had received this message.')
        return False
    else:
        logging.info('Final result was published successfully (recipients: %d).', count)

    return True
