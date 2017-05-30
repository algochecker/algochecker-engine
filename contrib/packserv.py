#!/usr/bin/env python3
import json
import os
import shutil

from flask import Flask, send_from_directory, abort, request, jsonify

app = Flask(__name__)

package_path = 'package'
cache_path = 'package/_cache'

shutil.rmtree(cache_path, ignore_errors=True)
os.mkdir(cache_path)


@app.route("/")
def hello():
    return jsonify({"message": "Hello, this is an exemplary package server."})


@app.route("/repo/")
def repo_index():
    # include only directories which contain config.json
    def filter_func(name):
        return os.path.exists(os.path.join(package_path, name, 'config.json'))

    # append ".zip" suffix to the directory names
    packages = [name + '.zip' for name in list(filter(filter_func, os.listdir(package_path)))]

    return jsonify({"packages": packages})


@app.route("/repo/<name>")
def repo(name):
    name = os.path.basename(name)
    pack_name = os.path.splitext(name)[0]

    print("Fetching zip archive for: {}".format(pack_name))

    if not os.path.exists(os.path.join(cache_path, name)):
        print("Creating zip package for cache")

        zip_name = os.path.join(cache_path, pack_name)
        dir_name = os.path.join(package_path, pack_name)

        if not os.path.exists(dir_name):
            print("Such package was not found")
            abort(404)

        shutil.make_archive(zip_name, 'zip', dir_name)

    return send_from_directory(cache_path, name)


@app.route("/report", methods=['POST'])
def report():
    data = request.get_json()

    if not data or 'uuid' not in data:
        print("Received malformed report")
        abort(400)

    print("Received report for: {}".format(data['uuid']))
    print(json.dumps(data, indent=4))

    return jsonify({"uuid": data['uuid']})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
