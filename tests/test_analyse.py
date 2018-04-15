# coding=utf-8
"""Thoth Build Analysers feature tests."""

import pytest

from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)


@pytest.fixture
def pytestbdd_feature_base_dir():
    return '.'


@scenario('features/analyse.feature', 'Analyse a successful Python build')
def test_analyse_a_successful_python_build():
    """Analyse a successful Python build."""


@given('I run OpenShift Build analyses')
def i_run_openshift_build_analyses():
    """I run OpenShift Build analyses."""


@when('I analyse a build logs')
def i_analyse_a_build_logs():
    """I analyse a build logs."""


@then('I conclude them successful or not-successful')
def i_conclude_them_successful_or_notsuccessful():
    """I conclude them successful or not-successful."""
