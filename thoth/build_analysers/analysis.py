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
# along with this program. If not, see <http://www.gnu.org/licenses/>

"""Build log analysis logic."""

import json
import re
import string
import textwrap

import itertools

import networkx as nx

import numpy as np
import pandas as pd

from collections import Counter
from pathlib import Path

from thoth.build_analysers.preprocessing import build_log_prepare
from thoth.build_analysers.preprocessing import build_log_to_dependency_table
from thoth.build_analysers.preprocessing import reconstruct_string

from thoth.lab.graph import get_root

from typing import Iterable, List, Tuple, Union


THRESHOLDS = {"WARNING": 0.3, "ERROR": 0.5}

_HERE = Path(__file__).parent
PIP_PATTERNS_FPATH = Path(_HERE / "resources/patterns.pip.csv")
PIPENV_PATTERNS_FPATH = Path(_HERE / "resources/patterns.pipenv.csv")

REPORT_TEMPLATE = string.Template(
    """
Build breaker:

$build_breaker

Probable reason:

    $reason

Candidates:

$candidates
"""
)


# TODO: Implement binary classifier to distinguish pip / pipenv logs
def retrieve_build_log_patterns(log_messages: List[str]) -> Tuple[str, pd.DataFrame]:
    """Retrieve build log patterns based on the given log file.

    This function detects whether the log file has been produced
    by 'pip' or 'pipenv' and retrieves appropriate resources.
    """
    patterns_pip = pd.read_csv(PIP_PATTERNS_FPATH).pattern
    patterns_pipenv = pd.read_csv(PIPENV_PATTERNS_FPATH).pattern

    # create BoW for each and compare it to the log file
    bow_log = Counter(itertools.chain(*[s.strip("{}").split() for s in log_messages]))

    # definite checks
    pipenv_indicators = ["pipenv", "pipfile", "pipfile.lock", "locking", "virtualenv", "candidates"]
    if any([re.search(p, w, re.IGNORECASE) for w in bow_log for p in pipenv_indicators]):
        return "pipenv", patterns_pipenv

    # pip first-line check
    pip_indicators = [r"Processing (.+)", r"You should consider upgrading via the '(.+)' command."]
    if any(
        [re.fullmatch(p, msg, re.IGNORECASE) for msg in [log_messages[0], log_messages[-1]] for p in pip_indicators]
    ):
        return "pip", patterns_pip

    # otherwise try to determine using BoW scores

    bow_pip = Counter(itertools.chain(*[s.strip("{}").split() for s in patterns_pip]))
    s = sum(bow_pip.values())
    bow_pip = {k: v / s for k, v in bow_pip.items()}

    bow_pipenv = Counter(itertools.chain(*[s.strip("{}").split() for s in patterns_pipenv]))
    s = sum(bow_pipenv.values())
    bow_pipenv = {k: v / s for k, v in bow_pipenv.items()}

    # compare scores
    score = {"pip": 0, "pipenv": 0}
    for word, count in bow_log.items():
        score["pip"] += bow_pip.get(word, 0) * count
        score["pipenv"] += bow_pipenv.get(word, 0) * count

    return ("pip", patterns_pip) if score["pip"] >= score["pipenv"] else ("pipenv", patterns_pipenv)


def build_breaker_report(log: Union[str, pd.DataFrame], *, top: int = 5, colorize: bool = False) -> dict:
    """Analyze raw build log and produce a report.

    :param log: Union[str, pd.DataFrame], raw build log to be analyzed or result of `build_log_analyze`
    :param top: int, maximum number of candidates to report
    :param colorize: bool, whether to map scores to colors (only valid if `log` is instance of str)

    :returns: dict of the following schema:
        {
            "build_breaker": {
                "already_satisfied": bool,
                "source": str,
                "target": str,
                "version_installed": str,
                "version_specified": str
            },
            "reason": {
                "ln": str,
                "msg" : str
            },
            "candidates": List[dict#reason]
        }
    """
    df_log = log
    if isinstance(log, str):
        df_log = build_breaker_analyze(log, colorize=colorize)

    build_breaker_info = dict()
    """Dictionary holding build breaker attributs."""
    reason = dict()
    """Probable reason of the failure."""
    candidates = []
    """List of top *k* candidates to cause the build failure."""

    errors = df_log.query("label == 'ERROR'")

    if len(errors) >= 1:
        dep_table = build_log_to_dependency_table(log)
        dep_table.target.fillna("", inplace=True)
        # make sure the packages are unique, keep only the latest
        dep_table.drop_duplicates("target", keep="last", inplace=True)

        if len(dep_table) >= 1:
            errors = errors.query("msg.str.contains('|'.join(@dep_table.target))", engine="python")
            build_breaker_package_name: str = build_breaker_identify(dep_table, errors.msg)

            if build_breaker_package_name:
                build_breaker_info, = dep_table.query(f"target == '{build_breaker_package_name}'").to_dict(
                    orient="records"
                )
                reason = next(
                    errors.query("msg.str.contains(@build_breaker_package_name)", engine="python").msg[::-1].iteritems()
                )

            elif len(errors) >= 1:
                reason = next(errors.sort_values("score").msg[::-1].iteritems())

        else:
            reason = next(errors.sort_values("score").msg[::-1].iteritems())

        candidates = list(map(lambda t: dict(zip(["ln", "msg"], t)), errors.sort_values("score").msg[::-1].iteritems()))

    return {"build_breaker": build_breaker_info, "reason": dict(zip(["ln", "msg"], reason)), "candidates": candidates}


def build_breaker_format_report(report: dict, indentation_level: int = 4) -> str:
    """Format the report produced by the `build_breaker_report` function into string."""
    if not report["candidates"]:
        return "No build breaker candidates identified."

    build_breaker_info_str = json.dumps(report["build_breaker"], indent=indentation_level, sort_keys=True)
    build_breaker_info_str = textwrap.indent(build_breaker_info_str, " " * indentation_level)

    def _format_reason(ln: str, reason: str):
        return f"{ln}: {reason}"

    build_breaker_candidates_str = json.dumps(
        [_format_reason(*c.values()) for c in report["candidates"]], indent=indentation_level, sort_keys=False
    )
    build_breaker_candidates_str = textwrap.indent(build_breaker_candidates_str, " " * indentation_level)

    return REPORT_TEMPLATE.safe_substitute(
        build_breaker=build_breaker_info_str,
        reason=_format_reason(*report["reason"].values()),
        candidates=build_breaker_candidates_str,
    )


def build_breaker_predict(
    log_messages: Iterable[str], patterns: Iterable[str], reverse_scores: bool = False
) -> np.ndarray:
    """Predict scores and candidate pattern indices for each log message in `log`.

    The method compares each message in `log` with a candidate pattern in `patterns`
    and outputs similarity score based on a BoW approach penalized by the length of
    the log message.

    :param logs: Iterable[str], An iterable of log messages
    :param patterns: Iterable[str], patterns to compare to log messages
    :returns: np.ndarray of shape (2, n), n is length of logs

        dimensions represent message similarity score and candidate pattern index respectively
    """
    print(f"Length of the log file: {len(log_messages)}")

    winner_scores, winner_indices = [-1] * len(log_messages), [None] * len(log_messages)
    for msg_idx, msg in enumerate(log_messages):
        winner_score, winner_idx = 0, None

        for pt_idx, pt in enumerate(patterns):
            score, match = simple_bow_similarity_with_replacement(pt, msg)

            if np.less(winner_score, score):
                winner_score = score
                winner_idx = pt_idx

            if np.isclose(score, 1.0, rtol=1e-02, atol=1e-03):
                break

        winner_scores[msg_idx] = winner_score
        winner_indices[msg_idx] = winner_idx

    scores = np.array(winner_scores)

    if reverse_scores:  # reverse the scores
        scores = 1 / (scores * np.max(1 / scores))

    return np.vstack([scores, winner_indices])


def build_breaker_analyze(log: str, *, colorize: bool = True):
    """Analyze raw build log."""
    log_messages = build_log_prepare(log)

    which, patterns = retrieve_build_log_patterns(log_messages)

    scores, candidate_indices = build_breaker_predict(log_messages, patterns, which == "pip")

    df_log = pd.DataFrame(list(zip(log_messages, scores)), columns=["msg", "score"])
    df_log["pattern"] = [patterns[int(i)] if i is not None else None for i in candidate_indices]

    threshold_e = THRESHOLDS["ERROR"]
    threshold_w = THRESHOLDS["WARNING"]

    warnings = df_log.query("score > @threshold_w", engine="python")
    errors = warnings.query("score > @threshold_e", engine="python")

    df_log["label"] = "INFO"
    df_log.loc[warnings.index, "label"] = "WARNING"
    df_log.loc[errors.index, "label"] = "ERROR"

    if colorize:
        try:
            from thoth.lab.utils import scale_colour_continuous

            df_log["colour"] = scale_colour_continuous(df_log.score, norm=False)
        except ImportError:
            # TODO: logger.warn, using discrete scale based on labels
            df_log["colour"] = df_log.label.map({"INFO": "green", "WARNING": "yellow", "ERROR": "red"})

    return df_log


def build_breaker_identify(dep_table: pd.DataFrame, error_messages: List[str]) -> Union[str, None]:
    """Identify build breaker package name."""
    g = dep_table.convert.to_dependency_graph()

    packages = []
    for msg in error_messages:
        packages.extend(p for p in dep_table.target if re.search(p, msg) and g.has_node(p))

    return packages[-1] if packages else None


def simple_bow_similarity(matcher: str, matchee: str) -> Tuple[float, List[str]]:
    """Compare two sentences and count number of common words.

    :returns: float, score representing sentence similarity
    """
    x = set(matchee.strip().lower().split())
    y = set(matcher.strip().lower().split())

    if len(y) <= 0:
        return 0, []

    match = x & y

    penalty = 1 + np.log10((len(x) - len(y)) ** 2 + 1)
    score = len(match) / (len(y) * penalty)

    return score, list(match)


def simple_bow_similarity_with_replacement(matcher: str, matchee: str, reformat=False) -> Tuple[float, List[str]]:
    """Compare two strings while respecting matcher string formatting syntax.

    This function checks for string formatted syntax in the `matcher`
    pattern and replaces it with regexp based syntax. Then size of the span
    is computed and transformed into similarity score.

    :returns: float, score representing sentence similarity
    """
    score = 0
    match = []

    if reformat:
        matcher = reformat(matcher)

    formatted = reconstruct_string(matcher, matchee.strip())

    if formatted:
        score, match = simple_bow_similarity(matcher, formatted)

    return score, list(match)


def get_succesfully_installed_packages(dep_table: pd.DataFrame, build_breaker: str = None):
    """Traverse dependency table in DFS manner and output installed packages."""
    g = dep_table.convert.to_dependency_graph()
    root = get_root(g)

    failed_branch = get_failed_branch(dep_table, build_breaker)

    successfully_installed = set()
    for node in nx.dfs_preorder_nodes(g, root):
        if re.match(re.escape(node), build_breaker or "", re.IGNORECASE):
            break
        successfully_installed.add(node)

    successfully_installed = successfully_installed.difference(set(failed_branch))

    return successfully_installed


def get_failed_branch(dep_table: pd.DataFrame, build_breaker: str):
    """Traverse dependency table in DFS manner and output installed packages."""
    g = dep_table.convert.to_dependency_graph()
    root = get_root(g)

    failed_branch = []

    if build_breaker:
        failed_branch = nx.shortest_path(g, root, build_breaker)[:-1]

    return failed_branch
