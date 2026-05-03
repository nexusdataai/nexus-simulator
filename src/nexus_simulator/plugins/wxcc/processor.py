"""
Simulator Processor - Core Logic for WXCC Simulator Seeding

This module provides the SimulatorProcessor class that encapsulates all simulator
seeding logic for use in the journey stage system.
"""

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .models import SeedDataRequest

# In nexus-backend the processor reached into ``src.services`` / ``src.models``
# via a sys.path dance; in the library these are clean sibling modules.
from .service import WXCCSimulatorService

SIMULATOR_AVAILABLE = True

# Environment defaults
DEFAULT_BUCKET = os.environ.get('WXCC_SIMULATOR_BUCKET', '')
DEFAULT_PREFIX = os.environ.get('WXCC_SIMULATOR_PREFIX', 'wxcc-simulator')
DEFAULT_REGION = os.environ.get('AWS_REGION', 'us-east-1')
DEFAULT_ORG_ID = os.environ.get('WXCC_SIM_ORG_ID', 'sim-org-001')
DEFAULT_BASE_URL = os.environ.get('WXCC_SIMULATOR_BASE_URL', 'http://localhost:8000')


@dataclass
class SimulatorConfig:
    """Configuration for simulator seeding"""
    num_tasks: int = 10
    days_back: int = 7
    include_recordings: bool = True
    use_current_time: bool = False
    reset_first: bool = False
    s3_bucket: str = field(default_factory=lambda: DEFAULT_BUCKET)
    s3_prefix: str = field(default_factory=lambda: DEFAULT_PREFIX)
    org_id: str = field(default_factory=lambda: DEFAULT_ORG_ID)
    aws_region: str = field(default_factory=lambda: DEFAULT_REGION)
    base_url: str = field(default_factory=lambda: DEFAULT_BASE_URL)

    def __post_init__(self):
        """Set defaults from environment if not provided"""
        if not self.s3_bucket:
            self.s3_bucket = DEFAULT_BUCKET
        if not self.s3_prefix:
            self.s3_prefix = DEFAULT_PREFIX
        if not self.org_id:
            self.org_id = DEFAULT_ORG_ID
        if not self.aws_region:
            self.aws_region = DEFAULT_REGION


class SimulatorProcessor:
    """
    Core simulator seeding logic for use in the journey stage system.

    This class provides methods for each step of the simulator seeding workflow:
    1. Check status - Verify simulator configuration and current state
    2. Reset data - Optionally clear all existing simulator data
    3. Seed tasks - Create tasks with recordings
    4. Verify data - Validate seeded data is accessible
    5. Report summary - Generate final summary metrics
    """

    def __init__(self, config: SimulatorConfig, log_callback: Callable[..., Any] | None = None):
        """
        Initialize the SimulatorProcessor.

        Args:
            config: SimulatorConfig instance with seeding settings
            log_callback: Optional callback function for logging (stage integration)
        """
        self.config = config
        self.log_callback = log_callback or (lambda level, msg, step_id=None: logger.info(msg))

        # Initialize service lazily
        self._service = None

        # Processing state (passed between steps)
        self.initial_status = None
        self.reset_result = None
        self.seed_result = None
        self.verification_result = None
        self.final_status = None

    def _log(self, level: str, message: str, step_id: str = None):
        """Log a message using the callback"""
        self.log_callback(level, message, step_id)

    @property
    def service(self) -> 'WXCCSimulatorService':
        """Lazy initialization of WXCCSimulatorService"""
        if self._service is None:
            if not SIMULATOR_AVAILABLE:
                raise RuntimeError("Simulator service not available. Check imports.")

            self._service = WXCCSimulatorService(
                bucket=self.config.s3_bucket,
                prefix=self.config.s3_prefix,
                region=self.config.aws_region,
                org_id=self.config.org_id,
                base_url=self.config.base_url,
            )
        return self._service

    def check_status(self) -> dict[str, Any]:
        """
        Step 1: Check simulator status and configuration.

        Returns:
            Dict with status check results
        """
        self._log('INFO', "Checking simulator status", 'check_status')

        try:
            # Check if simulator is properly configured
            if not self.config.s3_bucket:
                self._log('WARNING', "S3 bucket not configured", 'check_status')
                return {
                    'status': 'failed',
                    'step_id': 'check_status',
                    'error': 'S3 bucket not configured. Set WXCC_SIMULATOR_BUCKET.',
                    'summary': 'Simulator not properly configured'
                }

            # Get current status
            status = asyncio.run(self.service.get_status())

            self.initial_status = {
                'enabled': status.enabled,
                'org_id': status.org_id,
                'bucket': status.bucket,
                'prefix': status.prefix,
                'task_count': status.task_count,
                'recording_count': status.recording_count,
                'last_updated': status.last_updated.isoformat() if status.last_updated else None,
            }

            self._log('INFO', f"Simulator enabled: {status.enabled}", 'check_status')
            self._log('INFO', f"Current tasks: {status.task_count}", 'check_status')
            self._log('INFO', f"Current recordings: {status.recording_count}", 'check_status')
            self._log('INFO', f"S3 bucket: {status.bucket}/{status.prefix}", 'check_status')

            return {
                'status': 'completed',
                'step_id': 'check_status',
                'summary': f'Simulator ready with {status.task_count} existing tasks',
                'enabled': status.enabled,
                'existing_tasks': status.task_count,
                'existing_recordings': status.recording_count,
                'bucket': status.bucket,
                'prefix': status.prefix,
                'org_id': status.org_id,
            }

        except Exception as e:
            self._log('ERROR', f"Failed to check status: {str(e)}", 'check_status')
            return {
                'status': 'failed',
                'step_id': 'check_status',
                'error': str(e),
                'summary': f'Failed to check simulator status: {str(e)}'
            }

    def reset_data(self) -> dict[str, Any]:
        """
        Step 2: Reset simulator data if configured to do so.

        Returns:
            Dict with reset results
        """
        self._log('INFO', f"Reset first: {self.config.reset_first}", 'reset_data')

        if not self.config.reset_first:
            self._log('INFO', "Reset not requested, skipping", 'reset_data')
            self.reset_result = {'skipped': True}
            return {
                'status': 'completed',
                'step_id': 'reset_data',
                'summary': 'Reset not requested, skipping',
                'skipped': True,
                'tasks_deleted': 0,
                'recordings_deleted': 0,
            }

        try:
            self._log('INFO', "Resetting all simulator data", 'reset_data')

            result = asyncio.run(self.service.reset_data())

            self.reset_result = {
                'success': result.success,
                'tasks_deleted': result.data.get('tasks_deleted', 0) if result.data else 0,
                'recordings_deleted': result.data.get('recordings_deleted', 0) if result.data else 0,
            }

            self._log('INFO', f"Reset complete: {result.message}", 'reset_data')

            return {
                'status': 'completed',
                'step_id': 'reset_data',
                'summary': result.message,
                'skipped': False,
                'tasks_deleted': self.reset_result['tasks_deleted'],
                'recordings_deleted': self.reset_result['recordings_deleted'],
            }

        except Exception as e:
            self._log('ERROR', f"Failed to reset data: {str(e)}", 'reset_data')
            return {
                'status': 'failed',
                'step_id': 'reset_data',
                'error': str(e),
                'summary': f'Failed to reset simulator data: {str(e)}'
            }

    def seed_tasks(self) -> dict[str, Any]:
        """
        Step 3: Seed simulator with tasks and recordings.

        Returns:
            Dict with seeding results
        """
        self._log('INFO', f"Seeding {self.config.num_tasks} tasks", 'seed_tasks')
        self._log('INFO', f"Include recordings: {self.config.include_recordings}", 'seed_tasks')
        self._log('INFO', f"Days back: {self.config.days_back}", 'seed_tasks')
        self._log('INFO', f"Use current time: {self.config.use_current_time}", 'seed_tasks')

        try:
            # Create seed request
            request = SeedDataRequest(
                num_tasks=self.config.num_tasks,
                include_recordings=self.config.include_recordings,
                days_back=self.config.days_back,
                use_current_time=self.config.use_current_time,
                org_id=self.config.org_id,
            )

            result = asyncio.run(self.service.seed_data(request))

            self.seed_result = {
                'success': result.success,
                'tasks_created': result.data.get('tasks_created', 0) if result.data else 0,
                'recordings_created': result.data.get('recordings_created', 0) if result.data else 0,
                'used_local_recordings': result.data.get('used_local_recordings', False) if result.data else False,
                'local_recordings_available': result.data.get('local_recordings_available', 0) if result.data else 0,
            }

            audio_source = "local files" if self.seed_result['used_local_recordings'] else "synthetic"
            self._log('INFO', f"Tasks created: {self.seed_result['tasks_created']}", 'seed_tasks')
            self._log('INFO', f"Recordings created: {self.seed_result['recordings_created']}", 'seed_tasks')
            self._log('INFO', f"Audio source: {audio_source}", 'seed_tasks')

            return {
                'status': 'completed',
                'step_id': 'seed_tasks',
                'summary': result.message,
                'tasks_created': self.seed_result['tasks_created'],
                'recordings_created': self.seed_result['recordings_created'],
                'used_local_recordings': self.seed_result['used_local_recordings'],
                'local_recordings_available': self.seed_result['local_recordings_available'],
            }

        except Exception as e:
            self._log('ERROR', f"Failed to seed data: {str(e)}", 'seed_tasks')
            return {
                'status': 'failed',
                'step_id': 'seed_tasks',
                'error': str(e),
                'summary': f'Failed to seed simulator data: {str(e)}'
            }

    def verify_data(self) -> dict[str, Any]:
        """
        Step 4: Verify seeded data is accessible via API.

        Returns:
            Dict with verification results
        """
        self._log('INFO', "Verifying seeded data", 'verify_data')

        try:
            # Get updated status
            status = asyncio.run(self.service.get_status())

            # Verify via tasks query
            tasks_response = asyncio.run(self.service.get_tasks(org_id=self.config.org_id))
            tasks = tasks_response.data if tasks_response else []

            self.verification_result = {
                'status_task_count': status.task_count,
                'status_recording_count': status.recording_count,
                'api_tasks_returned': len(tasks),
                'verified': status.task_count > 0,
            }

            # Check a sample recording if available
            if tasks and status.recording_count > 0:
                sample_task_id = tasks[0].id if hasattr(tasks[0], 'id') else tasks[0].get('id')
                if sample_task_id:
                    try:
                        captures = asyncio.run(self.service.get_captures([sample_task_id]))
                        if captures and captures.data:
                            self.verification_result['sample_recording_verified'] = True
                            self._log('INFO', f"Sample recording verified for task {sample_task_id[:20]}...", 'verify_data')
                    except Exception as e:
                        self._log('WARNING', f"Could not verify sample recording: {str(e)}", 'verify_data')

            self._log('INFO', f"Verification complete - {status.task_count} tasks accessible", 'verify_data')

            return {
                'status': 'completed',
                'step_id': 'verify_data',
                'summary': f'Verified {status.task_count} tasks, {status.recording_count} recordings',
                'task_count': status.task_count,
                'recording_count': status.recording_count,
                'api_accessible': len(tasks) > 0,
                'verified': self.verification_result['verified'],
            }

        except Exception as e:
            self._log('ERROR', f"Verification failed: {str(e)}", 'verify_data')
            return {
                'status': 'failed',
                'step_id': 'verify_data',
                'error': str(e),
                'summary': f'Verification failed: {str(e)}'
            }

    def report_summary(self) -> dict[str, Any]:
        """
        Step 5: Generate final summary report.

        Returns:
            Dict with summary metrics
        """
        self._log('INFO', "Generating summary report", 'report_summary')

        try:
            # Get final status
            status = asyncio.run(self.service.get_status())

            self.final_status = {
                'enabled': status.enabled,
                'org_id': status.org_id,
                'bucket': status.bucket,
                'prefix': status.prefix,
                'task_count': status.task_count,
                'recording_count': status.recording_count,
                'last_updated': status.last_updated.isoformat() if status.last_updated else None,
            }

            # Build summary
            summary = self.get_summary()

            self._log('INFO', "=" * 60, 'report_summary')
            self._log('INFO', "WXCC SIMULATOR SEEDING SUMMARY", 'report_summary')
            self._log('INFO', "=" * 60, 'report_summary')
            self._log('INFO', "Configuration:", 'report_summary')
            self._log('INFO', f"  - num_tasks: {self.config.num_tasks}", 'report_summary')
            self._log('INFO', f"  - include_recordings: {self.config.include_recordings}", 'report_summary')
            self._log('INFO', f"  - days_back: {self.config.days_back}", 'report_summary')
            self._log('INFO', f"  - reset_first: {self.config.reset_first}", 'report_summary')
            self._log('INFO', "Results:", 'report_summary')
            self._log('INFO', f"  - Tasks created: {summary['results'].get('tasks_created', 0)}", 'report_summary')
            self._log('INFO', f"  - Recordings created: {summary['results'].get('recordings_created', 0)}", 'report_summary')
            self._log('INFO', f"  - Total tasks: {status.task_count}", 'report_summary')
            self._log('INFO', f"  - Total recordings: {status.recording_count}", 'report_summary')
            self._log('INFO', "=" * 60, 'report_summary')

            return {
                'status': 'completed',
                'step_id': 'report_summary',
                'summary': f'Seeding complete: {status.task_count} tasks, {status.recording_count} recordings',
                'final_task_count': status.task_count,
                'final_recording_count': status.recording_count,
                'processing_summary': summary,
            }

        except Exception as e:
            self._log('ERROR', f"Failed to generate summary: {str(e)}", 'report_summary')
            return {
                'status': 'failed',
                'step_id': 'report_summary',
                'error': str(e),
                'summary': f'Failed to generate summary: {str(e)}'
            }

    def get_summary(self) -> dict[str, Any]:
        """Get overall processing summary"""
        return {
            'config': {
                'num_tasks': self.config.num_tasks,
                'days_back': self.config.days_back,
                'include_recordings': self.config.include_recordings,
                'use_current_time': self.config.use_current_time,
                'reset_first': self.config.reset_first,
                's3_bucket': self.config.s3_bucket,
                's3_prefix': self.config.s3_prefix,
                'org_id': self.config.org_id,
            },
            'results': {
                'tasks_created': self.seed_result.get('tasks_created', 0) if self.seed_result else 0,
                'recordings_created': self.seed_result.get('recordings_created', 0) if self.seed_result else 0,
                'used_local_recordings': self.seed_result.get('used_local_recordings', False) if self.seed_result else False,
                'reset_performed': not (self.reset_result.get('skipped', True) if self.reset_result else True),
                'tasks_deleted': self.reset_result.get('tasks_deleted', 0) if self.reset_result else 0,
                'verified': self.verification_result.get('verified', False) if self.verification_result else False,
            },
            'initial_status': self.initial_status,
            'final_status': self.final_status,
        }


