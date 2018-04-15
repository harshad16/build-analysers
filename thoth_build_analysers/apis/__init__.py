from flask_restplus import Api

import thoth_build_analysers
from .openshift import ns as openshift_builds_v0alpha0

api = Api(version=thoth_build_analysers.__version__, title='Thoth: Build Analysers API',
          description='...', doc='/openapi/')

api.add_namespace(openshift_builds_v0alpha0, path='/api/v0alpha0/openshift')
