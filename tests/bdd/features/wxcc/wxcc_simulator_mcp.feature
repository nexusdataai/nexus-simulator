Feature: WXCC Simulator MCP Tool
  As an external client or UI
  I want to manage the WXCC simulator via MCP tools
  So that I can programmatically simulate calls and manage test data

  # These tests verify the MCP tool interface for the simulator
  # Run with: behave --tags=@mcp features/wxcc_simulator/wxcc_simulator_mcp.feature
  # For live tests: BEHAVE_RUN_LIVE=true behave --tags=@mcp --tags=@live

  Background:
    Given the MCP server is running
    And the WXCC simulator is enabled

  @mcp @simulator @smoke
  Scenario: Get simulator status via MCP tool
    When I call the wxcc_simulator_tool with action "status"
    Then the response should indicate success
    And the response should contain simulator status
    And the status should include enabled flag
    And the status should include task count

  @mcp @simulator @seed
  Scenario: Seed simulator via MCP tool
    When I call the wxcc_simulator_tool with action "seed" and parameters:
      | parameter          | value |
      | num_tasks          | 5     |
      | include_recordings | true  |
      | days_back          | 7     |
    Then the response should indicate success
    And tasks should be created in the simulator
    And the response should include tasks_created count

  @mcp @simulator @simulate
  Scenario: Simulate a single call via MCP tool
    When I simulate a call with:
      | origin       | +6591234567 |
      | destination  | +6598765432 |
      | duration     | 180         |
      | status       | completed   |
      | direction    | inbound     |
      | queue_name   | Sales       |
      | agent_name   | Alice       |
    Then the call should be created successfully
    And I should receive the task details in the response

  @mcp @simulator @simulate @defaults
  Scenario: Simulate call with minimal parameters
    When I call the wxcc_simulator_tool with action "simulate_call"
    Then the call should be created successfully
    And the response should contain generated values

  @mcp @simulator @list
  Scenario: List simulator tasks via MCP tool
    Given the simulator has been seeded with 3 calls
    When I call the wxcc_simulator_tool with action "list_tasks" and parameters:
      | parameter | value |
      | limit     | 50    |
    Then the response should indicate success
    And the response should contain a tasks list
    And each task should have required fields

  @mcp @simulator @delete
  Scenario: Delete a specific task via MCP tool
    Given the simulator has been seeded with 1 call
    And I have the task ID from seeding
    When I call the wxcc_simulator_tool with action "delete_task" and task_id
    Then the response should indicate success
    And the task should be deleted

  @mcp @simulator @reset
  Scenario: Reset simulator via MCP tool
    Given the simulator has existing data
    When I call the wxcc_simulator_tool with action "reset"
    Then the response should indicate success
    And the simulator should be empty

  @mcp @simulator @workflow
  Scenario: Complete simulator workflow via MCP tool
    # Step 1: Reset to clean state
    When I call the wxcc_simulator_tool with action "reset"
    Then the response should indicate success
    
    # Step 2: Seed with test data
    When I call the wxcc_simulator_tool with action "seed" and parameters:
      | parameter  | value |
      | num_tasks  | 5     |
    Then the response should indicate success
    
    # Step 3: Verify data
    When I call the wxcc_simulator_tool with action "list_tasks"
    Then the response should contain a tasks list
    
    # Step 4: Clean up
    When I call the wxcc_simulator_tool with action "reset"
    Then the response should indicate success

  @mcp @simulator @create_task
  Scenario: Create task with full control via MCP tool
    When I call the wxcc_simulator_tool with action "create_task" and task_data:
      | field       | value            |
      | origin      | +6590001111      |
      | destination | +6590002222      |
      | status      | completed        |
      | direction   | outbound         |
      | duration    | 300              |
      | queue_name  | Premium Support  |
      | agent_name  | Bob              |
    Then the response should indicate success
    And the task should be created with the specified values

  @mcp @simulator @error_handling
  Scenario: Handle invalid action gracefully
    When I call the wxcc_simulator_tool with action "invalid_action"
    Then the response should indicate error
    And the error message should mention valid actions

  @mcp @simulator @error_handling
  Scenario: Handle delete without task_id
    When I call the wxcc_simulator_tool with action "delete_task"
    Then the response should indicate error
    And the error message should mention task_id required

  @mcp @simulator @error_handling
  Scenario: Handle create_task without task_data
    When I call the wxcc_simulator_tool with action "create_task"
    Then the response should indicate error
    And the error message should mention task_data required

  @mcp @simulator @disabled
  Scenario: Handle simulator not enabled
    Given the WXCC simulator is disabled
    When I call the wxcc_simulator_tool with action "status"
    Then the response should indicate error
    And the error message should mention simulator not enabled

  @mcp @simulator @performance
  Scenario: Seed large dataset via MCP tool
    When I call the wxcc_simulator_tool with action "seed" and parameters:
      | parameter          | value |
      | num_tasks          | 50    |
      | include_recordings | false |
      | use_current_time   | true  |
    Then the response should indicate success
    And all tasks should be created within reasonable time

