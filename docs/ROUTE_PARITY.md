# Route parity inventory

This document is the **source of truth** for the reference server's HTTP surface during the
nexus-backend → nexus-simulator extraction. Each phase (5–8 of the master extraction plan)
activates the routes tied to the plugin it ports. No route in this library may simplify,
shortcut, or diverge from the nexus-backend source without an explicit, documented reason.

> Every fix, optimization, retry, caching behavior, decimal conversion, error-path nuance,
> and edge case in the source must be preserved **verbatim** during the phase port. The e2e
> tests migrated from nexus-backend in the same phase PR are the safety net.

## How to port a route

1. Open the referenced `file:lineStart-lineEnd` range in the nexus-backend source.
2. Translate the function body to use the plugin instance off `app.state.simulator.<plugin>`
   instead of nexus-backend's module-level service singleton.
3. Keep every branch, guard, and early-return. If the source has a comment starting with
   `# fix`, `# ensure`, `# workaround`, `# optimization`, `# handle`, transport it verbatim.
4. Stamp the phase PR description with the commit SHA of nexus-backend's `dev` branch you
   ported from, so drift is detectable later via `git log <sha>..origin/dev -- <source>`.
5. Migrate the corresponding nexus-backend test(s) to `tests/e2e/` in the same PR.

## Phase activation (from the master plan)

| Phase | Routes activated | Source plugin moved |
|-------|------------------|---------------------|
| 5 | WXCC (tasks, captures, recordings, admin, seed/reset, sample-recordings, health) | `plugins/wxcc/` (service + processor + models + MCP tool) |
| 6 | SFDC (status, load, reset, objects, dump, health)                                 | `plugins/sfdc/` |
| 7 | Oracle ERP + SAP (status, load, reset, objects, dump, health)                     | `plugins/oracle_erp/`, `plugins/sap/` |
| 8 | External Source (status, load, seed, reset, objects, uploads, health)             | `plugins/external_source/` |
| out-of-scope | WXCC journey stage (`wxcc_simulator_stage.py`) | Stays in nexus-ai-engine; imports `SimulatorProcessor` from `nexus_simulator.plugins.wxcc` |

Until the activating phase lands, the library's router returns **501 Not Implemented** on
each endpoint. CI does not treat 501 as a failure for these routes.

---

## WXCC Simulator API

Source: [nexus-backend/src/apis/wxcc_simulator_api.py](../../nexus-backend/src/apis/wxcc_simulator_api.py)
Library target: `src/nexus_simulator/server/routers/wxcc.py`
Mounted at: `/api/v1/simulator` (matches `nexus-backend/mcp_http_gateway.py` line 1513)

### WXCC-compatible endpoints (Bearer-auth via `WXCC_SIM_TOKEN`)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/tasks`                            |  94 | 5 |
| POST   | `/captures/query`                   | 141 | 5 |
| GET    | `/recordings/{recording_id}`        | 173 | 5 |
| GET    | `/recordings/{recording_id}/url`    | 205 | 5 |

### Admin endpoints (no auth — host wraps with auth as needed)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/status`                                   | 234 | 5 |
| GET    | `/admin/tasks`                              | 247 | 5 |
| POST   | `/tasks`                                    | 284 | 5 |
| PUT    | `/tasks/{task_id}`                          | 298 | 5 |
| DELETE | `/tasks/{task_id}`                          | 311 | 5 |
| POST   | `/tasks/{task_id}/recordings`               | 324 | 5 |
| POST   | `/seed`                                     | 358 | 5 |
| POST   | `/reset`                                    | 378 | 5 |
| GET    | `/sample-recordings`                        | 395 | 5 |
| POST   | `/sample-recordings`                        | 409 | 5 |
| DELETE | `/sample-recordings/{filename}`             | 445 | 5 |
| GET    | `/health`                                   | 462 | 5 |

### MCP tools

Source: [nexus-backend/src/tools/wxcc_simulator_tool.py](../../nexus-backend/src/tools/wxcc_simulator_tool.py)
Library target: `src/nexus_simulator/server/mcp.py` exposes `wxcc_simulator_tool` via FastMCP,
backed by the WXCC plugin instance. Tool schema must match nexus-backend 1:1 so existing MCP
clients work unchanged.

---

## SFDC Simulator API

Source: [nexus-backend/src/apis/sfdc_simulator_api.py](../../nexus-backend/src/apis/sfdc_simulator_api.py)
Library target: `src/nexus_simulator/server/routers/sfdc.py`
Mounted at: `/api/v1/sfdc-simulator` (matches `nexus-backend/mcp_http_gateway.py` line 1524)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/status`                                   |  52 | 6 |
| GET    | `/load/status`                              |  83 | 6 |
| POST   | `/load`                                     |  90 | 6 |
| POST   | `/reset`                                    |  98 | 6 |
| GET    | `/objects`                                  | 105 | 6 |
| GET    | `/objects/{schema}/{table}`                 | 130 | 6 |
| GET    | `/objects/{schema}/{table}/columns`         | 160 | 6 |
| POST   | `/dump`                                     | 188 | 6 |
| GET    | `/dump/status`                              | 219 | 6 |
| POST   | `/restart-pods`                             | 226 | 6 |
| GET    | `/health`                                   | 272 | 6 |

---

## Oracle ERP Simulator API

Source: [nexus-backend/src/apis/oracle_erp_simulator_api.py](../../nexus-backend/src/apis/oracle_erp_simulator_api.py)
Library target: `src/nexus_simulator/server/routers/oracle_erp.py`
Mounted at: `/api/v1/oracle-erp-simulator` (matches `nexus-backend/mcp_http_gateway.py` line 1533)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/status`                                   |  39 | 7 |
| GET    | `/load/status`                              |  53 | 7 |
| POST   | `/load`                                     |  59 | 7 |
| POST   | `/reset`                                    |  66 | 7 |
| GET    | `/objects`                                  |  73 | 7 |
| GET    | `/objects/{schema}/{table}`                 |  81 | 7 |
| GET    | `/objects/{schema}/{table}/columns`         |  94 | 7 |
| GET    | `/dump/status`                              | 117 | 7 |
| POST   | `/restart-pods`                             | 123 | 7 |
| GET    | `/health`                                   | 168 | 7 |

---

## SAP Simulator API

Source: [nexus-backend/src/apis/sap_simulator_api.py](../../nexus-backend/src/apis/sap_simulator_api.py)
Library target: `src/nexus_simulator/server/routers/sap.py`
Mounted at: `/api/v1/sap-simulator` (matches `nexus-backend/mcp_http_gateway.py` line 1542)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/status`                                   |  39 | 7 |
| GET    | `/load/status`                              |  53 | 7 |
| POST   | `/load`                                     |  59 | 7 |
| POST   | `/reset`                                    |  66 | 7 |
| GET    | `/objects`                                  |  73 | 7 |
| GET    | `/objects/{schema}/{table}`                 |  81 | 7 |
| GET    | `/objects/{schema}/{table}/columns`         |  94 | 7 |
| GET    | `/dump/status`                              | 117 | 7 |
| POST   | `/restart-pods`                             | 123 | 7 |
| GET    | `/health`                                   | 168 | 7 |

---

## External Source Simulator API

Source: [nexus-backend/src/apis/external_source_simulator_api.py](../../nexus-backend/src/apis/external_source_simulator_api.py)
Library target: `src/nexus_simulator/server/routers/external.py`
Mounted at: `/api/v1/external-simulator` (matches `nexus-backend/mcp_http_gateway.py` line 1550)

| Method | Path | Source line | Library phase |
|--------|------|-------------|---------------|
| GET    | `/status`                                   |  39 | 8 |
| GET    | `/load/status`                              |  45 | 8 |
| POST   | `/load`                                     |  51 | 8 |
| POST   | `/seed`                                     |  58 | 8 |
| POST   | `/reset`                                    |  65 | 8 |
| GET    | `/objects`                                  |  75 | 8 |
| GET    | `/objects/{schema}/{table}`                 |  83 | 8 |
| GET    | `/objects/{schema}/{table}/columns`         |  96 | 8 |
| GET    | `/health`                                   | 112 | 8 |
| POST   | `/upload/invoice`                           | 198 | 8 |
| POST   | `/upload/lab-report`                        | 203 | 8 |
| POST   | `/upload/contract`                          | 208 | 8 |
| POST   | `/upload/sustainability-report`             | 213 | 8 |

---

## Health and infra routes (library-native)

Not ported from nexus-backend; these belong to the reference server itself.

| Method | Path | Phase |
|--------|------|-------|
| GET    | `/health`                     | 0 (this pass) |
| GET    | `/readiness`                  | 0 (this pass) |
| GET    | `/version`                    | 0 (this pass) |

---

## Base paths

Nexus-backend mounts each simulator router under a fixed prefix in
[`mcp_http_gateway.py`](../../nexus-backend/mcp_http_gateway.py) lines 1508–1554.
The library's reference server mirrors those prefixes so UIs and MCP clients don't
need URL rewrites when a host app swaps in the library's routers:

| Plugin           | Prefix                          |
|------------------|---------------------------------|
| WXCC             | `/api/v1/simulator`             |
| SFDC             | `/api/v1/sfdc-simulator`        |
| Oracle ERP       | `/api/v1/oracle-erp-simulator`  |
| SAP              | `/api/v1/sap-simulator`         |
| External Source  | `/api/v1/external-simulator`    |
