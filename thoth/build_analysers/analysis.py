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

import re
import string

import itertools

import numpy as np
import pandas as pd

from collections import Counter
from pathlib import Path

from thoth.build_analysers.preprocessing import build_log_prepare
from thoth.build_analysers.preprocessing import reconstruct_string

from typing import Iterable, Union

THRESHOLDS = {
    'WARNING': 0.3,
    'ERROR'  : 0.5
}

_HERE = Path(__file__).parent
PIP_PATTERNS_FPATH = Path(_HERE / "resources/patterns.pip.csv")
PIPENV_PATTERNS_FPATH = Path(_HERE / "resources/patterns.pipenv.csv")

REPORT_TEMPLATE = string.Template("""
Build breaker:

$info     

Probable reason:

    $ln: $reason
""")


def retrieve_build_log_patterns(log_messages: List[str]) -> Tuple[str, pd.DataFrame]:
    """Retrieve build log patterns based on the given log file.
    
    This function detects whether the log file has been produced
    by 'pip' or 'pipenv' and retrieves appropriate resources.
    """
    df_pip = pd.read_csv(PIP_PATTERNS_FPATH)
    df_pipenv = pd.read_csv(PIPENV_PATTERNS_FPATH)
    
    # create BoW for each and compare it to the log file
    bow_log = Counter(
        itertools.chain(*[s.strip("{}").split() for s in log_messages])
    )
    
    # definite checks
    pipenv_patterns = [
        'pipenv', 'pipfile', 'pipfile.lock', 'locking', 'virtualenv', 'candidates',
    ]
    if any([
        re.search(p, w) for w in bow_log
        for p in pipenv_patterns
    ]):
        return 'pipenv', df_pipenv
    
    # otherwise try to determine using BoW scores
    
    bow_pip = Counter(itertools.chain(*[s.strip("{}").split() for s in df_pip.pattern]))
    s = sum(bow_pip.values())
    bow_pip = {k: v / s for k, v in bow_pip.items()}
    
    bow_pipenv = Counter(itertools.chain(*[s.strip("{}").split() for s in df_pipenv.pattern]))
    s = sum(bow_pipenv.values())
    bow_pipenv = {k: v / s for k, v in bow_pipenv.items()}
    
    # compare scores
    score = {'pip': 0, 'pipenv': 0}
    for word, count in bow_log.items():
        score['pip'] += bow_pip.get(word, 0) * count
        score['pipenv'] += bow_pipenv.get(word, 0) * count
    
    return ('pip', df_pip) if score['pip'] >= score['pipenv'] else ('pipenv', df_pipenv)


def build_breaker_report(
    log: str,
    *,
    colorize: bool = True,
    indentation_level: int = 4
) -> dict:
    """Analyze raw build log and produce a report."""
    df_log = build_breaker_analyze(log)
    
    dep_table = build_log_to_dependency_table(log)
    
    errors = df_log.query("label == 'ERROR' & msg.str.contains('|'.join(@dep_table.target))")
    build_breaker = build_breaker_identify(dep_table, errors.msg)

    if build_breaker:
        build_breaker_info = dep_table.query(f"target == '{build_breaker}'")

        line_no, reason = next(
            df_log.query("msg.str.contains(@build_breaker)").msg[::-1].iteritems())
        
        build_breaker_info_str = json.dumps(
            build_breaker_info.to_dict(orient='records')[0], indent=indentation_level, sort_keys=True
        )
        build_breaker_info_str = textwrap.indent(
            build_breaker_info_str, ' ' * indentation_level
        )

        return REPORT_TEMPLATE.safe_substitute(info=build_breaker_info_str, ln=line_no, reason=reason)

    else:
        return "No build breaker identified."

def build_breaker_identify(dep_table: pd.DataFrame, error_messages: List[str]) -> Union[str, None]:
    """Identify build breaker package name."""
    g = dep_table.convert.to_dependency_graph()
    
    packages = []
    for msg in error_messages:
        packages.extend(
            p for p in dep_table.target
            if re.search(p, msg) and g.has_node(p)
        )

    return packages[-1] if packages else None


def build_breaker_predict(log_messages: Iterable[str], patterns: Iterable[str], reverse_scores: bool = False) -> np.ndarray:
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

        winner_scores[msg_idx]  = winner_score
        winner_indices[msg_idx] = winner_idx
        
    scores = np.array(winner_scores)

    if reverse_scores:  # reverse the scores
        scores = 1 / ( scores * np.max(1 / scores) )
    
    return np.vstack([winner_scores, winner_indices])


def build_breaker_analyze(log: str, *, colorize: bool = True):
    """Analyze raw build log."""
    log_messages = build_log_prepare(log)
    
    which, patterns = retrieve_build_log_patterns(log_messages)
    
    scores, candidate_indices = build_breaker_predict(log_messages, patterns, which == 'pip')
    
    df_log = pd.DataFrame(zip(log_messages, scores), columns=['msg', 'score'])
    df_log['pattern'] = [patterns[int(i)] if i is not None else None for i in candidate_indices]
    
    threshold_e = THRESHOLDS['ERROR']
    threshold_w = THRESHOLDS['WARNING']
    
    warnings = df_log.query("score > @threshold_w")
    errors   = warnings.query("score > @threshold_e")
    
    df_log['label'] = 'INFO'
    df_log.loc[warnings.index, 'label'] = 'WARNING'
    df_log.loc[errors.index, 'label'] = 'ERROR'
    
    if colorize:
        df_log['colour'] = scale_colour_continuous(df_log.score, norm=False)

    return df_log


def build_breaker_identify(dep_table: pd.DataFrame, error_messages: List[str]) -> Union[str, None]:
    """Identify build breaker package name."""
    g = dep_table.convert.to_dependency_graph()
    
    packages = []
    for msg in error_messages:
        packages.extend(
            p for p in dep_table.target
            if re.search(p, msg) and g.has_node(p)
        )

    return packages[-1] if packages else None


def simple_bow_similarity(matcher, matchee):
    """Compare two sentences and count number of common words.
    
    :returns: float, score representing sentence similarity
    """
    x = set(matchee.strip().lower().split())
    y = set(matcher.strip().lower().split())
    
    if len(y) <= 0:
        return 0, []
    
    match = x & y
    
    penalty = 1 + np.log10((len(x) - len(y))**2 + 1)
    score = len(match) / (len(y) * penalty)
    
    return score, list(match)


def simple_bow_similarity_with_replacement(matcher, matchee, reformat=False):
    """Compare two matcheeences while respecting matcher string formatting syntax.
    
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
