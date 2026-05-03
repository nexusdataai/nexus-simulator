# nexus-simulator

Pluggable simulator library extracted from `nexus-backend`.

Ships three things:

- A **library core** with a port-based `BaseSimulator` and a `SimulatorRegistry`
  plugin pattern. Five simulator plugins ship in-tree: WXCC (call/recordings),
  SFDC, Oracle ERP, SAP, External Source (Google Drive / Social Listening /
  uploads). Storage is via DynamoDB/S3/Redis default adapters; consumers can
  swap any port for a custom adapter.
- A **reference FastAPI + MCP server** (`nexus-simulator serve`) that composes
  the library into a standalone HTTP + MCP surface matching nexus-backend's
  existing simulator APIs 1:1.
- An **importable testing harness** (`nexus_simulator.testing`) that lets any
  consumer exercise the simulators in-process, including the WXCC seed
  workflow end-to-end, without a backend or AWS account.

## Status

**Pre-release (`0.1.0a1`).** The public API is not yet stable. Expect churn
during phases 2–9 of the extraction from
[`nexus-backend`](https://github.com/nexusdataai/nexus-backend) until `0.1.0`.

## Install

```bash
# From the internal Python index
pip install nexus-simulator

# Direct from GitHub (pin to a tag or main)
pip install "nexus-simulator @ git+https://github.com/nexusdataai/nexus-simulator.git@main"

# Editable, side-by-side with nexus-backend during development
pip install -e /path/to/nexus-simulator
```

Available extras:

```bash
pip install "nexus-simulator[aws]"      # boto3/botocore for the default adapters
pip install "nexus-simulator[redis]"    # redis-py for the cache adapter
pip install "nexus-simulator[server]"   # FastAPI + uvicorn + fastmcp + httpx
pip install "nexus-simulator[harness]"  # everything above + behave + pytest-benchmark
pip install "nexus-simulator[test,dev]" # full test + dev toolchain
```

## Package layout

```
src/nexus_simulator/
  config.py          # SimulatorConfig + per-plugin configs
  factory.py         # build_simulator(config)
  errors.py          # SimulatorError + subclasses
  registry.py        # SimulatorRegistry + register_simulator()
  contracts/         # Protocol ports (StorageBackend, CacheBackend, FDWQueryPort, RecordingsBackend)
  models/            # Shared pydantic models (FDW request/response, common types)
  base/              # BaseSimulator ABC (Redis-backed FDW core)
  plugins/
    wxcc/            # WXCC simulator (calls + recordings) + processor + models
    sfdc/            # SFDC simulator + models
    oracle_erp/      # Oracle ERP simulator + models
    sap/             # SAP simulator + models
    external_source/ # Google Drive / Social Listening / Uploads simulator
  adapters/          # DynamoDB, S3, Redis, in-memory shipped adapters
  server/            # Reference FastAPI app + per-plugin routers + MCP + CLI
  testing/           # make_test_app, SeedYAMLRunner, pytest fixtures plugin
```

## Quickstart — local reference server

```bash
make install-venv
source .venv/bin/activate
make serve                              # http://localhost:8002/health
```

Or via Docker:

```bash
make docker-build && make docker-run    # http://localhost:8000/health
```

Or docker-compose:

```bash
make compose-up
```

Routes return 501 until their owning phase of the extraction plan ports the
underlying plugin. See [docs/ROUTE_PARITY.md](docs/ROUTE_PARITY.md) for the
full inventory and phase mapping. Health, readiness, and version endpoints
are live today.

## Integration guidelines

`nexus-simulator` is designed to be embedded in five different shapes. Pick
the one that matches your host application; the underlying core is the same.

| Mode | Best for | Install | Coupling |
|------|----------|---------|----------|
| 1. Embed as a Python library | Apps that already host their own framework and want direct simulator calls | `nexus-simulator[aws,redis]` | Tightest — single process |
| 2. Mount the FastAPI routers in your app | Apps using FastAPI that want the simulator HTTP surface "for free" | `nexus-simulator[server,aws,redis]` | Same process, separate URL prefix |
| 3. Run as an independent pod / microservice | Polyglot fleets, language-agnostic clients, multi-tenant isolation | Docker image / `[server]` extra | HTTP boundary |
| 4. Connect via MCP | LLM clients (Claude Desktop, Cursor, custom MCP hosts) | `[server]` extra (phase 5+) | stdio / HTTP MCP |
| 5. Use the harness in your own tests | Anyone — the harness is import-safe at any time | `nexus-simulator[harness]` | Test-time only |

Modes 1 + 5 are usable today. Mode 2 is usable today but the routers return
501 until phases 5–8 land. Mode 3 follows mode 2. Mode 4 activates in
phase 5 (WXCC) and grows per phase.

### Mode 1 — Embed as a Python library

For apps that want to call simulators directly without HTTP overhead.

```python
# your_app/bootstrap.py
from nexus_simulator import build_simulator
from nexus_simulator.config import (
    SimulatorConfig,
    WXCCPluginConfig,
    SFDCPluginConfig,
    OracleERPPluginConfig,
    SAPPluginConfig,
    ExternalSourcePluginConfig,
)

config = SimulatorConfig(
    region="us-east-1",
    role_arn="arn:aws:iam::123456789012:role/your-simulator-role",
    redis_url="redis://localhost:6379/0",
    wxcc=WXCCPluginConfig(
        bucket="prod-wxcc-simulator",
        prefix="wxcc-simulator",
        org_id="sim-org-001",
    ),
    sfdc=SFDCPluginConfig(bucket="prod-sfdc-simulator", prefix="sfdc-simulator"),
    oracle_erp=OracleERPPluginConfig(bucket="prod-oracle-simulator", prefix="oracle-simulator"),
    sap=SAPPluginConfig(bucket="prod-sap-simulator", prefix="sap-simulator"),
    external_source=ExternalSourcePluginConfig(bucket="prod-external-simulator", prefix="external-simulator"),
)

sim = build_simulator(config)

# Once phases 5+ land, plugins become available:
#   await sim.wxcc.seed_data(SeedDataRequest(num_tasks=20))
#   await sim.sfdc.list_foreign_servers()
#   await sim.oracle_erp.execute_query(...)
```

Custom plugins register at startup via the simulator registry (activates
phase 1):

```python
from nexus_simulator.registry import register_simulator
from your_app.simulators import MyCustomSimulator

register_simulator("my_custom", lambda cfg: MyCustomSimulator(cfg))
```

### Mode 2 — Mount the FastAPI routers in your app

For host apps that already run FastAPI (e.g. nexus-backend itself in
phase 9+). Use the library's routers under their canonical prefixes;
add your own auth, rate-limiting, and observability middleware on top.

```python
# your_app/main.py
from fastapi import FastAPI

from nexus_simulator import build_simulator
from nexus_simulator.config import SimulatorConfig
from nexus_simulator.server.app import (
    WXCC_PREFIX,
    SFDC_PREFIX,
    ORACLE_ERP_PREFIX,
    SAP_PREFIX,
    EXTERNAL_PREFIX,
)
from nexus_simulator.server.routers import (
    health,
    wxcc,
    sfdc,
    oracle_erp,
    sap,
    external,
)

app = FastAPI(title="Your App")

# Your own auth middleware FIRST — the library does not ship auth
app.add_middleware(YourCognitoAuthMiddleware)

# Then mount the simulator routers
app.include_router(health.router, tags=["health"])
app.include_router(wxcc.router,        prefix=WXCC_PREFIX,        tags=["WXCC Simulator"])
app.include_router(sfdc.router,        prefix=SFDC_PREFIX,        tags=["SFDC Simulator"])
app.include_router(oracle_erp.router,  prefix=ORACLE_ERP_PREFIX,  tags=["Oracle ERP Simulator"])
app.include_router(sap.router,         prefix=SAP_PREFIX,         tags=["SAP Simulator"])
app.include_router(external.router,    prefix=EXTERNAL_PREFIX,    tags=["External Simulator"])

@app.on_event("startup")
async def _wire_simulator() -> None:
    app.state.simulator = build_simulator(SimulatorConfig(...))
```

The reference server's `create_app(simulator)` does the same wiring for you
if you don't need to interleave with other routers — see
`nexus_simulator.server.create_app`.

### Mode 3 — Run as an independent pod / microservice

Already wired end-to-end. Build the image, deploy the manifests, talk to it
over HTTP. See the [Deployment as an independent pod](#deployment-as-an-independent-pod)
section below. Calls from another service:

```python
import httpx

SIM = "http://nexus-simulator.nexus-simulator.svc.cluster.local:8000"

async def get_wxcc_status() -> dict:
    async with httpx.AsyncClient(base_url=SIM) as client:
        resp = await client.get("/api/v1/simulator/admin/status")
        resp.raise_for_status()
        return resp.json()
```

Health probes for Kubernetes / your load balancer:

| Endpoint     | Use as                |
|--------------|-----------------------|
| `/health`    | liveness probe        |
| `/readiness` | readiness probe       |
| `/version`   | deployment audit      |

### Mode 4 — Connect via MCP

When phase 5 lands, the same library backs an MCP server exposing the
`wxcc_simulator_tool` tool (1:1 schema parity with nexus-backend so existing
MCP clients work unchanged):

```bash
# stdio (Claude Desktop, Cursor)
nexus-simulator serve --mcp-stdio

# HTTP MCP (other hosts)
nexus-simulator serve --mcp-http --port 9001
```

Configure your MCP client to invoke the binary or hit the HTTP endpoint
exactly as it would for nexus-backend's MCP server today.

### Mode 5 — Use the harness in your own tests

Any project depending on `nexus-simulator[harness]` automatically picks up
the shipped pytest fixtures (registered via the `pytest11` entry point):

```python
# your_project/tests/test_my_seed.py
import pytest

@pytest.mark.asyncio
async def test_my_wxcc_seed_runs(http_client, seed_runner, samples_dir):
    # 1. Hit the in-process FastAPI harness
    health = await http_client.get("/health")
    assert health.status_code == 200

    # 2. Run a plugin-seed YAML end-to-end (phase 5+)
    result = seed_runner.run(samples_dir / "wxcc-smoke.yaml")
    assert result.ok
```

The harness factories are also usable directly (no pytest required):

```python
from nexus_simulator.testing import (
    SeedYAMLRunner,
    TestHttpClient,
    make_test_app,
    make_test_simulator,
)

app = make_test_app()
async with TestHttpClient(app) as client:
    resp = await client.get("/api/v1/simulator/admin/status")
```

`TestHttpClient(base_url="https://nexus-simulator-dev....")` works the same
way against a real deployed pod, so the same test code runs in-process for
CI and against staging for smoke checks.

### Configuration contract

All configuration flows through `SimulatorConfig`
([src/nexus_simulator/config.py](src/nexus_simulator/config.py)). The library
never reads environment variables itself; consumers build the dataclass from
whichever source they prefer (env, SSM, Secrets Manager, Kubernetes ConfigMap,
app config file).

The reference server's CLI does read env vars as a convenience; the
authoritative names are:

| Env var | SimulatorConfig field | Required by phase |
|---------|----------------------|-------------------|
| `AWS_REGION`                       | `region`                          | 3+ |
| `AWS_ROLE_ARN`                     | `role_arn`                        | optional |
| `REDIS_URL`                        | `redis_url`                       | 3+ (optional fallback to in-memory) |
| `WXCC_SIMULATOR_BUCKET`            | `wxcc.bucket`                     | 5 |
| `WXCC_SIMULATOR_PREFIX`            | `wxcc.prefix`                     | 5 |
| `WXCC_SIM_ORG_ID`                  | `wxcc.org_id`                     | 5 |
| `WXCC_SIM_TOKEN`                   | `wxcc.bearer_token`               | 5 (host-side auth check) |
| `SFDC_SIMULATOR_BUCKET`            | `sfdc.bucket`                     | 6 |
| `ORACLE_ERP_SIMULATOR_BUCKET`      | `oracle_erp.bucket`               | 7 |
| `SAP_SIMULATOR_BUCKET`             | `sap.bucket`                      | 7 |
| `EXTERNAL_SIMULATOR_BUCKET`        | `external_source.bucket`          | 8 |

Until a phase activates, its env vars are **not** required. The reference
server starts cleanly with zero AWS configuration today (routes 501).

### Choose your storage adapters

The shipped adapters live under `src/nexus_simulator/adapters/` and are
selected via `build_simulator(...)` overrides (lands in phase 3):

- **DynamoDB + S3 + Redis (default).** Enable `[aws,redis]` extras; pass real
  bucket/table names in `SimulatorConfig`. Item layout matches nexus-backend
  so no data migration is needed when swapping the backend in phase 9.
- **In-memory.** Used by the harness; suitable for tests and local prototyping.
  No AWS or Redis dependency.
- **Custom.** Implement the Protocols in `nexus_simulator.contracts` and
  inject them into `build_simulator` (e.g. Postgres-backed `StorageBackend`,
  filesystem `RecordingsBackend`, Memcached `CacheBackend`). Each port is small
  (5–10 methods) and documented in the module docstring once it lands.

### Auth, observability, multi-tenancy

These are intentionally **out of scope** for the library:

- **Auth.** No middleware. Add Cognito / OAuth / RBAC in your host app
  (mode 2) or as an ingress concern (mode 3). The library trusts the caller.
  The WXCC `Bearer` token check used today by `wxcc_simulator_api.verify_auth`
  is reproduced in `plugins/wxcc/auth.py` as an opt-in dependency the host can
  attach.
- **Multi-tenancy.** Plugin keys do not include a tenant prefix. If you need
  hard tenant isolation, prefix `org_id` in your host app before calling the
  library, or supply a tenant-aware adapter via the custom-adapter route.
- **Observability.** The library logs via `loguru`. Wire your tracer / metrics
  / log shipper in the host process; the library makes no global modifications.

### Versioning policy

- `0.1.0a1` ... `0.1.0aN` during phases 2–9. Pin to git `main` or to a
  specific alpha tag.
- `0.1.0` once the route surface and contracts stabilize. Semver from then on.
- Pre-1.0 minor releases may make backwards-incompatible changes. Pin
  exactly until 1.0.

A consumer-facing `CHANGELOG.md` lands at the first stable release; until
then the master extraction plan and this README are authoritative.

### Stability matrix (today)

| Surface | Stability |
|---------|-----------|
| `SimulatorConfig` field names                       | Stable |
| `SimulatorError` hierarchy                          | Stable |
| Package import paths under `nexus_simulator.*`      | Stable |
| `nexus_simulator.server.create_app` signature       | Stable |
| Testing harness public API                          | Stable for the alpha series |
| Plugin method signatures                            | In flux (lands phases 5–8) |
| Adapter constructor signatures                      | In flux (lands phase 3) |
| `SimulatorRegistry` contract                        | In flux (lands phase 1) |
| MCP tool schemas                                    | Locked to nexus-backend's; activate phase 5 |

## Testing

The library is tested in complete isolation from nexus-backend and AWS — no
credentials, no network, no backend process required. See
[tests/README.md](tests/README.md) for the full tier guide.

```bash
make install-venv && source .venv/bin/activate
make test                # unit tests (<5s)
make test-all            # every tier (unit + integration + contract + property + e2e + journeys + bdd + endurance-smoke)
make coverage            # branch coverage with a 60% floor (ratcheting up per phase)
make seed                # run a sample plugin-seed YAML end-to-end
```

Tiered test directories:

- `tests/unit/`        fast Python-only tests
- `tests/integration/` moto-backed AWS adapter tests + fakeredis
- `tests/contract/`    parametrized across adapter implementations
- `tests/property/`    hypothesis state-machine tests
- `tests/e2e/`         in-process `httpx.AsyncClient` against the reference FastAPI app
- `tests/bdd/`         behave scenarios against the in-process harness
- `tests/endurance/`   concurrent load smoke (heavy scenarios opt-in)
- `tests/journeys/`    plugin-seed YAMLs exercised end-to-end

## Deployment as an independent pod

The reference server is packaged for Kubernetes. Manifests under
[deploy/k8s/](deploy/k8s/) provide a production-shaped Deployment + Service +
HPA + NetworkPolicy + ServiceAccount; the Dockerfile produces a <130MB
non-root image matching nexus-ai-engine's conventions (python:3.12-slim, uid
1001, healthcheck on `/health`).

```bash
make docker-build
make k8s-apply             # kubectl apply -k deploy/k8s/
make k8s-smoke             # port-forward + curl /health
```

A GitHub Actions workflow
([`.github/workflows/deploy-eks.yml`](.github/workflows/deploy-eks.yml))
builds and pushes to ECR, then applies the manifests to the target EKS
cluster. It reuses nexus-backend's AWS infra — `AWS_ROLE_TO_ASSUME_DEV`,
cluster `nexus-dev`, region `us-east-1` — and deploys into the new namespace
`nexus-simulator`. See [deploy/k8s/README.md](deploy/k8s/README.md) for
the complete checklist of AWS resources required before a live deploy.

## Development

```bash
make install-venv         # create .venv and install with all extras
source .venv/bin/activate
make watch                # TDD watch mode on unit tests
make lint                 # ruff
make typecheck            # mypy
make all                  # pre-push gate: clean + lint + typecheck + test-all + coverage + build
```

## License

MIT. See [LICENSE](LICENSE).
