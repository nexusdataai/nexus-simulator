"""MCP server exposing the WXCC simulator tool — Phase 5 (activated).

Source:
    /opt/mycode/nexus/nexus-backend/src/tools/wxcc_simulator_tool.py

Tool schema (action enum, request/response shapes) matches nexus-backend 1:1
so existing MCP clients (the CLI MCP, Claude Desktop, Cursor) work unchanged.
The actual tool implementation lives in
``nexus_simulator.server.mcp_wxcc.register_simulator_tools`` (a verbatim
port); this module is the thin composition root that builds the FastMCP
server and registers the tool against the supplied ``Simulator``.

Future plugins (SFDC/Oracle/SAP/External) do not currently expose MCP tools
in nexus-backend; if they do in the future, register them here.
"""

from __future__ import annotations

from typing import Any

from .mcp_wxcc import register_simulator_tools


def create_mcp_server(simulator: Any | None = None) -> Any:
    """Build a FastMCP server with the WXCC simulator tool registered.

    Args:
        simulator: ``Simulator`` instance returned by ``build_simulator``.
            When ``simulator.wxcc`` is ``None`` the WXCC tool is skipped (no
            error) — useful for hosts that intentionally disable WXCC but
            still want the MCP surface present.

    Raises:
        ImportError: if ``fastmcp`` (in ``[server]`` extra) is not installed.
    """
    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - defensive
        raise ImportError(
            "fastmcp is not installed. Install nexus-simulator[server] "
            "to enable the MCP server."
        ) from exc

    mcp = FastMCP("nexus-simulator")

    wxcc = getattr(simulator, "wxcc", None) if simulator is not None else None
    if wxcc is not None:
        register_simulator_tools(mcp, wxcc)

    return mcp
