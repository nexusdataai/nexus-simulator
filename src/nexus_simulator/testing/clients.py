"""In-process HTTP and MCP test clients."""

from __future__ import annotations

from typing import Any


class TestHttpClient:
    """Thin wrapper around ``httpx.AsyncClient`` bound to an in-process ASGI app.

    Usage::

        async with TestHttpClient(app) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200

    When ``base_url`` is provided (instead of or in addition to ``app``), the
    client makes real HTTP calls against that URL — useful for smoke testing
    a deployed pod from the same test code.
    """

    __test__ = False  # tell pytest this isn't a test class

    def __init__(
        self,
        app: Any | None = None,
        *,
        base_url: str = "http://testserver",
        headers: dict[str, str] | None = None,
    ) -> None:
        import httpx

        if app is not None:
            transport = httpx.ASGITransport(app=app)
            self._client = httpx.AsyncClient(
                transport=transport, base_url=base_url, headers=headers
            )
        else:
            self._client = httpx.AsyncClient(base_url=base_url, headers=headers)

    async def __aenter__(self) -> Any:
        return self._client

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._client.aclose()


class TestMCPClient:
    """In-process MCP client. Not usable until phase 5 activates the MCP server."""

    __test__ = False  # tell pytest this isn't a test class

    def __init__(self, mcp_server: Any | None = None) -> None:
        self._server = mcp_server

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._server is None:
            raise NotImplementedError(
                "MCP server not available. Activates in phase 5 of the extraction plan."
            )
        raise NotImplementedError("In-process MCP client wiring lands with phase 5.")
