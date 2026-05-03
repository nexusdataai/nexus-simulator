"""Pytest fixtures for WXCC plugin unit tests.

Migrated from
``nexus-backend/tests/unit/wxcc_simulator/conftest.py`` with the imports
rewritten to point at the in-tree plugin
(``nexus_simulator.plugins.wxcc``) and the sys.path bootstrap dropped.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def sample_simulator_config():
    """Sample simulator configuration"""
    return {
        "num_tasks": 10,
        "days_back": 7,
        "include_recordings": True,
        "use_current_time": False,
        "reset_first": True,
        "s3_bucket": "test-bucket",
        "s3_prefix": "wxcc-simulator",
        "org_id": "sim-org-001",
        "aws_region": "us-east-1",
    }


@pytest.fixture
def mock_simulator_status():
    """Mock simulator status response"""
    mock_status = MagicMock()
    mock_status.enabled = True
    mock_status.org_id = "sim-org-001"
    mock_status.bucket = "test-bucket"
    mock_status.prefix = "wxcc-simulator"
    mock_status.task_count = 5
    mock_status.recording_count = 5
    mock_status.last_updated = datetime.now()
    return mock_status


@pytest.fixture
def mock_admin_response():
    """Mock admin response"""
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.message = "Operation completed successfully"
    mock_response.data = {
        "tasks_created": 10,
        "recordings_created": 10,
        "tasks_deleted": 5,
        "recordings_deleted": 5,
        "used_local_recordings": True,
        "local_recordings_available": 7,
    }
    return mock_response


@pytest.fixture
def mock_tasks_response():
    """Mock tasks response"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(id="task-001"),
        MagicMock(id="task-002"),
        MagicMock(id="task-003"),
    ]
    return mock_response


@pytest.fixture
def mock_captures_response():
    """Mock captures response"""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(taskId="task-001", recording=[MagicMock()]),
    ]
    return mock_response


@pytest.fixture
def mock_wxcc_simulator_service(
    mock_simulator_status, mock_admin_response, mock_tasks_response, mock_captures_response
):
    """Mock WXCCSimulatorService"""
    mock_service = MagicMock()
    mock_service.get_status = AsyncMock(return_value=mock_simulator_status)
    mock_service.reset_data = AsyncMock(return_value=mock_admin_response)
    mock_service.seed_data = AsyncMock(return_value=mock_admin_response)
    mock_service.get_tasks = AsyncMock(return_value=mock_tasks_response)
    mock_service.get_captures = AsyncMock(return_value=mock_captures_response)
    return mock_service


@pytest.fixture
def simulator_processor_with_mocks(sample_simulator_config, mock_wxcc_simulator_service):
    """Create SimulatorProcessor with mocked WXCCSimulatorService injected."""
    with patch.dict(
        os.environ,
        {
            "WXCC_SIMULATOR_BUCKET": "test-bucket",
            "WXCC_SIMULATOR_PREFIX": "wxcc-simulator",
            "WXCC_SIM_ORG_ID": "sim-org-001",
            "AWS_REGION": "us-east-1",
        },
    ):
        from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

        config = SimulatorConfig(**sample_simulator_config)
        processor = SimulatorProcessor(config=config)
        # Inject mock service
        processor._service = mock_wxcc_simulator_service
        return processor
