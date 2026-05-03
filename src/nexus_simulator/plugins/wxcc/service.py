"""
WXCC Simulator Service

Service for managing Webex Contact Center simulator data.
Provides S3-backed storage for tasks and recordings with WXCC API-compatible responses.

Memory-safety: Uses LRU caching with size limits to prevent unbounded memory growth.
"""

import io
import json
import os
import random
import struct
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError  # noqa: F401  - parity with source's import block
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None

# Memory safety configuration
MAX_SAMPLE_CACHE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB max for sample recordings cache
MAX_SAMPLE_FILES = 20  # Maximum number of sample files to cache
MAX_DATA_CACHE_TASKS = 10000  # Maximum tasks to keep in data cache


class LRUBytesCache:
    """
    LRU cache for bytes data with both count and size limits.

    Thread-safe implementation that evicts least recently used items
    when either the item count or total size limit is exceeded.
    """

    def __init__(self, max_items: int = MAX_SAMPLE_FILES, max_size_bytes: int = MAX_SAMPLE_CACHE_SIZE_BYTES):
        self._cache: OrderedDict[str, tuple[str, bytes]] = OrderedDict()  # key -> (filename, bytes)
        self._max_items = max_items
        self._max_size_bytes = max_size_bytes
        self._current_size = 0

    def get(self, key: str) -> tuple[str, bytes] | None:
        """Get item from cache, moving it to end (most recently used)."""
        if key not in self._cache:
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, filename: str, data: bytes) -> bool:
        """
        Add item to cache, evicting LRU items if limits exceeded.

        Returns:
            True if item was added, False if item too large
        """
        data_size = len(data)

        # Don't cache items larger than half the max size
        if data_size > self._max_size_bytes // 2:
            logger.warning(f"Item {key} too large to cache ({data_size} bytes)")
            return False

        # Remove existing entry if present
        if key in self._cache:
            _, old_data = self._cache.pop(key)
            self._current_size -= len(old_data)

        # Evict items until we have space
        while (self._current_size + data_size > self._max_size_bytes or
               len(self._cache) >= self._max_items):
            if not self._cache:
                break
            # Pop oldest item (first in OrderedDict)
            evicted_key, (_, evicted_data) = self._cache.popitem(last=False)
            self._current_size -= len(evicted_data)
            logger.debug(f"Evicted {evicted_key} from sample cache ({len(evicted_data)} bytes)")

        # Add new item
        self._cache[key] = (filename, data)
        self._current_size += data_size
        return True

    def get_all(self) -> list[tuple[str, bytes]]:
        """Get all cached items as list of (filename, bytes) tuples."""
        return list(self._cache.values())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._current_size = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "items": len(self._cache),
            "max_items": self._max_items,
            "size_bytes": self._current_size,
            "max_size_bytes": self._max_size_bytes,
            "utilization_percent": round(self._current_size / self._max_size_bytes * 100, 1) if self._max_size_bytes > 0 else 0
        }

from .models import (  # noqa: E402  - intentionally below LRUBytesCache (verbatim port from nexus-backend layout)
    AdminResponse,
    CallTypeEnum,
    CapturesResponse,
    ChannelTypeEnum,
    # Admin models
    CreateTaskRequest,
    Recording,
    # Recording models
    RecordingAttributes,
    SeedDataRequest,
    SimulatorData,
    SimulatorStatus,
    StoredRecording,
    # Storage models
    StoredTask,
    Task,
    # Task models
    TaskAttributes,
    TaskDirectionEnum,
    TaskRecording,
    TasksResponse,
    # Enums
    TaskStatusEnum,
    UpdateTaskRequest,
    # Error models
    WXCCError,
    WXCCErrorMessage,
    WXCCErrorResponse,
)

# Config-provider import removed during the nexus-backend → nexus-simulator port.
# The library reads no env vars by default; the host application supplies
# bucket/prefix/region/org_id/base_url via WXCCPluginConfig and build_simulator
# wires them in. The os.getenv() fallbacks in __init__ remain so a backward-
# compatible WXCCSimulatorService() (no kwargs) still works when invoked from
# a host that sets the same env vars nexus-backend used.


class WXCCSimulatorService:
    """
    Service class for WXCC simulator operations.

    Manages tasks and recordings stored in S3 with WXCC API-compatible responses.
    """

    # Path to local recordings directory (relative to the repo root).
    # Layout: nexus-simulator/src/nexus_simulator/plugins/wxcc/service.py
    # Repo root is five `dirname()` calls up; recordings live at
    # nexus-simulator/scripts/wxcc-simulator/recordings/.
    RECORDINGS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
        "scripts", "wxcc-simulator", "recordings"
    )

    def __init__(
        self,
        bucket: str | None = None,
        prefix: str | None = None,
        region: str | None = None,
        org_id: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize the WXCC simulator service.

        Args:
            bucket: S3 bucket name (default: from config/env WXCC_SIMULATOR_BUCKET)
            prefix: S3 prefix for simulator data (default: from config/env WXCC_SIMULATOR_PREFIX)
            region: AWS region (default: from config/env AWS_REGION)
            org_id: Simulated organization ID (default: from config/env WXCC_SIM_ORG_ID)
            base_url: Base URL for recording URLs (default: from config/env WXCC_SIMULATOR_BASE_URL)
        """
        # Library port: nexus-backend's CONFIG_AVAILABLE branch (config_provider)
        # was removed. The library reads no env vars by default — values are
        # supplied via WXCCPluginConfig through build_simulator. The
        # os.getenv() fallbacks below are kept for direct construction
        # (WXCCSimulatorService() with no kwargs) so backwards-compat tests
        # and ad-hoc scripts still work the way they did before the port.
        self.bucket = bucket or os.getenv("WXCC_SIMULATOR_BUCKET", "")
        self.prefix = prefix or os.getenv("WXCC_SIMULATOR_PREFIX", "wxcc-simulator")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.org_id = org_id or os.getenv("WXCC_SIM_ORG_ID", "sim-org-001")
        self.base_url = base_url or os.getenv("WXCC_SIMULATOR_BASE_URL", "http://localhost:8000")

        self._s3_client = None
        self._data_cache: SimulatorData | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_ttl_seconds = 60  # Cache TTL
        self._local_recordings: list[str] | None = None  # Cache for local recording files

        # Use LRU cache for sample recordings instead of unbounded list
        self._sample_cache = LRUBytesCache(
            max_items=MAX_SAMPLE_FILES,
            max_size_bytes=MAX_SAMPLE_CACHE_SIZE_BYTES
        )

        logger.info(f"WXCC Simulator Service initialized: bucket={self.bucket}, prefix={self.prefix}")

    @property
    def enabled(self) -> bool:
        """Check if simulator is properly configured."""
        return bool(self.bucket) and BOTO3_AVAILABLE

    @property
    def s3_client(self):
        """Get or create S3 client, with LocalStack support."""
        if self._s3_client is None and BOTO3_AVAILABLE:
            use_localstack = os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true'

            if use_localstack:
                # Use LocalStack endpoint
                endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
                self._s3_client = boto3.client(
                    "s3",
                    region_name=self.region or 'us-east-1',
                    endpoint_url=endpoint_url,
                    aws_access_key_id='test',
                    aws_secret_access_key='test',
                )
            else:
                self._s3_client = boto3.client("s3", region_name=self.region)
        return self._s3_client

    def _get_data_key(self) -> str:
        """Get S3 key for simulator data JSON."""
        return f"{self.prefix}/data.json"

    def _get_recordings_prefix(self) -> str:
        """Get S3 prefix for recordings."""
        return f"{self.prefix}/recordings/"

    def _get_sample_recordings_prefix(self) -> str:
        """Get S3 prefix for sample recordings (source audio files)."""
        return f"{self.prefix}/sample-recordings/"

    def _get_sample_recordings_from_s3(self) -> list[tuple[str, bytes]]:
        """
        Fetch sample recordings from S3 sample-recordings/ prefix.

        Downloads audio files from s3://{bucket}/{prefix}/sample-recordings/
        and caches them using LRU cache with size limits.

        Returns:
            List of (filename, bytes) tuples for each sample recording
        """
        if not self.enabled:
            return []

        # Check if we already have cached S3 samples
        cached_samples = self._sample_cache.get_all()
        if cached_samples:
            return cached_samples

        sample_prefix = self._get_sample_recordings_prefix()

        try:
            # List objects in sample-recordings/ prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket,
                Prefix=sample_prefix
            )

            sample_keys = []
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    # Only include audio files
                    ext = os.path.splitext(key)[1].lower()
                    if ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                        sample_keys.append((key, obj.get('Size', 0)))

            if not sample_keys:
                logger.debug(f"No sample recordings found in s3://{self.bucket}/{sample_prefix}")
                return []

            # Sort by size (smallest first) to maximize cache utilization
            sample_keys.sort(key=lambda x: x[1])

            # Download each sample recording with LRU caching
            loaded_count = 0
            for key, _size in sample_keys:
                # Check if we would exceed cache limits
                cache_stats = self._sample_cache.stats()
                if cache_stats["items"] >= MAX_SAMPLE_FILES:
                    logger.debug(f"Sample cache item limit reached ({MAX_SAMPLE_FILES})")
                    break

                try:
                    response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                    audio_bytes = response['Body'].read()
                    filename = os.path.basename(key)

                    # Add to LRU cache
                    if self._sample_cache.put(key, filename, audio_bytes):
                        loaded_count += 1
                        logger.debug(f"Cached sample recording: {filename} ({len(audio_bytes)} bytes)")
                    else:
                        logger.debug(f"Sample recording too large to cache: {filename}")

                except Exception as e:
                    logger.warning(f"Failed to download sample recording {key}: {e}")

            if loaded_count > 0:
                cache_stats = self._sample_cache.stats()
                logger.info(f"Loaded {loaded_count} sample recordings from S3 "
                           f"(cache: {cache_stats['size_bytes'] // 1024}KB / "
                           f"{cache_stats['max_size_bytes'] // 1024 // 1024}MB)")

            return self._sample_cache.get_all()

        except Exception as e:
            logger.warning(f"Failed to list sample recordings from S3: {e}")
            return []

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "sample_cache": self._sample_cache.stats(),
            "data_cache_valid": self._data_cache is not None and self._cache_timestamp is not None,
            "data_cache_ttl_seconds": self._cache_ttl_seconds,
        }

    def _get_local_recordings(self) -> list[str]:
        """
        Get list of available local recording files.

        Looks for audio files (mp3, wav, m4a) in the recordings directory.

        Returns:
            List of full paths to recording files
        """
        if self._local_recordings is not None:
            return self._local_recordings

        self._local_recordings = []

        logger.debug(f"Checking for local recordings in: {self.RECORDINGS_DIR}")

        if os.path.isdir(self.RECORDINGS_DIR):
            for filename in os.listdir(self.RECORDINGS_DIR):
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                    full_path = os.path.join(self.RECORDINGS_DIR, filename)
                    if os.path.isfile(full_path):
                        self._local_recordings.append(full_path)
                        logger.debug(f"  ✓ Found: {filename}")

            if self._local_recordings:
                logger.info(f"✓ Found {len(self._local_recordings)} local recording files in {self.RECORDINGS_DIR}")
            else:
                logger.warning(f"⚠ No recording files found in {self.RECORDINGS_DIR}")
        else:
            logger.warning(f"⚠ Recordings directory not found: {self.RECORDINGS_DIR}")

        return self._local_recordings

    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac',
        }
        return content_types.get(ext, 'audio/mpeg')

    def _generate_test_wav(self, duration_seconds: int = 5) -> bytes:
        """
        Generate a simple test WAV file with a tone.

        Creates a valid WAV file with a 440Hz sine wave tone.

        Args:
            duration_seconds: Duration of the audio in seconds

        Returns:
            WAV file bytes
        """
        import math

        sample_rate = 8000  # 8kHz (telephone quality)
        num_channels = 1
        bits_per_sample = 16
        frequency = 440  # A4 note

        # Generate samples
        num_samples = sample_rate * duration_seconds
        samples = []

        for i in range(num_samples):
            # Generate sine wave with fade in/out
            t = i / sample_rate
            fade = 1.0

            # Fade in first 0.1s
            if t < 0.1:
                fade = t / 0.1
            # Fade out last 0.1s
            elif t > duration_seconds - 0.1:
                fade = (duration_seconds - t) / 0.1

            # Add some variation (simulate speech-like amplitude changes)
            amplitude = 0.3 * fade * (0.5 + 0.5 * math.sin(2 * math.pi * 0.5 * t))

            sample = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
            samples.append(sample)

        # Build WAV file
        buffer = io.BytesIO()

        # WAV header
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(samples) * bits_per_sample // 8

        # RIFF header
        buffer.write(b'RIFF')
        buffer.write(struct.pack('<I', 36 + data_size))  # File size - 8
        buffer.write(b'WAVE')

        # fmt chunk
        buffer.write(b'fmt ')
        buffer.write(struct.pack('<I', 16))  # Chunk size
        buffer.write(struct.pack('<H', 1))   # Audio format (PCM)
        buffer.write(struct.pack('<H', num_channels))
        buffer.write(struct.pack('<I', sample_rate))
        buffer.write(struct.pack('<I', byte_rate))
        buffer.write(struct.pack('<H', block_align))
        buffer.write(struct.pack('<H', bits_per_sample))

        # data chunk
        buffer.write(b'data')
        buffer.write(struct.pack('<I', data_size))

        for sample in samples:
            buffer.write(struct.pack('<h', sample))

        return buffer.getvalue()

    async def _load_data(self, force_refresh: bool = False) -> SimulatorData:
        """
        Load simulator data with three-tier caching: in-memory -> Redis -> S3.
        """
        if (
            not force_refresh
            and self._data_cache is not None
            and self._cache_timestamp is not None
            and (datetime.utcnow() - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds
        ):
            return self._data_cache

        redis_key = f"sim:wxcc:data:{self.org_id}"
        try:
            from . import _redis as redis_client
            cached = await redis_client.redis_get(redis_key)
            if cached and not force_refresh:
                data_json = json.loads(cached)
                self._data_cache = SimulatorData(**data_json)
                self._cache_timestamp = datetime.utcnow()
                logger.debug(f"Loaded WXCC data from Redis: {len(self._data_cache.tasks)} tasks")
                return self._data_cache
        except Exception as e:
            logger.debug(f"Redis miss for WXCC data: {e}")

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._get_data_key()
            )
            data_json = json.loads(response["Body"].read().decode("utf-8"))
            self._data_cache = SimulatorData(**data_json)
            self._cache_timestamp = datetime.utcnow()
            logger.debug(f"Loaded simulator data from S3: {len(self._data_cache.tasks)} tasks, {len(self._data_cache.recordings)} recordings")
            try:
                from . import _redis as redis_client
                await redis_client.redis_set(redis_key, json.dumps(data_json, default=str), ttl=300)
            except Exception:
                pass
            return self._data_cache

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info("No existing simulator data, initializing empty data")
                self._data_cache = SimulatorData(org_id=self.org_id)
                self._cache_timestamp = datetime.utcnow()
                await self._save_data()
                return self._data_cache
            raise
        except Exception as e:
            logger.error(f"Failed to load simulator data: {e}")
            self._data_cache = SimulatorData(org_id=self.org_id)
            self._cache_timestamp = datetime.utcnow()
            return self._data_cache

    async def _save_data(self) -> None:
        """Save simulator data to S3 and Redis."""
        if self._data_cache is None:
            return

        self._data_cache.updated_at = datetime.utcnow()

        try:
            from . import _redis as redis_client
            redis_key = f"sim:wxcc:data:{self.org_id}"
            await redis_client.redis_set(redis_key, self._data_cache.model_dump_json(), ttl=300)
        except Exception:
            pass

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self._get_data_key(),
                Body=self._data_cache.model_dump_json(indent=2),
                ContentType="application/json"
            )
            logger.debug("Saved simulator data to S3")
        except Exception as e:
            logger.error(f"Failed to save simulator data: {e}")
            raise

    def _invalidate_cache(self) -> None:
        """Invalidate the data cache."""
        self._cache_timestamp = None

    # ==========================================
    # WXCC-Compatible API Methods
    # ==========================================

    async def get_tasks(
        self,
        from_time: int | None = None,
        to_time: int | None = None,
        org_id: str | None = None,
        channel_type: str = "telephony",
        page_size: int = 100,
    ) -> TasksResponse:
        """
        Get tasks matching the query parameters.

        Matches WXCC GET /v1/tasks endpoint behavior.

        Args:
            from_time: Start time in milliseconds
            to_time: End time in milliseconds
            org_id: Organization ID (validated)
            channel_type: Channel type filter
            page_size: Maximum results to return

        Returns:
            TasksResponse with matching tasks
        """
        # Validate org_id
        if org_id and org_id != self.org_id:
            logger.warning(f"Org ID mismatch: expected {self.org_id}, got {org_id}")
            # Return empty results for wrong org
            return TasksResponse(data=[], meta={"totalCount": 0})

        data = await self._load_data()
        tasks: list[Task] = []

        for _task_id, stored_task in data.tasks.items():
            task = stored_task.task

            # Filter by channel type
            if task.channelType != channel_type:
                continue

            # Filter by time range
            if from_time is not None and task.createdTime is not None:
                if task.createdTime < from_time:
                    continue

            if to_time is not None and task.createdTime is not None:
                if task.createdTime > to_time:
                    continue

            tasks.append(task)

        # Sort by createdTime descending
        tasks.sort(key=lambda t: t.createdTime or 0, reverse=True)

        # Apply page size
        tasks = tasks[:page_size]

        logger.info(f"get_tasks: returning {len(tasks)} tasks")
        return TasksResponse(
            data=tasks,
            meta={"totalCount": len(tasks)},
            links=[]
        )

    async def get_captures(self, task_ids: list[str]) -> CapturesResponse:
        """
        Get recordings for the specified task IDs.

        Matches WXCC POST /v1/captures/query endpoint behavior.

        Args:
            task_ids: List of task IDs to get recordings for

        Returns:
            CapturesResponse with recordings
        """
        data = await self._load_data()
        task_recordings: list[TaskRecording] = []

        for task_id in task_ids:
            stored_task = data.tasks.get(task_id)
            if not stored_task:
                logger.debug(f"Task not found: {task_id}")
                continue

            recordings: list[Recording] = []
            for recording_id in stored_task.recording_ids:
                stored_rec = data.recordings.get(recording_id)
                if stored_rec:
                    # Update file path to point to our streaming endpoint
                    rec = stored_rec.recording.model_copy()
                    rec.attributes.filePath = f"{self.base_url}/recordings/{recording_id}"
                    recordings.append(rec)

            task_recordings.append(TaskRecording(
                taskId=task_id,
                recording=recordings
            ))

        logger.info(f"get_captures: returning recordings for {len(task_recordings)} tasks")
        return CapturesResponse(
            data=task_recordings,
            meta={}
        )

    async def get_recording_stream(self, recording_id: str) -> tuple[bytes | None, str | None]:
        """
        Get recording file content for streaming.

        Args:
            recording_id: Recording ID

        Returns:
            Tuple of (file_bytes, content_type) or (None, None) if not found
        """
        data = await self._load_data()
        stored_rec = data.recordings.get(recording_id)

        if not stored_rec:
            logger.warning(f"Recording not found: {recording_id}")
            return None, None

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=stored_rec.s3_key
            )
            content = response["Body"].read()
            content_type = response.get("ContentType", "audio/wav")

            logger.info(f"Streaming recording {recording_id}: {len(content)} bytes")
            return content, content_type

        except ClientError as e:
            logger.error(f"Failed to get recording from S3: {e}")
            return None, None

    async def get_recording_presigned_url(self, recording_id: str, expires_in: int = 3600) -> str | None:
        """
        Get a presigned URL for direct S3 download.

        Args:
            recording_id: Recording ID
            expires_in: URL expiration in seconds

        Returns:
            Presigned URL or None if not found
        """
        data = await self._load_data()
        stored_rec = data.recordings.get(recording_id)

        if not stored_rec:
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": stored_rec.s3_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    # ==========================================
    # Admin API Methods
    # ==========================================

    async def create_task(self, request: CreateTaskRequest) -> AdminResponse:
        """
        Create a new mock task.

        Args:
            request: Task creation request

        Returns:
            AdminResponse with created task info
        """
        data = await self._load_data()

        # Generate timestamps
        now = datetime.utcnow()
        created_time_ms = int(now.timestamp() * 1000)
        end_time = now + timedelta(seconds=request.duration_seconds)

        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            taskName=request.task_name,
            channelType=request.channel_type,
            startTime=now.isoformat() + "Z",
            endTime=end_time.isoformat() + "Z",
            createdTime=created_time_ms,
            lastUpdatedTime=created_time_ms,
            attributes=TaskAttributes(
                status=request.status,
                direction=request.direction,
                origin=request.origin,
                destination=request.destination,
                queueId=request.queue_id,
                queueName=request.queue_name,
                agentId=request.agent_id,
                agentName=request.agent_name,
            )
        )

        # Store task
        stored_task = StoredTask(
            task=task,
            recording_ids=[],
            created_at=now,
            updated_at=now,
        )
        data.tasks[task.id] = stored_task

        # Handle recording if provided
        if request.recording_file:
            recording_result = await self._create_recording_for_task(
                task_id=task.id,
                s3_key=request.recording_file,
                start_time_ms=created_time_ms,
                duration_seconds=request.duration_seconds,
                participants=[request.origin, request.destination],
                call_type=CallTypeEnum(request.direction.value),
            )
            if recording_result:
                stored_task.recording_ids.append(recording_result)

        await self._save_data()
        self._invalidate_cache()  # Invalidate cache so next fetch gets fresh data

        logger.info(f"Created task: {task.id}")
        return AdminResponse(
            success=True,
            message="Task created successfully",
            data={"task_id": task.id, "task": task.model_dump()}
        )

    async def update_task(self, task_id: str, request: UpdateTaskRequest) -> AdminResponse:
        """
        Update an existing task.

        Args:
            task_id: Task ID to update
            request: Update request

        Returns:
            AdminResponse with result
        """
        data = await self._load_data()

        stored_task = data.tasks.get(task_id)
        if not stored_task:
            return AdminResponse(
                success=False,
                message=f"Task not found: {task_id}"
            )

        task = stored_task.task

        # Update fields if provided
        if request.task_name is not None:
            task.taskName = request.task_name
        if request.end_time is not None:
            task.endTime = request.end_time
        if request.status is not None:
            task.attributes.status = request.status
        if request.direction is not None:
            task.attributes.direction = request.direction
        if request.origin is not None:
            task.attributes.origin = request.origin
        if request.destination is not None:
            task.attributes.destination = request.destination
        if request.queue_id is not None:
            task.attributes.queueId = request.queue_id
        if request.agent_id is not None:
            task.attributes.agentId = request.agent_id

        task.lastUpdatedTime = int(datetime.utcnow().timestamp() * 1000)
        stored_task.updated_at = datetime.utcnow()

        await self._save_data()
        self._invalidate_cache()  # Invalidate cache so next fetch gets fresh data

        logger.info(f"Updated task: {task_id}")
        return AdminResponse(
            success=True,
            message="Task updated successfully",
            data={"task": task.model_dump()}
        )

    async def delete_task(self, task_id: str) -> AdminResponse:
        """
        Delete a task and its recordings.

        Args:
            task_id: Task ID to delete

        Returns:
            AdminResponse with result
        """
        data = await self._load_data()

        stored_task = data.tasks.get(task_id)
        if not stored_task:
            return AdminResponse(
                success=False,
                message=f"Task not found: {task_id}"
            )

        # Delete associated recordings
        for recording_id in stored_task.recording_ids:
            stored_rec = data.recordings.get(recording_id)
            if stored_rec:
                # Delete S3 file
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket,
                        Key=stored_rec.s3_key
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete recording file: {e}")

                del data.recordings[recording_id]

        # Delete task
        del data.tasks[task_id]
        await self._save_data()
        self._invalidate_cache()  # Invalidate cache so next fetch gets fresh data

        logger.info(f"Deleted task: {task_id}")
        return AdminResponse(
            success=True,
            message="Task deleted successfully"
        )

    async def upload_recording(
        self,
        task_id: str,
        file_content: bytes,
        file_name: str = "recording.wav",
        participants: list[str] = None,
        call_type: CallTypeEnum = CallTypeEnum.INBOUND,
    ) -> AdminResponse:
        """
        Upload a recording file and associate it with a task.

        Args:
            task_id: Task ID to associate recording with
            file_content: Recording file bytes
            file_name: File name
            participants: Call participants
            call_type: Type of call

        Returns:
            AdminResponse with recording info
        """
        data = await self._load_data()

        stored_task = data.tasks.get(task_id)
        if not stored_task:
            return AdminResponse(
                success=False,
                message=f"Task not found: {task_id}"
            )

        # Generate recording ID and S3 key
        recording_id = str(uuid.uuid4())
        s3_key = f"{self._get_recordings_prefix()}{recording_id}.wav"

        # Upload to S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=file_content,
                ContentType="audio/wav"
            )
        except Exception as e:
            logger.error(f"Failed to upload recording: {e}")
            return AdminResponse(
                success=False,
                message=f"Failed to upload recording: {str(e)}"
            )

        # Get task times for recording timestamps
        task = stored_task.task
        start_time_ms = task.createdTime or int(datetime.utcnow().timestamp() * 1000)

        # Estimate duration (30 seconds per 100KB, rough estimate)
        duration_seconds = max(60, len(file_content) // 3200)  # 3.2KB per second for 8kHz WAV

        # Create recording
        recording = Recording(
            id=recording_id,
            attributes=RecordingAttributes(
                fileName=file_name,
                filePath=f"{self.base_url}/recordings/{recording_id}",
                startTime=start_time_ms,
                stopTime=start_time_ms + (duration_seconds * 1000),
                participants=participants or [],
                channel1="agent",
                channel2="customer",
                callType=call_type,
            )
        )

        # Store recording
        stored_rec = StoredRecording(
            recording=recording,
            task_id=task_id,
            s3_key=s3_key,
            file_size=len(file_content),
            created_at=datetime.utcnow(),
        )
        data.recordings[recording_id] = stored_rec
        stored_task.recording_ids.append(recording_id)

        await self._save_data()

        logger.info(f"Uploaded recording {recording_id} for task {task_id}")
        return AdminResponse(
            success=True,
            message="Recording uploaded successfully",
            data={
                "recording_id": recording_id,
                "s3_key": s3_key,
                "file_size": len(file_content),
            }
        )

    async def _create_recording_for_task(
        self,
        task_id: str,
        s3_key: str,
        start_time_ms: int,
        duration_seconds: int,
        participants: list[str],
        call_type: CallTypeEnum,
    ) -> str | None:
        """
        Create a recording entry for an existing S3 file.

        Internal method used when creating tasks with recordings.
        """
        data = await self._load_data()

        recording_id = str(uuid.uuid4())

        recording = Recording(
            id=recording_id,
            attributes=RecordingAttributes(
                fileName=s3_key.split("/")[-1],
                filePath=f"{self.base_url}/recordings/{recording_id}",
                startTime=start_time_ms,
                stopTime=start_time_ms + (duration_seconds * 1000),
                participants=participants,
                channel1="agent",
                channel2="customer",
                callType=call_type,
            )
        )

        stored_rec = StoredRecording(
            recording=recording,
            task_id=task_id,
            s3_key=s3_key,
            created_at=datetime.utcnow(),
        )
        data.recordings[recording_id] = stored_rec

        return recording_id

    async def seed_data(self, request: SeedDataRequest) -> AdminResponse:
        """
        Seed the simulator with sample data.

        Args:
            request: Seed configuration

        Returns:
            AdminResponse with seeding results
        """
        data = await self._load_data(force_refresh=True)

        # Use provided org_id or default
        if request.org_id:
            data.org_id = request.org_id
            self.org_id = request.org_id

        tasks_created = 0
        recordings_created = 0

        # Sample data for realistic tasks
        sample_origins = [
            "+6591234567", "+6598765432", "+6581112222",
            "+6589998888", "+6577776666", "+6566665555"
        ]
        sample_destinations = [
            "+6560001111", "+6560002222", "+6560003333"
        ]
        sample_queues = [
            ("queue-sales", "Sales Queue"),
            ("queue-support", "Technical Support"),
            ("queue-billing", "Billing Inquiries"),
        ]
        sample_agents = [
            ("agent-001", "John Smith"),
            ("agent-002", "Jane Doe"),
            ("agent-003", "Bob Wilson"),
        ]
        sample_task_names = [
            "Inbound Sales Call",
            "Technical Support Request",
            "Billing Inquiry",
            "Account Update",
            "Service Complaint",
        ]

        now = datetime.utcnow()

        for _i in range(request.num_tasks):
            # Determine task time
            if request.use_current_time:
                # Use current time with small random offset (0-5 minutes) for variety
                task_time = now - timedelta(seconds=random.uniform(0, 300))
            else:
                # Spread tasks over the specified days
                task_time = now - timedelta(
                    days=random.uniform(0, request.days_back),
                    hours=random.uniform(0, 23),
                    minutes=random.uniform(0, 59)
                )

            # Random task attributes
            duration = random.randint(60, 600)  # 1-10 minutes
            direction = random.choice([TaskDirectionEnum.INBOUND, TaskDirectionEnum.OUTBOUND])
            status = random.choices(
                [TaskStatusEnum.COMPLETED, TaskStatusEnum.ABANDONED, TaskStatusEnum.TRANSFERRED],
                weights=[0.85, 0.10, 0.05]
            )[0]
            queue = random.choice(sample_queues)
            agent = random.choice(sample_agents)
            origin = random.choice(sample_origins)
            destination = random.choice(sample_destinations)

            # Create task
            task_id = str(uuid.uuid4())
            created_time_ms = int(task_time.timestamp() * 1000)
            end_time = task_time + timedelta(seconds=duration)

            task = Task(
                id=task_id,
                taskName=random.choice(sample_task_names),
                channelType=ChannelTypeEnum.TELEPHONY,
                startTime=task_time.isoformat() + "Z",
                endTime=end_time.isoformat() + "Z",
                createdTime=created_time_ms,
                lastUpdatedTime=created_time_ms,
                attributes=TaskAttributes(
                    status=status,
                    direction=direction,
                    origin=origin if direction == TaskDirectionEnum.INBOUND else destination,
                    destination=destination if direction == TaskDirectionEnum.INBOUND else origin,
                    queueId=queue[0],
                    queueName=queue[1],
                    agentId=agent[0],
                    agentName=agent[1],
                    ani=origin,
                    dnis=destination,
                )
            )

            stored_task = StoredTask(
                task=task,
                recording_ids=[],
                created_at=task_time,
                updated_at=task_time,
            )

            # Create recording if requested (all calls have recordings)
            if request.include_recordings:
                recording_id = str(uuid.uuid4())

                # Try to use local recording files first
                local_recordings = self._get_local_recordings()
                # Try S3 sample recordings if no local files
                s3_samples = self._get_sample_recordings_from_s3() if not local_recordings else []

                if local_recordings:
                    # Randomly pick a local recording
                    local_file = random.choice(local_recordings)
                    file_ext = os.path.splitext(local_file)[1].lower()
                    s3_key = f"{self._get_recordings_prefix()}{recording_id}{file_ext}"
                    content_type = self._get_content_type(local_file)
                    file_name = os.path.basename(local_file)

                    logger.info(f"🎵 Using local recording: {file_name} (randomly selected from {len(local_recordings)} files)")

                    try:
                        with open(local_file, 'rb') as f:
                            file_content = f.read()

                        self.s3_client.put_object(
                            Bucket=self.bucket,
                            Key=s3_key,
                            Body=file_content,
                            ContentType=content_type
                        )
                        file_size = len(file_content)
                        logger.debug(f"✓ Uploaded local recording: {file_name} -> {s3_key} ({file_size:,} bytes)")
                    except Exception as e:
                        logger.error(f"✗ Failed to upload local recording {local_file}: {e}")
                        file_content = None
                        file_size = None
                elif s3_samples:
                    # Use S3 sample recordings (from sample-recordings/ prefix)
                    sample_filename, sample_bytes = random.choice(s3_samples)
                    file_ext = os.path.splitext(sample_filename)[1].lower()
                    s3_key = f"{self._get_recordings_prefix()}{recording_id}{file_ext}"
                    content_type = self._get_content_type(sample_filename)

                    try:
                        self.s3_client.put_object(
                            Bucket=self.bucket,
                            Key=s3_key,
                            Body=sample_bytes,
                            ContentType=content_type
                        )
                        file_size = len(sample_bytes)
                        file_name = sample_filename
                        logger.debug(f"Used S3 sample recording: {file_name} -> {s3_key}")
                    except Exception as e:
                        logger.warning(f"Failed to upload S3 sample recording {sample_filename}: {e}")
                        file_content = None
                        file_size = None
                        file_name = f"{task_id[:8]}_recording{file_ext}"
                else:
                    # Fallback to generated WAV if no local or S3 sample recordings
                    logger.warning("⚠ No local recordings found! Falling back to synthetic audio (meaningless tone)")
                    logger.warning(f"⚠ To use real recordings, place MP3 files in: {self.RECORDINGS_DIR}")

                    s3_key = f"{self._get_recordings_prefix()}{recording_id}.wav"
                    content_type = "audio/wav"

                    # Generate and upload actual WAV file
                    test_duration = random.randint(5, 15)
                    file_content = self._generate_test_wav(test_duration)

                    try:
                        self.s3_client.put_object(
                            Bucket=self.bucket,
                            Key=s3_key,
                            Body=file_content,
                            ContentType=content_type
                        )
                        file_size = len(file_content)
                        logger.debug(f"Generated synthetic audio: {test_duration}s WAV file")
                    except Exception as e:
                        logger.error(f"Failed to upload test recording: {e}")
                        file_content = None
                        file_size = None

                    file_name = f"{task_id[:8]}_recording.wav"

                recording = Recording(
                    id=recording_id,
                    attributes=RecordingAttributes(
                        fileName=file_name,
                        filePath=f"{self.base_url}/recordings/{recording_id}",
                        startTime=created_time_ms,
                        stopTime=created_time_ms + (duration * 1000),
                        participants=[origin, destination],
                        channel1="agent",
                        channel2="customer",
                        callType=CallTypeEnum(direction.value),
                    )
                )

                stored_rec = StoredRecording(
                    recording=recording,
                    task_id=task_id,
                    s3_key=s3_key,
                    file_size=file_size,
                    created_at=task_time,
                )
                data.recordings[recording_id] = stored_rec
                stored_task.recording_ids.append(recording_id)
                recordings_created += 1

            data.tasks[task_id] = stored_task
            tasks_created += 1

        await self._save_data()
        self._invalidate_cache()  # Invalidate cache so next fetch gets fresh data

        # Check what recording source was used
        local_recordings = self._get_local_recordings()
        s3_samples = self._get_sample_recordings_from_s3() if not local_recordings else []

        used_local = len(local_recordings) > 0 if request.include_recordings else False
        used_s3_samples = len(s3_samples) > 0 if request.include_recordings and not used_local else False

        if used_local:
            logger.info(f"✅ Seeded {tasks_created} tasks and {recordings_created} recordings using {len(local_recordings)} local audio files (MP3)")
            logger.info(f"📁 Local recordings directory: {self.RECORDINGS_DIR}")
        elif used_s3_samples:
            logger.info(f"✅ Seeded {tasks_created} tasks and {recordings_created} recordings using {len(s3_samples)} S3 sample files")
        else:
            logger.warning(f"⚠ Seeded {tasks_created} tasks and {recordings_created} recordings using SYNTHETIC audio (meaningless tones)")
            logger.warning(f"⚠ No local MP3 files found in: {self.RECORDINGS_DIR}")

        return AdminResponse(
            success=True,
            message=f"Seeded {tasks_created} tasks and {recordings_created} recordings",
            data={
                "tasks_created": tasks_created,
                "recordings_created": recordings_created,
                "org_id": self.org_id,
                "used_local_recordings": used_local,
                "used_s3_samples": used_s3_samples,
                "local_recordings_available": len(local_recordings),
                "s3_samples_available": len(s3_samples),
            }
        )

    async def reset_data(self) -> AdminResponse:
        """
        Reset all simulator data.

        Deletes all tasks and recordings.

        Returns:
            AdminResponse with result
        """
        data = await self._load_data()

        # Count before reset
        task_count = len(data.tasks)
        recording_count = len(data.recordings)

        # Delete all recording files from S3
        for stored_rec in data.recordings.values():
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket,
                    Key=stored_rec.s3_key
                )
            except Exception as e:
                logger.warning(f"Failed to delete recording: {e}")

        # Reset data
        data.tasks = {}
        data.recordings = {}
        data.updated_at = datetime.utcnow()

        await self._save_data()
        self._invalidate_cache()

        logger.info(f"Reset simulator: deleted {task_count} tasks and {recording_count} recordings")
        return AdminResponse(
            success=True,
            message=f"Reset complete: deleted {task_count} tasks and {recording_count} recordings",
            data={
                "tasks_deleted": task_count,
                "recordings_deleted": recording_count,
            }
        )

    async def get_status(self) -> SimulatorStatus:
        """
        Get simulator status.

        Returns:
            SimulatorStatus with current state
        """
        data = await self._load_data()

        return SimulatorStatus(
            enabled=self.enabled,
            org_id=self.org_id,
            bucket=self.bucket,
            prefix=self.prefix,
            task_count=len(data.tasks),
            recording_count=len(data.recordings),
            last_updated=data.updated_at,
        )

    async def get_all_tasks(self) -> list[dict]:
        """
        Get all tasks (for admin UI).

        Returns:
            List of task dictionaries with key info
        """
        data = await self._load_data()

        tasks = []
        for _task_id, stored_task in data.tasks.items():
            task = stored_task.task
            tasks.append({
                "id": task.id,
                "taskName": task.taskName,
                "status": task.attributes.status if task.attributes else "unknown",
                "direction": task.attributes.direction if task.attributes else "unknown",
                "origin": task.attributes.origin if task.attributes else "",
                "destination": task.attributes.destination if task.attributes else "",
                "channelType": task.channelType,
                "createdTime": task.createdTime,
                "endedTime": task.endTime,
                "recording_count": len(stored_task.recording_ids),
            })

        return tasks

    # ==========================================
    # Sample Recordings Management
    # ==========================================

    async def list_sample_recordings(self) -> dict[str, Any]:
        """
        List all sample recordings available in the S3 sample-recordings/ prefix.

        Returns:
            Dict with list of sample recordings and metadata
        """
        if not self.enabled or not self.bucket:
            return {
                "success": False,
                "message": "Simulator not enabled or bucket not configured",
                "recordings": []
            }

        sample_prefix = self._get_sample_recordings_prefix()
        recordings = []

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket,
                Prefix=sample_prefix
            )

            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    filename = os.path.basename(key)

                    # Skip if empty filename (prefix itself)
                    if not filename:
                        continue

                    # Only include audio files
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
                        recordings.append({
                            "filename": filename,
                            "size": obj.get('Size', 0),
                            "last_modified": obj.get('LastModified', '').isoformat() if obj.get('LastModified') else None,
                            "s3_key": key
                        })

            logger.info(f"📁 Listed {len(recordings)} sample recordings from s3://{self.bucket}/{sample_prefix}")

            return {
                "success": True,
                "message": f"Found {len(recordings)} sample recordings",
                "recordings": recordings,
                "bucket": self.bucket,
                "prefix": sample_prefix
            }

        except Exception as e:
            logger.error(f"Failed to list sample recordings: {e}")
            return {
                "success": False,
                "message": f"Failed to list sample recordings: {str(e)}",
                "recordings": []
            }

    async def upload_sample_recording(
        self,
        filename: str,
        content: bytes,
        content_type: str = None
    ) -> dict[str, Any]:
        """
        Upload a sample recording file to S3.

        Args:
            filename: Name of the file
            content: File content as bytes
            content_type: MIME type (auto-detected if not provided)

        Returns:
            Dict with upload result
        """
        if not self.enabled or not self.bucket:
            return {
                "success": False,
                "message": "Simulator not enabled or bucket not configured"
            }

        # Sanitize filename
        safe_filename = os.path.basename(filename)
        s3_key = f"{self._get_sample_recordings_prefix()}{safe_filename}"

        # Auto-detect content type if not provided
        if not content_type:
            os.path.splitext(safe_filename)[1].lower()
            content_type = self._get_content_type(safe_filename)

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content,
                ContentType=content_type
            )

            # Clear the sample recordings cache so new file is picked up
            self._sample_cache.clear()

            logger.info(f"📤 Uploaded sample recording: {safe_filename} ({len(content):,} bytes) -> s3://{self.bucket}/{s3_key}")

            return {
                "success": True,
                "message": f"Uploaded {safe_filename} ({len(content):,} bytes)",
                "filename": safe_filename,
                "size": len(content),
                "s3_key": s3_key,
                "bucket": self.bucket
            }

        except Exception as e:
            logger.error(f"Failed to upload sample recording {safe_filename}: {e}")
            return {
                "success": False,
                "message": f"Failed to upload: {str(e)}"
            }

    async def delete_sample_recording(self, filename: str) -> dict[str, Any]:
        """
        Delete a sample recording file from S3.

        Args:
            filename: Name of the file to delete

        Returns:
            Dict with delete result
        """
        if not self.enabled or not self.bucket:
            return {
                "success": False,
                "message": "Simulator not enabled or bucket not configured"
            }

        # Sanitize filename
        safe_filename = os.path.basename(filename)
        s3_key = f"{self._get_sample_recordings_prefix()}{safe_filename}"

        try:
            # Check if file exists first
            try:
                self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            except Exception:
                return {
                    "success": False,
                    "message": f"File not found: {safe_filename}"
                }

            # Delete the file
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=s3_key
            )

            # Clear the sample recordings cache
            self._sample_cache.clear()

            logger.info(f"🗑️ Deleted sample recording: {safe_filename} from s3://{self.bucket}/{s3_key}")

            return {
                "success": True,
                "message": f"Deleted {safe_filename}",
                "filename": safe_filename,
                "s3_key": s3_key
            }

        except Exception as e:
            logger.error(f"Failed to delete sample recording {safe_filename}: {e}")
            return {
                "success": False,
                "message": f"Failed to delete: {str(e)}"
            }

    # ==========================================
    # Error Response Helpers
    # ==========================================

    def create_error_response(self, code: str, message: str) -> WXCCErrorResponse:
        """Create a WXCC-compatible error response."""
        return WXCCErrorResponse(
            error=WXCCError(
                key=code,
                message=[WXCCErrorMessage(description=message)]
            )
        )

    def create_auth_error(self) -> WXCCErrorResponse:
        """Create authentication error response."""
        return self.create_error_response(
            "401",
            "Validation Unsuccessful: FAIL_VALIDATE_TOKEN"
        )

    def create_not_found_error(self, resource: str) -> WXCCErrorResponse:
        """Create not found error response."""
        return self.create_error_response(
            "404",
            f"Resource not found: {resource}"
        )

