"""
Unit tests for SimulatorProcessor — migrated from
``nexus-backend/tests/unit/wxcc_simulator/test_simulator_processor.py``.

Imports rewritten to point at the in-tree plugin
(``nexus_simulator.plugins.wxcc``); the sys.path bootstrap is dropped.
Test bodies are otherwise verbatim — they cover the SimulatorProcessor
behavior (config, status, reset, seed, verify, report, error handling,
logging) end-to-end with mocked WXCCSimulatorService.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch


class TestSimulatorConfig:
    """Tests for SimulatorConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        with patch.dict(
            os.environ,
            {
                "WXCC_SIMULATOR_BUCKET": "",
                "WXCC_SIMULATOR_PREFIX": "wxcc-simulator",
                "WXCC_SIM_ORG_ID": "sim-org-001",
                "AWS_REGION": "us-east-1",
            },
            clear=False,
        ):
            from nexus_simulator.plugins.wxcc import SimulatorConfig

            config = SimulatorConfig()

            assert config.num_tasks == 10
            assert config.days_back == 7
            assert config.include_recordings is True
            assert config.use_current_time is False
            assert config.reset_first is False
            assert config.org_id == "sim-org-001"

    def test_custom_config(self, sample_simulator_config):
        """Test custom configuration values"""
        from nexus_simulator.plugins.wxcc import SimulatorConfig

        config = SimulatorConfig(**sample_simulator_config)

        assert config.num_tasks == 10
        assert config.days_back == 7
        assert config.include_recordings is True
        assert config.reset_first is True
        assert config.s3_bucket == "test-bucket"
        assert config.org_id == "sim-org-001"


class TestSimulatorProcessor:
    """Tests for SimulatorProcessor class"""

    def test_processor_initialization(self, sample_simulator_config):
        """Test processor initialization"""
        with patch.dict(
            os.environ,
            {"WXCC_SIMULATOR_BUCKET": "test-bucket"},
            clear=False,
        ):
            from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

            config = SimulatorConfig(**sample_simulator_config)
            processor = SimulatorProcessor(config=config)

            assert processor.config == config
            assert processor._service is None  # Lazy initialization
            assert processor.initial_status is None
            assert processor.seed_result is None

    def test_check_status_success(self, simulator_processor_with_mocks, mock_simulator_status):
        """Test successful status check"""
        processor = simulator_processor_with_mocks

        result = processor.check_status()

        assert result["status"] == "completed"
        assert result["step_id"] == "check_status"
        assert result["existing_tasks"] == 5
        assert result["existing_recordings"] == 5
        assert result["enabled"] is True
        assert processor.initial_status is not None

    def test_check_status_no_bucket(self):
        """Test status check fails when bucket not configured"""
        with patch.dict(os.environ, {"WXCC_SIMULATOR_BUCKET": ""}, clear=False):
            from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

            config = SimulatorConfig(s3_bucket="")
            processor = SimulatorProcessor(config=config)

            result = processor.check_status()

            assert result["status"] == "failed"
            assert "S3 bucket not configured" in result["error"]

    def test_reset_data_when_requested(self, simulator_processor_with_mocks, mock_admin_response):
        """Test reset data when reset_first is True"""
        processor = simulator_processor_with_mocks

        result = processor.reset_data()

        assert result["status"] == "completed"
        assert result["skipped"] is False
        assert result["tasks_deleted"] == 5
        assert result["recordings_deleted"] == 5

    def test_reset_data_skipped(self, sample_simulator_config, mock_wxcc_simulator_service):
        """Test reset data is skipped when reset_first is False"""
        from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

        config_no_reset = sample_simulator_config.copy()
        config_no_reset["reset_first"] = False

        config = SimulatorConfig(**config_no_reset)
        processor = SimulatorProcessor(config=config)
        processor._service = mock_wxcc_simulator_service

        result = processor.reset_data()

        assert result["status"] == "completed"
        assert result["skipped"] is True
        assert result["tasks_deleted"] == 0

    def test_seed_tasks_success(self, simulator_processor_with_mocks, mock_admin_response):
        """Test successful task seeding"""
        processor = simulator_processor_with_mocks

        result = processor.seed_tasks()

        assert result["status"] == "completed"
        assert result["tasks_created"] == 10
        assert result["recordings_created"] == 10
        assert result["used_local_recordings"] is True

    def test_verify_data_success(
        self, simulator_processor_with_mocks, mock_simulator_status, mock_tasks_response
    ):
        """Test successful data verification"""
        processor = simulator_processor_with_mocks

        result = processor.verify_data()

        assert result["status"] == "completed"
        assert result["task_count"] == 5
        assert result["recording_count"] == 5
        assert result["verified"] is True

    def test_report_summary(self, simulator_processor_with_mocks):
        """Test summary report generation"""
        processor = simulator_processor_with_mocks

        processor.check_status()
        processor.reset_data()
        processor.seed_tasks()
        processor.verify_data()

        result = processor.report_summary()

        assert result["status"] == "completed"
        assert result["final_task_count"] == 5
        assert "processing_summary" in result

    def test_get_summary(self, simulator_processor_with_mocks):
        """Test get_summary method"""
        processor = simulator_processor_with_mocks

        processor.reset_data()
        processor.seed_tasks()
        processor.verify_data()

        summary = processor.get_summary()

        assert "config" in summary
        assert "results" in summary
        assert summary["config"]["num_tasks"] == 10
        assert summary["results"]["tasks_created"] == 10


class TestSimulatorProcessorErrorHandling:
    """Tests for error handling in SimulatorProcessor"""

    def test_check_status_exception(self, sample_simulator_config):
        """Test exception handling in check_status"""
        from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

        config = SimulatorConfig(**sample_simulator_config)
        processor = SimulatorProcessor(config=config)

        mock_service = MagicMock()
        mock_service.get_status = AsyncMock(side_effect=Exception("Connection failed"))
        processor._service = mock_service

        result = processor.check_status()

        assert result["status"] == "failed"
        assert "Connection failed" in result["error"]

    def test_seed_tasks_exception(self, sample_simulator_config):
        """Test exception handling in seed_tasks"""
        from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

        config = SimulatorConfig(**sample_simulator_config)
        processor = SimulatorProcessor(config=config)

        mock_service = MagicMock()
        mock_service.seed_data = AsyncMock(side_effect=Exception("S3 upload failed"))
        processor._service = mock_service

        result = processor.seed_tasks()

        assert result["status"] == "failed"
        assert "S3 upload failed" in result["error"]


class TestSimulatorProcessorLogging:
    """Tests for logging functionality"""

    def test_custom_log_callback(self, sample_simulator_config):
        """Test custom log callback is used"""
        from nexus_simulator.plugins.wxcc import SimulatorConfig, SimulatorProcessor

        log_messages = []

        def custom_logger(level, message, step_id=None):
            log_messages.append((level, message, step_id))

        config = SimulatorConfig(**sample_simulator_config)
        processor = SimulatorProcessor(config=config, log_callback=custom_logger)

        processor._log("INFO", "Test message", "test_step")

        assert len(log_messages) == 1
        assert log_messages[0] == ("INFO", "Test message", "test_step")
