# Simulator UI redesign (branch `ui-redesign`)

The front end was rebuilt on the Nexus design system used by the website and
the ontology product (graphite and blue, Geist fonts, the N logo, one icon family).

What changed: everything under `frontend/src`, plus `index.html`, `package.json`,
`package-lock.json`, the Tailwind/TypeScript/Vite config files and `public/favicon.svg`.

What did not change: the backend, `Dockerfile`, `nginx.conf`, the runtime
`/config.json`, routes (`/`, `/simulators/:id`, `/scenarios`, `/tables`, `/apis`,
`/settings`) and every backend endpoint the UI calls.

## Where things are

| Folder | What it holds |
| --- | --- |
| `src/services/api.ts` | Every backend call. Screens never call `fetch` directly. |
| `src/config/simulators.ts` | The nine systems: names, API roots, which actions each has. |
| `src/config/navigation.ts` | Sidebar, breadcrumbs, search palette. |
| `src/pages/` | One file per screen. |
| `src/components/sim/` | Table list, row viewer, backbone panel, preview. |
| `src/components/ds/`, `src/styles/` | Design system, copied from `nexus-ontology/frontend`. |
| `src/core/` | Small helpers. Named `core` because this repo's `.gitignore` ignores `lib/`. |

To add a system, add one entry to `SIMULATORS` in `src/config/simulators.ts`.

## Run locally

`npm install`, then `npm run dev` (port 5390). API calls go to
`VITE_PROXY_TARGET` from `.env.local`, default `http://localhost:8000`.

## Deploy (local k3s)

```
cd /opt/mycode/nexus/nexus-deployer/kube-operator
./deploy-app-changes.sh simulator --ui --env local --no-commit
```

## Roll back

```
k3s kubectl -n simulator-local set image deployment/simulator-local-frontend frontend=nexus-simulator-ui:0.1.27-67c11e7
```

The old front end is still on `main`.

## Not tested yet

Buttons that change data (Load, Seed, Reset, Generate, Seed all telecom,
scenario Run/Revert, vendor API write tests). They call the same endpoints as
before and ask for confirmation first.
