Feature: Thoth Build Analysers

  Background: OpenShift Build Analyse
    Given I have a bunch of OpenShift Build logs

  Scenario: Analyse an empty build log
    When I analyse build log empty
    Then I conclude it not to be successful
    And Then I handle an Exception

  Scenario: Analyse a Python build
    When I analyse build log <build_id>
    Then I conclude it to be <successful_or_not>

    Examples:
      | build_id     | successful_or_not |
      | result-api-1 | False             |
      | user-api-113 | True              |
