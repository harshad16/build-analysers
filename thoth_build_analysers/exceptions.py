"""Exceptions used by Build Analysers."""


class ThothBuildAnalyserException(Exception):
    """A base exception for Thoth Build Analyser exception hierarchy."""


class BuildLogAnalysisException(ThothBuildAnalyserException):
    """The Analyser did not conclude anything."""


class EmptyBuildLogException(ThothBuildAnalyserException):
    """The Analyser does not work on en empty build log."""
