#!/usr/bin/env python
# -*- coding: utf-8 -*-
#   thoth-build-analysers
#   Copyright(C) 2018 Christoph Görn
#
#   This program is free software: you can redistribute it and / or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Thoth: Build Analysers API"""

import os
import time
import logging

from flask import Flask
from flask import jsonify
from flask import request
from flask.helpers import make_response

import requests

from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import Histogram
from prometheus_client import core
from prometheus_client import generate_latest

import thoth_build_analysers
from thoth_build_analysers.apis import api
from thoth_build_analysers.configuration import Configuration

DEBUG = bool(os.getenv('DEBUG', False))

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


app = Flask(__name__)
app.config.SWAGGER_UI_JSONEDITOR = True
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
app.logger.setLevel(logging.DEBUG)

api.init_app(app)


@app.route('/readiness')
def api_readiness():
    return jsonify({
        'name': 'Thoth Build Analysers',
        'version': thoth_build_analysers.__version__
    })


@app.route('/liveness')
def api_liveness():
    try:
        response = requests.get(Configuration.KUBERNETES_API_URL,
                                verify=Configuration.KUBERNETES_VERIFY_TLS)
    except requests.exceptions.ConnectionError as e:
        logger.error(e)

        return jsonify({
            'name': 'Thoth Build Analysers',
            'version': thoth_build_analysers.__version__,
            'status': 'I am not running within an OpenShift cluster... nevertheless my services are available!'
        }), 503

    return jsonify({
        'name': 'Thoth Build Analysers',
        'version': thoth_build_analysers.__version__
    })


@app.route('/schema')
def print_api_schema():
    return jsonify(api.__schema__)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=DEBUG)
