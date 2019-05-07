# thoth-build-analysers
# Copyright(C) 2018, 2019 Marek Cermak
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Parse packages installed using pipenv."""

import logging
import re
import typing

import attr

from .base import HandlerBase

_LOG = logging.getLogger("thoth.build_analysers.parsing.handlers.pipenv")


@attr.s
class Pipenv(HandlerBase):
    """Handle extracting packages from build logs - pipenv installer."""

    def run(self, input_text: str) -> list:
        """Find and parse installed packages and their versions from a build log."""  # Ignore PycodestyleBear (E501)
        result = []

        return result


HandlerBase.register(Pipenv)
