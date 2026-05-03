# Running the nexus-simulator test suite

The library is tested end-to-end **in complete isolation from nexus-backend
and AWS**. No credentials, no network, no Docker, no running service required.

## Quickstart

```bash
make install-venv
source .venv/bin/activate
make test          # unit only, <5s
make test-all      # every tier (unit + integration + contract + property + e2e + journeys + bdd + endurance-smoke)
make ci            # exact sequence CI runs
```

## Tier guide

| Directory | What it covers | Typical runtime | Marker |
|-----------|----------------|-----------------|--------|
| `tests/unit/`        | Pure-Python logic: config, errors, factory stub, registry, package structure | <2s   | none |
| `tests/integration/` | Moto + fakeredis-backed adapter behavior (S3, Redis)                          | <60s  | `integration` |
| `tests/contract/`    | Parametrized across adapters; same class runs against in-memory and moto      | <60s  | none |
| `tests/property/`    | Hypothesis state-machine tests for plugin lifecycle, FDW filters              | <60s  | none |
| `tests/e2e/`         | In-process `httpx.AsyncClient` against the FastAPI harness                    | <30s  | `e2e` |
| `tests/bdd/`         | behave features + steps, hits the same in-process harness                     | <2m   | `bdd` |
| `tests/endurance/`   | Concurrent load smoke against the in-process harness                          | <2m   | `heavy` opts out |
| `tests/journeys/`    | Exercises plugin-seed YAMLs through `SeedYAMLRunner`                          | <5s   | none |

Heavy endurance scenarios are tagged `@pytest.mark.heavy` and skipped by
`make test-endurance`; run `make test-endurance-full` or trigger the nightly
CI job to exercise them.

## Harness usage

The shipped harness (`nexus_simulator.testing`, lands in Phase 4) exposes
everything tests need:

```python
from nexus_simulator.testing import (
    SeedYAMLRunner,
    TestHttpClient,
    make_test_app,
    make_test_simulator,
)

# In-process FastAPI
app = make_test_app()
async with TestHttpClient(app) as client:
    resp = await client.get("/health")
    assert resp.status_code == 200

# Plugin-seed YAML end-to-end
runner = SeedYAMLRunner(app=app)
result = runner.run("tests/journeys/samples/wxcc-smoke.yaml")
print(result.summary())
```

Any repo installing `nexus-simulator[harness]` also picks up the pytest
fixtures automatically via the `pytest11` entry point. The relevant fixtures:
`simulator_config`, `simulator`, `app`, `http_client`, `mcp_client`,
`seed_runner`. Tier-specific fixtures add `s3_client`, `redis_client`,
`wxcc_bucket`, `sfdc_bucket`, `oracle_erp_bucket`, `sap_bucket`,
`external_bucket` (integration) and `sample_seed_path`,
`seed_samples_dir` (journeys).

## Running a seed YAML end-to-end

```bash
make seed                                                    # runs samples/wxcc-smoke.yaml
make seed SEED=tests/journeys/samples/sfdc-smoke.yaml
nexus-simulator run-seed path/to/custom.yaml                 # direct CLI
```

Phase-2 behavior: the runner validates YAML shape and prints a summary. Full
end-to-end execution (load plugin → seed data → query objects → verify
artifacts) activates in phases 5–8, alongside each plugin port.

## Adding a test

- Unit: drop a `test_*.py` into `tests/unit/`. Import from `nexus_simulator.*`
  directly. No fixtures from the harness are needed.
- E2E: use the `http_client` fixture and hit `/api/v1/...`. Expect 501 for
  routes whose activating phase has not landed yet.
- Contract: add your adapter's construction to the parametrized fixture in
  `tests/contract/conftest.py` and subclass the matching base in
  `tests/contract/base.py`. The same test class then runs against every
  adapter.
- BDD: add a `.feature` under `tests/bdd/features/` and step defs under
  `tests/bdd/steps/`. Use `context.loop.run_until_complete(context.client....)`
  to hit the in-process harness.
- Endurance: tag `@pytest.mark.heavy` if the test takes >5s; use `gather_n`
  from the endurance conftest for concurrency.
- Seed YAML: add a file under `tests/journeys/samples/`; it's picked up
  automatically by the parametrized `sample_seed_path` fixture.

## Migration from nexus-backend (per phase)

As each phase of the master extraction plan lands in nexus-backend's `stage`
branch, tests that exercised the moved functionality move here:

- Unit tests for plugin logic → `tests/unit/`
- HTTP endpoint tests → `tests/e2e/` (swap real HTTP for the in-process
  client; remove nexus-backend auth headers)
- BDD scenarios for plugin flows → `tests/bdd/features/`
- Endurance scenarios → `tests/endurance/`

Refer to `docs/ROUTE_PARITY.md` for the route inventory and phase mapping.

## Troubleshooting

- **moto version mismatch** — we pin `moto>=5.0` which uses the unified
  `@mock_aws`; 4.x-style per-service decorators won't work.
- **asyncio warnings** — `pyproject.toml` sets `asyncio_mode = "auto"`;
  plain `def test_...(http_client)` is enough for async tests.
- **fakeredis vs real Redis** — integration tests use `fakeredis`; the
  default `CacheBackend` adapter constructed by `build_simulator` falls back
  to fakeredis when ``redis_url`` is absent in the test config.
- **behave step discovery** — step modules must live under
  `tests/bdd/steps/`; behave finds them by filesystem layout.
- **hypothesis flakiness** — set `HYPOTHESIS_PROFILE=ci` for tighter
  determinism or `thorough` for deeper fuzzing.
