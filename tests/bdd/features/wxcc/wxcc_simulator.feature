Feature: WXCC Simulator Data Management
  As a QA engineer
  I want to seed and clean up WXCC simulator test data
  So that I can run reliable call processing tests

  # These tests run against real/simulated AWS services
  # Run with: behave --tags=@live features/wxcc_simulator/wxcc_simulator.feature
  # Enable live tests: BEHAVE_RUN_LIVE=true behave --tags=@live

  Background:
    Given the WXCC simulator environment is configured

  @live @smoke
  Scenario: Smoke test - Verify simulator connectivity
    When I check the simulator status
    Then the simulator should be accessible
    And the S3 bucket should be configured
    And the simulator status should be logged

  @live @seed
  Scenario: Seed simulator with test calls
    Given the simulator is accessible
    When I seed the simulator with 5 test calls
    Then the seeding should complete successfully
    And 5 tasks should be created
    And 5 recordings should be created
    And the seeded data should be verifiable

  @live @seed @current_time
  Scenario: Seed simulator with current timestamp calls
    Given the simulator is accessible
    When I seed the simulator with 3 current-time calls
    Then the seeding should complete successfully
    And all call timestamps should be recent

  @live @reset
  Scenario: Reset simulator data
    Given the simulator has existing data
    When I reset the simulator data
    Then the reset should complete successfully
    And the simulator should be empty
    And 0 tasks should exist
    And 0 recordings should exist

  @live @cleanup
  Scenario: Clean up after seeding
    Given the simulator is accessible
    And the simulator has been seeded with 3 test calls
    When I clean up the simulator
    Then the cleanup should complete successfully
    And the simulator should be empty

  @live @complete @slow
  Scenario: Complete seeding lifecycle
    Given the simulator is accessible
    And the following simulator configuration:
      | parameter          | value |
      | num_tasks          | 5     |
      | days_back          | 3     |
      | include_recordings | true  |
      | reset_first        | true  |
    When I execute the complete seeding workflow
    Then all workflow steps should complete
    And the workflow summary should be logged
    And the final task count should match seeded count

  @live @verify
  Scenario: Verify seeded data via API
    Given the simulator has been seeded with 3 test calls
    When I query the simulator for tasks
    Then the task query should return 3 tasks
    When I query for recordings
    Then recordings should be available for each task

  @live @recordings
  Scenario: Seed with local recording files
    Given the simulator is accessible
    And local recording files are available
    When I seed the simulator with local recordings enabled
    Then the seeding should use local recordings
    And seeded recordings should be uploaded to S3

  @live @error_handling
  Scenario: Handle missing bucket configuration
    Given the simulator bucket is not configured
    When I attempt to check simulator status
    Then the status check should fail gracefully
    And an appropriate error message should be returned

  @live @performance @slow
  Scenario: Seed large number of calls efficiently
    Given the simulator is accessible
    And the following simulator configuration:
      | parameter          | value |
      | num_tasks          | 20    |
      | days_back          | 7     |
      | include_recordings | true  |
      | reset_first        | true  |
    When I seed the simulator with configured tasks
    Then all tasks should be seeded within timeout
    And seeding metrics should be logged

  @live @integration
  Scenario: Seed simulator for call processing integration test
    Given the simulator is accessible
    And the task tracker is cleared
    When I seed the simulator with 3 test calls for processing
    Then the calls should be available for processing
    And the call processing pipeline should be ready

  @live @cleanup_only
  Scenario: Clean simulator without seeding
    When I reset the simulator data
    Then the simulator should be empty
    And no errors should occur

