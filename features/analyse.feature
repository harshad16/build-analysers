Feature: Thoth Build Analysers

  Background: OpenShift Build Analyse
    Given I run OpenShift Build analyses

  Scenario: Analyse a successful Python build
    When I analyse a build logs
    Then I conclude them successful or not-successful

    Examples:
      | build_id     | successful |
      | result-api-1 | False      |