"""
WXCC Simulator MCP Tool

FastMCP tool wrapper for WXCC simulator management operations. Enables
external clients (Claude Desktop, Cursor, custom MCP hosts) to simulate
calls, seed data, reset, and manage tasks.

Verbatim port of nexus-backend's `src/tools/wxcc_simulator_tool.py`. The only
intentional differences from the source are:

- The module-level ``_service`` singleton is replaced with a closure over a
  ``WXCCSimulatorService`` instance passed to ``register_simulator_tools``,
  so the host's ``build_simulator(config)`` instance is used.
- Imports are rewritten to point at the in-tree WXCC plugin
  (``nexus_simulator.plugins.wxcc.*``).
"""

from typing import Any

from loguru import logger

from ..plugins.wxcc.models import (
    CreateTaskRequest,
    SeedDataRequest,
    TaskDirectionEnum,
    TaskStatusEnum,
)
from ..plugins.wxcc.service import WXCCSimulatorService


def register_simulator_tools(mcp: Any, simulator: WXCCSimulatorService) -> None:
    """
    Register WXCC simulator tools with a FastMCP server.

    Args:
        mcp: FastMCP server instance (any framework with a ``.tool(...)``
            decorator that takes ``name=`` and ``description=`` kwargs).
        simulator: A wired ``WXCCSimulatorService`` instance — typically
            ``build_simulator(config).wxcc``.
    """

    def get_service() -> WXCCSimulatorService:
        return simulator

    @mcp.tool(
        name="wxcc_simulator_tool",
        description="WXCC Simulator management - simulate calls, seed data, reset, and manage tasks. Use this to programmatically control the call simulator for testing."
    )
    async def wxcc_simulator_tool(
        action: str,
        # Seed parameters
        num_tasks: int | None = None,
        include_recordings: bool = True,
        days_back: int = 7,
        use_current_time: bool = False,
        # Simulate call parameters
        origin: str | None = None,
        destination: str | None = None,
        duration: int | None = None,
        status: str | None = None,
        direction: str | None = None,
        queue_name: str | None = None,
        agent_name: str | None = None,
        # Task management parameters
        task_id: str | None = None,
        task_data: dict[str, Any] | None = None,
        # List parameters
        from_time: int | None = None,
        to_time: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        WXCC Simulator management tool for external clients.

        Actions:
        - seed: Seed simulator with sample calls
        - reset: Reset all simulator data
        - status: Get simulator status
        - simulate_call: Create a single simulated call (convenience action)
        - create_task: Create a task with full control
        - list_tasks: List all simulated tasks
        - delete_task: Delete a specific task

        Args:
            action: Action to perform (required)
            num_tasks: Number of tasks to seed (for seed action, default: 10)
            include_recordings: Include recordings when seeding (default: True)
            days_back: Spread tasks over this many days (default: 7)
            use_current_time: Create tasks with current timestamp (default: False)
            origin: Caller phone number (for simulate_call)
            destination: Called phone number (for simulate_call)
            duration: Call duration in seconds (for simulate_call)
            status: Call status - completed, abandoned, transferred (for simulate_call)
            direction: Call direction - inbound, outbound (for simulate_call)
            queue_name: Queue name (for simulate_call)
            agent_name: Agent name (for simulate_call)
            task_id: Task ID (for delete_task)
            task_data: Full task data dict (for create_task)
            from_time: Start time in ms epoch (for list_tasks)
            to_time: End time in ms epoch (for list_tasks)
            limit: Max tasks to return (for list_tasks, default: 100)

        Returns:
            dict with operation results including status, message, and data

        Example Usage:
            # Seed simulator with 20 calls
            {"action": "seed", "num_tasks": 20}

            # Reset all data
            {"action": "reset"}

            # Get status
            {"action": "status"}

            # Simulate a single call
            {"action": "simulate_call", "origin": "+6591234567", "destination": "+6598765432", "duration": 180, "status": "completed"}

            # List tasks
            {"action": "list_tasks", "limit": 50}
        """
        try:
            service = get_service()

            # Check if simulator is enabled
            if not service.enabled:
                return {
                    "status": "error",
                    "message": "WXCC Simulator is not enabled. Set WXCC_SIMULATOR_BUCKET environment variable.",
                    "data": None
                }

            # Route to appropriate action
            if action == "seed":
                return await _handle_seed(
                    service,
                    num_tasks=num_tasks or 10,
                    include_recordings=include_recordings,
                    days_back=days_back,
                    use_current_time=use_current_time,
                )

            elif action == "reset":
                return await _handle_reset(service)

            elif action == "status":
                return await _handle_status(service)

            elif action == "simulate_call":
                return await _handle_simulate_call(
                    service,
                    origin=origin,
                    destination=destination,
                    duration=duration,
                    status=status,
                    direction=direction,
                    queue_name=queue_name,
                    agent_name=agent_name,
                    include_recording=include_recordings,
                )

            elif action == "create_task":
                return await _handle_create_task(service, task_data)

            elif action == "list_tasks":
                return await _handle_list_tasks(
                    service,
                    from_time=from_time,
                    to_time=to_time,
                    limit=limit,
                )

            elif action == "delete_task":
                return await _handle_delete_task(service, task_id)

            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action}. Valid actions: seed, reset, status, simulate_call, create_task, list_tasks, delete_task",
                    "data": None
                }

        except Exception as e:
            logger.error(f"WXCC Simulator tool error: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": None
            }


async def _handle_seed(
    service: WXCCSimulatorService,
    num_tasks: int,
    include_recordings: bool,
    days_back: int,
    use_current_time: bool,
) -> dict[str, Any]:
    """Handle seed action."""
    request = SeedDataRequest(
        num_tasks=num_tasks,
        include_recordings=include_recordings,
        days_back=days_back,
        use_current_time=use_current_time,
    )

    result = await service.seed_data(request)

    return {
        "status": "success" if result.success else "error",
        "message": result.message,
        "data": result.data
    }


async def _handle_reset(service: WXCCSimulatorService) -> dict[str, Any]:
    """Handle reset action."""
    result = await service.reset_data()

    return {
        "status": "success" if result.success else "error",
        "message": result.message,
        "data": result.data
    }


async def _handle_status(service: WXCCSimulatorService) -> dict[str, Any]:
    """Handle status action."""
    status = await service.get_status()

    return {
        "status": "success",
        "message": "Simulator status retrieved",
        "data": {
            "enabled": status.enabled,
            "org_id": status.org_id,
            "bucket": status.bucket,
            "prefix": status.prefix,
            "task_count": status.task_count,
            "recording_count": status.recording_count,
            "last_updated": status.last_updated.isoformat() if status.last_updated else None,
        }
    }


async def _handle_simulate_call(
    service: WXCCSimulatorService,
    origin: str | None,
    destination: str | None,
    duration: int | None,
    status: str | None,
    direction: str | None,
    queue_name: str | None,
    agent_name: str | None,
    include_recording: bool,
) -> dict[str, Any]:
    """Handle simulate_call action - convenience method to create a single call."""
    import random

    # Generate defaults for missing values
    if not origin:
        origin = f"+65{random.randint(80000000, 99999999)}"
    if not destination:
        destination = f"+65{random.randint(60000000, 69999999)}"
    if not duration:
        duration = random.randint(30, 600)
    if not status:
        status = random.choice(["completed", "completed", "completed", "abandoned"])
    if not direction:
        direction = "inbound"
    if not queue_name:
        queue_name = random.choice(["Sales", "Support", "Billing", "General"])
    if not agent_name:
        agent_name = random.choice(["Alice", "Bob", "Charlie", "Diana"])

    # Map status string to enum
    status_enum = TaskStatusEnum.COMPLETED
    if status.lower() == "abandoned":
        status_enum = TaskStatusEnum.ABANDONED
    elif status.lower() == "transferred":
        status_enum = TaskStatusEnum.TRANSFERRED

    # Map direction string to enum
    direction_enum = TaskDirectionEnum.INBOUND
    if direction.lower() == "outbound":
        direction_enum = TaskDirectionEnum.OUTBOUND

    # Create task request
    request = CreateTaskRequest(
        origin=origin,
        destination=destination,
        direction=direction_enum,
        status=status_enum,
        duration=duration,
        queue_id=f"queue-{queue_name.lower()}",
        queue_name=queue_name,
        agent_id=f"agent-{agent_name.lower()}",
        agent_name=agent_name,
    )

    result = await service.create_task(request)

    # If recording requested, we need to seed with recording
    # The create_task doesn't automatically add recordings, but seed does

    return {
        "status": "success" if result.success else "error",
        "message": result.message,
        "data": result.data
    }


async def _handle_create_task(
    service: WXCCSimulatorService,
    task_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Handle create_task action with full control."""
    if not task_data:
        return {
            "status": "error",
            "message": "task_data is required for create_task action",
            "data": None
        }

    # Map string values to enums if present
    if "status" in task_data and isinstance(task_data["status"], str):
        task_data["status"] = TaskStatusEnum(task_data["status"])
    if "direction" in task_data and isinstance(task_data["direction"], str):
        task_data["direction"] = TaskDirectionEnum(task_data["direction"])

    request = CreateTaskRequest(**task_data)
    result = await service.create_task(request)

    return {
        "status": "success" if result.success else "error",
        "message": result.message,
        "data": result.data
    }


async def _handle_list_tasks(
    service: WXCCSimulatorService,
    from_time: int | None,
    to_time: int | None,
    limit: int,
) -> dict[str, Any]:
    """Handle list_tasks action."""
    result = await service.get_tasks(
        from_time=from_time,
        to_time=to_time,
        page_size=limit,
    )

    # Convert to list of dicts
    tasks_data = []
    for task in result.data:
        tasks_data.append({
            "id": task.id,
            "status": task.attributes.status,
            "direction": task.attributes.direction,
            "origin": task.attributes.origin,
            "destination": task.attributes.destination,
            "queue_name": task.attributes.queueName,
            "agent_name": task.attributes.agentName,
            "created_time": task.attributes.createdTime,
        })

    return {
        "status": "success",
        "message": f"Found {len(tasks_data)} tasks",
        "data": {
            "tasks": tasks_data,
            "count": len(tasks_data),
        }
    }


async def _handle_delete_task(
    service: WXCCSimulatorService,
    task_id: str | None,
) -> dict[str, Any]:
    """Handle delete_task action."""
    if not task_id:
        return {
            "status": "error",
            "message": "task_id is required for delete_task action",
            "data": None
        }

    result = await service.delete_task(task_id)

    return {
        "status": "success" if result.success else "error",
        "message": result.message,
        "data": result.data
    }

