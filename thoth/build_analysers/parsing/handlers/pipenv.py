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

_RE_ESCAPE_SEQ = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
_RE_FOUND_CANDIDATE = re.compile(
    r'\s*found candidate (?P<package>[+a-zA-Z_\-.():/0-9>=<;,"]+)'
    r"\s*\(constraint was (?P<constraint>[a-zA-Z_\-.:/0-9>=<~;, ]+)\)$"
)


@attr.s
class Pipenv(HandlerBase):
    """Handle extracting packages from build logs - pipenv installer."""

    def run(self, input_text: str) -> list:
        """Find and parse installed packages and their versions from a build log."""
        result = []
        lines = input_text.split("\n")
        for line in map(self._remove_escape_seq, lines):
            match_result = _RE_FOUND_CANDIDATE.fullmatch(line)
            if match_result:
                package, constraint = match_result.groups()
                dependency = self._parse_package(package, constraint)
                dependency["from"] = [{"package": None, "version_specified:": None}]  # TODO: get the parent packages
                dependency["artifact"] = None
                result.append(dependency)
                continue

        return result

    @staticmethod
    def _remove_escape_seq(line: str) -> str:
        """Remove escape characters that can occur on stdout (e.g. colored output)."""
        return _RE_ESCAPE_SEQ.sub("", line)

    @classmethod
    def _parse_package(cls, package_specifier: str, constraint: str = "<any>") -> dict:
        """Parse packages and return them in a dictionary."""
        result = []

        parsed_package = cls._do_parse_package(package_specifier)
        result = {
            "package": parsed_package[0],
            "version_specified": constraint,
            "version_installed": parsed_package[1],
            "already_satisfied": None,
        }

        return result or None

    @staticmethod
    def _do_parse_package(package_specifier: str) -> typing.Tuple[str, typing.Optional[str]]:
        """Parse packages from a report line.

        Parsing the packages and return them in a
        tuple describing also version, version specifier.
        """
        if package_specifier.startswith("git+"):
            _LOG.warning(
                "Detected installing a Python package from a git repository: %r", package_specifier
            )  # Ignore PycodestyleBear (E501)
            package_name = package_specifier
            version = "master"

            # Try to find branch or commit specification.
            split_result = package_specifier.rsplit("@", maxsplit=1)
            if len(split_result) == 2:
                package_name = split_result[0]
                version = split_result[1]

            return package_name, version

        # See https://www.python.org/dev/peps/pep-0440/#version-specifiers for
        # all possible values.  # Ignore PycodestyleBear (E501)
        version_start_idx = None
        for ver_spec in ("~=", "!=", "===", "==", "<=", ">=", ">", "<"):
            try:
                found_idx = package_specifier.index(ver_spec)
                if version_start_idx is None or found_idx < version_start_idx:
                    version_start_idx = found_idx
            except ValueError:
                pass

        if version_start_idx:
            # Ignore PycodestyleBear (E501)
            return package_specifier[:version_start_idx], package_specifier[version_start_idx:]

        return package_specifier, None


HandlerBase.register(Pipenv)
