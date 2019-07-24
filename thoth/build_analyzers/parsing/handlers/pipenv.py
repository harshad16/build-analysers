# thoth-build-analyzers
# Copyright(C) 2019 Marek Cermak
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

_LOG = logging.getLogger("thoth.build_analyzers.parsing.handlers.pipenv")

_RE_ESCAPE_SEQ = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
_RE_FOUND_CANDIDATE = re.compile(
    r'\s*found candidate (?P<package>[+a-zA-Z_\-.():/0-9>=~<;,"]+)'
    r"\s*\(constraint was (?P<constraint>[a-zA-Z_\-.:/0-9>=~<;, ]+)\)$"
)
_RE_COULD_NOT_FOUND = re.compile(
    r"(.*) Could not find a version that matches "
    r'(?P<package>[+a-zA-Z\-_]+)(?P<constraint>[+a-zA_Z\-.:/0-9>=~<;,"]+)'
)
_RE_REQUIRES = re.compile(
    r'\s*(?P<package>[+a-zA-Z_\-.():/0-9>=<;,"]+)' r'\s*requires (?P<dependencies>[+a-zA-Z_\-.():/0-9>=<;, "]+)'
)


@attr.s
class Pipenv(HandlerBase):
    """Handle extracting packages from build logs - pipenv installer."""

    def run(self, input_text: str) -> list:
        """Find and parse installed packages and their versions from a build log."""
        result = []

        seen = set()
        lines = input_text.split("\n")
        for line in map(self._remove_escape_seq, lines):
            if line in seen:
                continue

            seen.add(line)  # we want to skip duplicite lines

            for pattern in [_RE_FOUND_CANDIDATE, _RE_REQUIRES, _RE_COULD_NOT_FOUND]:
                match_result = pattern.fullmatch(line)
                if match_result:
                    package = match_result.group("package")
                    if "constraint" in match_result.groupdict():
                        constraint = match_result.group("constraint")
                        result.append(self._parse_package(package, constraint=constraint))
                    elif "dependencies" in match_result.groupdict():
                        dependencies = match_result.group("dependencies")
                        result.extend(self._parse_secondary_dependency(package, dependencies))
                    else:
                        result.append(self._parse_package(package))
                    break

        return result

    @staticmethod
    def _remove_escape_seq(line: str) -> str:
        """Remove escape characters that can occur on stdout (e.g. colored output)."""
        return _RE_ESCAPE_SEQ.sub("", line)

    @classmethod
    def _parse_package(
        cls,
        package_specifier: str,
        parents: typing.List[dict] = None,
        constraint: str = "<any>",
        specified: bool = False,
    ) -> dict:
        """Parse packages and return them in a dictionary."""
        package, version = cls._do_parse_package(package_specifier)
        result = {
            "package": package,
            "from": parents or [{"package": None, "version_specified": None}],
            "version_specified": version if specified else constraint,
            "version_installed": None,
            "already_satisfied": None,
            "artifact": None,
        }

        return result

    @classmethod
    def _parse_secondary_dependency(cls, package_specifier: str, dependencies: str) -> list:
        """Parse package with secondary dependencies and return them in a list."""
        parent = cls._parse_package(package_specifier)
        result = [parent]

        parent_package_specifier = {k: parent[k] for k in ["package", "version_installed"]}

        for dep in dependencies.split(","):
            if dep == "-":
                continue
            result.append(cls._parse_package(dep, parents=[parent_package_specifier], specified=True))

        return result

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
