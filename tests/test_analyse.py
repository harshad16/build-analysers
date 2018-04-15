# coding=utf-8
"""Thoth Build Analysers feature tests."""

import os
import pytest

from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)

from thoth_build_analysers import openshift


@pytest.fixture
def pytestbdd_feature_base_dir():
    return '.'


FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    '../fixtures',
)


@scenario('features/analyse.feature', 'Analyse a Python build')
def test_analyse_a_successful_python_build():
    """Analyse a successful Python build."""


@given('I have a bunch of OpenShift Build logs')
def openshift_build_logs():
    """I have a bunch of OpenShift Build logs."""

    result_fixtures = []

    result_fixtures.append({'fixture_name': 'empty', 'log': '',
                            'was_successful': False})

    with open(os.path.join(FIXTURE_DIR, 'result-api-1-build'), 'r') as fixture:
        fixture = fixture.read()
        result_fixtures.append({'fixture_name': 'result-api-1-build', 'log': fixture,
                               'was_successful': False})

    with open(os.path.join(FIXTURE_DIR, 'user-api-113-build'), 'r') as fixture:
        fixture = fixture.read()
        result_fixtures.append({'fixture_name': 'result-api-1-build', 'log': fixture,
                               'was_successful': True})

    return result_fixtures


@when('I analyse build log empty')
def i_analyse_build_log_empty():
    """I analyse build log 'empty'."""


@when('I analyse build log <build_id>')
def i_analyse_build_log_build_id(openshift_build_logs, build_id):
    """I analyse build log <build_id>."""

    assert isinstance(build_id, str)

    # let's make sure we got something to test, ja, I know: it is redundant
    assert openshift_build_logs is not None
    assert openshift_build_logs is not []
    assert len(openshift_build_logs) > 0

    for build_log in openshift_build_logs:
        if build_log['fixture_name'] is not 'empty':
            build_result = openshift.analyse(build_log['log'])

            assert build_result is build_log['was_successful']


@then('I conclude it to be <successful_or_not>')
def i_conclude_it_to_be_successful_or_not(successful_or_not):
    """I conclude it to be <successful_or_not>."""

    assert isinstance(bool(successful_or_not), bool)


@then('I conclude it not to be successful')
def i_conclude_it_not_to_be_successful():
    """I conclude it not to be successful."""
