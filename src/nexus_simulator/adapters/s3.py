"""S3-backed ``StorageBackend`` adapter.

Uses ``boto3``; lazy-initialized so the library imports cleanly even when
``[aws]`` extras are not installed (the constructor will raise at call-time
rather than at import).

Wire format (JSON serialization, key layout under ``<prefix>/<key>``) matches
nexus-backend's ``BaseSimulatorService._s3_get_json`` / ``_s3_key`` so an
existing S3 dump in nexus-backend's account is consumable verbatim by this
adapter.
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import Iterable
from typing import Any, BinaryIO

from loguru import logger

try:
    import boto3
    from botocore.exceptions import ClientError  # noqa: F401  (re-exported for callers)

    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None  # type: ignore[assignment]
    BOTO3_AVAILABLE = False

from ..errors import StorageError

s3_logger = logger.bind(component="s3-adapter")


class S3StorageBackend:
    """``StorageBackend`` backed by an S3 bucket.

    All operations are I/O-bound boto3 calls dispatched through
    ``asyncio.to_thread`` so the surface stays async-compatible with the
    in-memory adapter.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        *,
        region: str | None = None,
        client: Any = None,
    ) -> None:
        if not BOTO3_AVAILABLE and client is None:
            raise StorageError(
                "boto3 is not installed. Install nexus-simulator[aws] or pass a custom client."
            )
        self.bucket = bucket
        self.prefix = prefix
        self._region = region
        self._client = client  # injected for tests; constructed lazily otherwise

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _s3(self) -> Any:
        if self._client is None:
            self._client = boto3.client("s3", region_name=self._region)
        return self._client

    async def get_json(self, key: str) -> Any | None:
        full = self._full_key(key)

        def _read() -> Any | None:
            try:
                resp = self._s3().get_object(Bucket=self.bucket, Key=full)
                return json.loads(resp["Body"].read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001 - mirrors backend's broad except
                s3_logger.warning(f"Failed to load s3://{self.bucket}/{full}: {e}")
                return None

        return await asyncio.to_thread(_read)

    async def ensure_bucket(self) -> None:
        def _ensure() -> None:
            client = self._s3()
            try:
                client.head_bucket(Bucket=self.bucket)
            except Exception:
                kwargs: dict[str, Any] = {"Bucket": self.bucket}
                if self._region and self._region != "us-east-1":
                    kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
                try:
                    client.create_bucket(**kwargs)
                except Exception as exc:  # noqa: BLE001
                    s3_logger.warning(f"create_bucket {self.bucket} failed: {exc}")

        await asyncio.to_thread(_ensure)

    async def put_json(self, key: str, value: Any) -> None:
        full = self._full_key(key)
        body = json.dumps(value, default=str).encode("utf-8")

        def _write() -> None:
            self._s3().put_object(
                Bucket=self.bucket,
                Key=full,
                Body=body,
                ContentType="application/json",
            )

        await asyncio.to_thread(_write)

    async def list_keys(self, sub_prefix: str = "") -> Iterable[str]:
        scan_prefix = self._full_key(sub_prefix) if sub_prefix else self.prefix
        relative_prefix = f"{self.prefix}/" if self.prefix else ""

        def _list() -> list[str]:
            out: list[str] = []
            paginator = self._s3().get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=scan_prefix):
                for obj in page.get("Contents", []) or []:
                    full = obj["Key"]
                    if relative_prefix and full.startswith(relative_prefix):
                        out.append(full[len(relative_prefix):])
                    else:
                        out.append(full)
            return out

        return await asyncio.to_thread(_list)

    async def get_bytes(self, key: str) -> bytes | None:
        full = self._full_key(key)

        def _read() -> bytes | None:
            try:
                resp = self._s3().get_object(Bucket=self.bucket, Key=full)
                return resp["Body"].read()
            except Exception as e:  # noqa: BLE001
                s3_logger.warning(f"Failed to read bytes s3://{self.bucket}/{full}: {e}")
                return None

        return await asyncio.to_thread(_read)

    async def put_bytes(self, key: str, data: bytes) -> None:
        full = self._full_key(key)

        def _write() -> None:
            self._s3().put_object(Bucket=self.bucket, Key=full, Body=data)

        await asyncio.to_thread(_write)

    async def delete(self, key: str) -> None:
        full = self._full_key(key)

        def _del() -> None:
            self._s3().delete_object(Bucket=self.bucket, Key=full)

        await asyncio.to_thread(_del)

    async def stream_to(self, key: str, sink: BinaryIO) -> None:
        full = self._full_key(key)

        def _stream() -> None:
            resp = self._s3().get_object(Bucket=self.bucket, Key=full)
            buf = io.BytesIO(resp["Body"].read())
            sink.write(buf.getvalue())

        await asyncio.to_thread(_stream)
