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

from werkzeug.exceptions import BadRequest, ServiceUnavailable  # pragma: no cover
from flask import request  # pragma: no cover
from flask_restplus import Namespace, Resource, fields  # pragma: no cover

ns = Namespace('openshift', description='OpenShift Builds')  # pragma: no cover

analyse_request = ns.model('AnalyseRequest', {
    'build_id': fields.String(required=True, example='goern-dev-thoth/user-api-1', description='ID of the OpenShift Build to be analyserd'),
})  # pragma: no cover

analyse_request_response = ns.model('AnalyseRequestResponse', {
    'id': fields.String(required=True, readOnly=True, example='7b63d226-1d6c-11e8-968f-54ee7504b46f', description='The Analyse unique identifier')
})  # pragma: no cover

PHASE = ['pending', 'running', 'succeeded', 'failed', 'unknown']  # pragma: no cover


@ns.route('/')
class AnalysisList(Resource):
    """Lists of all currently known Build Analysis"""
    @ns.doc('list_analysis')
    @ns.response(503, 'Service we depend on is not available')
    def get(self):
        """List all Analysis"""

        return []
