"""Publish backbone stream events to optional external sinks (Redis Stream, etc.)."""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger

log = logger.bind(component="telco-stream-publisher")


def _redis_stream_name(layer: str, topic: str) -> str:
    safe = topic.replace("/", ":").replace(" ", "_")
    return f"telco:backbone:{layer.lower()}:{safe}"


async def publish_backbone_streams(
    layer: str,
    streams: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Publish events per topic based on TELCO_STREAM_SINK env.

    - ``none`` (default): no-op; consumers use SSE or cache only.
    - ``redis_stream``: XADD each event to a Redis stream (needs REDIS_URL).
    """
    sink = (os.environ.get("TELCO_STREAM_SINK") or "none").strip().lower()
    result: dict[str, Any] = {"sink": sink, "topics": {}}
    if sink == "none" or not streams:
        return result

    if sink == "redis_stream":
        url = os.environ.get("REDIS_URL")
        if not url:
            log.warning("TELCO_STREAM_SINK=redis_stream but REDIS_URL is unset; skipping publish")
            result["error"] = "REDIS_URL missing"
            return result
        try:
            import redis.asyncio as aioredis
        except ImportError:
            log.warning("redis package not installed; cannot publish to Redis Stream")
            result["error"] = "redis not installed"
            return result
        try:
            client = aioredis.from_url(url, decode_responses=True)
            try:
                for topic, events in streams.items():
                    sname = _redis_stream_name(layer, topic)
                    posted = 0
                    for ev in events or []:
                        payload = json.dumps(ev, default=str)
                        await client.xadd(sname, {"data": payload})
                        posted += 1
                    result["topics"][topic] = {"stream": sname, "events": posted}
            finally:
                await client.aclose()
        except Exception as e:  # noqa: BLE001
            log.warning("Redis stream publish failed: {}", e)
            result["error"] = str(e)
        return result

    if sink == "kafka":
        log.info(
            "TELCO_STREAM_SINK=kafka is not wired in this build; install confluent-kafka and extend stream_publisher"
        )
        result["error"] = "kafka publisher not implemented"
        return result

    log.warning("Unknown TELCO_STREAM_SINK={!r}; supported: none, redis_stream", sink)
    result["error"] = f"unknown sink {sink}"
    return result
