# thoth-build-analyzers
# Copyright(C) 2019, 2020 Marek Cermak
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

"""Build log preprocessing and feature gathering."""

import itertools
import re
import parse

import pandas as pd

from pathlib import Path, PosixPath


from astpath import file_contents_to_xml_ast
from astpath import file_to_xml_ast
from astpath import find_in_ast
from astpath import search

from astpath.search import _tostring_factory
from astpath.search import _query_factory

from thoth.lab import underscore
from thoth.lab import convert

from typing import Iterable, List, Mapping, Tuple, Union

from thoth.build_analyzers.parsing import parse_log

query = _query_factory()
tostring = _tostring_factory()


def build_log_prepare(log: str) -> List[str]:
    """Process raw build log by lines and output list of log messages.

    :returns: List[str], list of log messages
    """
    log_messages = log.splitlines()
    log_messages = [m.strip() for m in log_messages if len(set(m)) > 0]

    return log_messages


def build_log_to_dependency_table(log: str, handlers: List[str] = None) -> pd.DataFrame:
    """Parse raw build log to find software stack and create dependency table."""
    df = pd.io.json.json_normalize(parse_log(log, handlers=handlers), record_path="result")

    if len(df) <= 0:
        return pd.DataFrame()

    df = df._.vstack("from")._.flatten("from", {"package": "source"}).drop(["artifact", "from"], axis=1)

    return df.convert.to_dependency_table(source="source", target="package")


def ast_search_expressions(
    entrypoint: Union[str, PosixPath],
    expressions: Union[str, List[str]] = None,
    glob: str = "**/*.py",
    verbose: bool = False,
):
    """Glob through the source AST and extract AST elements and patterns."""
    if isinstance(entrypoint, str):
        entrypoint = Path(entrypoint)

    expression = "|".join(expressions)

    matching_elements = []
    for module in entrypoint.glob(glob):
        try:
            xml_ast = file_to_xml_ast(module, omit_docstrings=True)

            match = query(xml_ast, expression)
            matching_elements.extend(match)
        except Exception:
            if verbose:
                print(f"Unable to process module '{module}'")

    matching_arguments = list(
        itertools.chain(*[elt.xpath("./ancestor-or-self::*[@s][1]/@s") for elt in matching_elements])
    )

    return matching_elements, matching_arguments


def ast_search_pip(entrypoint: str):
    """Search through the source AST and extract patterns for pip."""
    elements, arguments = ast_search_expressions(
        entrypoint=entrypoint, expressions=["//args/Str[string-length(@s) > 5]"]
    )

    return clean_pattern_dataframe(ast_to_pattern_dataframe(elements, arguments))


def ast_search_pipenv(entrypoint: str):
    """Search through the source AST and extract patterns for pipenv."""
    elements, arguments = ast_search_expressions(
        entrypoint=entrypoint, expressions=["//Str[string-length(@s) > 5]"], glob="**/exceptions.py"
    )

    return clean_pattern_dataframe(ast_to_pattern_dataframe(elements, arguments))


def ast_to_pattern_dataframe(elements: list, patterns: List[str]) -> pd.DataFrame:
    """Convert AST matches into a pattern dataframe.

    :param elements: list of AST elements corresponding to the patterns
    """
    if not len(elements) == len(patterns):
        raise ValueError(
            f"Length of `elements` does not match length of `patterns`, {len(elements)} != {len(patterns)}"
        )
    callers = []
    caller_attrs = []
    method_attrs = []

    parent_tags = []

    for elt in elements:
        parent: str = elt.xpath("name(./parent::*[1])") or None

        parent_tags.append(parent)

        func, = elt.xpath("./ancestor::Call[1]/func[1]") or [None]

        caller = None
        method = None

        if func is not None:
            caller, = func.xpath("./Attribute/*/Name[1]") or [None]
            method, = func.xpath("./Attribute[1]") or [None]

        callers.append(func)
        caller_attrs.append(dict(caller.attrib) if caller is not None else None)
        method_attrs.append(dict(method.attrib) if method is not None else None)

    df = pd.DataFrame(patterns, columns=["pattern"])

    df["parent_tag"] = parent_tags
    df["caller_attrs"] = caller_attrs
    df["method_attrs"] = method_attrs

    caller_records = {"id": "caller"}
    method_records = {"attr": "method"}

    df = pd.concat(
        [
            df,
            df.caller_attrs._.flatten(record_paths=caller_records),
            df.method_attrs._.flatten(record_paths=method_records),
        ],
        axis=1,
        sort=False,
    )

    df = (
        df.drop(["caller_attrs", "method_attrs"], axis=1)
        .drop_duplicates("pattern")
        .dropna(subset=["caller", "method"], how="all")
    )

    return df


def clean_pattern_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the DataFrame by removing unwanted patterns and reformatting."""
    df = df.query(
        """
        ( (caller == "logger") & (method.str.match("info|debug")) ) | \
        ( (caller == "crayons") ) | \
        ( (method.str.match("append")) & (parent_tag.str.match("value(s)?|args")) ) | \
        ( (method.str.match("command|format")) & (parent_tag.str.match("value(s)?")) ) | \
        ( (method.str.match("_update|echo")) )
    """
    )

    # check if any log message contains splitlines (important for future comparison)
    rows = []
    for i, row in df[df.pattern.str.contains("\n")].iterrows():
        for sub_str in reversed(row.pattern.split("\n")):
            new_row = row.copy()
            new_row.pattern = sub_str

            rows.append(new_row)

        df.drop(i, inplace=True)

    df = df.append(rows)

    # simple heuristics, remove all-mighty patterns
    df = (
        df[df.pattern.str.contains(r"[a-zA-Z]{3,}")]
        .sort_values(["caller", "method"], na_position="last", ascending=False)
        .reset_index(drop=True)
    )

    # reformat pattern here to reduce complexity
    df.pattern = df.pattern.apply(reformat)

    return df


PEP_461_FORMAT_CODES = {"c", "b", "a", "r", "s", "d", "i", "o", "u", "x", "X", "e", "E", "f", "F", "g", "G"}


def reformat(string: str) -> str:  # Ignore PyDocStyleBear
    """Reformat format codes by PEP 461 and PEP 3101 to formatting style defined by `parse` library."""

    def _reformat(rest):
        span = re.search(r"(?:(?<=\s)|(?<=\W)|(?<=^))(%\w)|(\{.*?\})(?=\s|\W|$)", rest)
        if span is not None:
            code = span.group(0)

            if code[1:] in PEP_461_FORMAT_CODES or re.fullmatch(r"^\{.*?\}$", code):
                formatted = rest[: span.start()] + "{}"

                yield formatted
                yield from _reformat(rest[span.end() :])  # Ignore PycodestyleBear (E203)
        else:
            yield rest

    formatted = "".join(_reformat(string)).strip()

    return formatted


def reconstruct_string(format_pattern: str, format_string: str) -> str:
    """Attempt to reconstruct string based on a format pattern."""
    format_pattern = reformat(format_pattern)

    # hand-coded heuristic to prevent over-match of == versions
    if format_pattern == "{}=={}":
        return format_string

    try:
        parsed = parse.parse(format_pattern, format_string)
    except Exception:
        parsed = None

    if not parsed:
        return format_string

    reconstructed = ""
    cut = 0
    for span in parsed.spans.values():
        start, end = span
        reconstructed += format_string[cut:start] + "{}"
        cut = end

    reconstructed += format_string[cut:]

    return reconstructed
