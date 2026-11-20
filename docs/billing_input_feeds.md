# Billing input feeds (simulator) vs final Kenan tables (ontology)

## Split of responsibility

| Layer | Responsibility |
|---|---|
| **Nexus Simulator** | Generates **inbound billing feeds** from BSS, OSS, and NSS: atlas tables, legacy CRM/charging tables, backbone **files**, **vendor APIs**, and **streams** tagged `billing_input`. |
| **Nexus Ontology ETL** | Ingests those feeds and **hydrates final Kenan BP tables** (CMF, CDR_DATA, BILL_INVOICE, BMF, …). |

Reference definitions live in `data/Telco-Data/kenan.html` / `kenan.js` (inbound feeds + final tables).

## API

- `POST /api/v1/telco/seed-billing` — seeds billing **input** families on BSS → NSS → OSS (`TELCO_BACKBONE_PROFILE=billing` by default).
- `GET /api/v1/telco/billing` — returns `input_feeds` (from `billing_feeds.json`) with linked live `artifacts`, plus flat lists of tables/files/APIs/streams.

`ontology_lands_in` on each feed documents where Ontology ETL lands data; the simulator does **not** create those tables by default.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `TELCO_BACKBONE_PROFILE` | `billing` | Limit backbone generation to billing-relevant atlas families. |