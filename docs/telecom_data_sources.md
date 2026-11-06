# Telecom Data Sources for Customer Intelligence Use Cases

How each data source contributes to four customer intelligence use cases:

- **Churn propensity:** will this customer leave in the next 30 to 90 days?
- **Upsell / offer response:** will they accept a plan upgrade?
- **Usage-decline risk:** is this customer's usage likely to keep dropping?
- **Anomaly detection:** is this customer's behaviour unusual compared with similar customers? (no labels needed)

**Legend:** ● strong signal · ○ supporting signal · blank = little or no relevance

**Origin systems:**
- **BSS** (Business Support Systems): CRM, billing, charging, orders
- **OSS** (Operations Support Systems): fault, performance and configuration management, trouble tickets
- **NSS** (Network Switching Subsystem / core network): HLR/HSS/UDM, MSC, MME/AMF, PCRF/PCF, IMS

## Data sources

| Origin | Data source | Typical grain | Example signals | Churn | Upsell | Usage decline | Anomaly |
|---|---|---|---|---|---|---|---|
| **BSS** | CRM / customer profile | 1 row per customer | Tenure, segment, region, family/business account | ● | ● | ○ | ○ |
| **BSS** | Subscription & plan history | 1 row per plan change | Downgrades, upgrades, add-ons dropped | ● | ● | ● | ○ |
| **BSS** | Contract / lock-in | 1 row per contract | Contract end date, device instalments left | ● | ● | | |
| **BSS** | Billing / invoices | 1 row per invoice per month | Bill amount trend, bill shock | ● | ○ | ○ | ● |
| **BSS** (OCS/charging) | Prepaid recharges | 1 row per recharge | Recharge gaps, smaller top-ups | ● | ○ | ● | ● |
| **BSS** | Payments & collections | 1 row per payment | Late or failed payments, dunning stage | ● | ○ | | ● |
| **BSS** | Customer care interactions | 1 row per call/chat/ticket | Repeat contacts, unresolved complaints | ● | ○ | ○ | ● |
| **BSS** | Billing disputes & credits | 1 row per dispute | Disputes raised, refunds issued | ● | | | ● |
| **BSS** | MNP / port-out requests | 1 row per request | Porting code requested | ● | | | ● |
| **BSS** | Campaign & offer history | 1 row per offer | Offers accepted, ignored; contact fatigue | ○ | ● | | |
| **BSS** | VAS / OTT bundles | 1 row per subscription | Streaming bundles, cancelled add-ons | ● | ● | ○ | |
| **BSS** | Retail / store visits | 1 row per visit | Store visits, SIM replacements | ○ | ● | | ○ |
| **BSS** + NSS | SIM swap events | 1 row per event | Unusual SIM swaps | | | | ● |
| **NSS** (MSC, SGW/PGW, SMF) | Usage records (CDRs / data sessions) | 1 row per call or session | Voice minutes, data GB, SMS trend | ● | ● | ● | ● |
| **NSS** (HLR/HSS/UDM) | Subscriber network profile | 1 row per subscriber | Service barring, provisioning status, roaming enabled | ● | ○ | ● | ● |
| **NSS** (MME/AMF) | Attach / registration failures | 1 row per signaling event | Failed attaches, registration rejects | ● | | ● | ● |
| **NSS** (MME/AMF) | Location / home cell | Per subscriber per day | Home or work cell, recent move | ● | | ● | ○ |
| **NSS** (EIR) | Device / IMEI changes | 1 row per device change | Handset age, 5G capable, non-operator device | ● | ● | ● | ○ |
| **NSS** (IMS) | VoLTE / VoWiFi call failures | 1 row per failed call | VoLTE drops, setup failures | ● | | ● | ● |
| **NSS** (PCRF/PCF) | Policy / throttling events | 1 row per policy event | Fair-usage limit hit, speed throttled | ● | ● | ● | ○ |
| **NSS** (SMSC, USSD) | Messaging / USSD logs | 1 row per message | Balance checks, USSD menu usage | ○ | ○ | ○ | ○ |
| **NSS** (TAP via BSS) | Roaming usage | 1 row per session | Travel patterns, roaming bill shock | ○ | ● | ○ | ● |
| **NSS / OSS** (probes, DPI) | App usage mix | Per subscriber per day | Video, social, gaming share | ○ | ● | ○ | ● |
| **NSS / OSS** (probes) | Per-subscriber QoE | Per subscriber per day | Throughput, latency, video stalls as experienced | ● | ○ | ● | ● |
| **NSS / OSS** | Dual-SIM indicators (derived) | Per subscriber per period | Traffic moving to another SIM | ● | | ● | ○ |
| **OSS** (fault management) | Network alarms | 1 row per alarm | Cell or site down, severity, duration | ● | | ● | ● |
| **OSS** (performance management) | Cell KPIs / counters | Per cell per 15 min | Drop rate, congestion, PRB utilisation, throughput | ● | ○ | ● | ● |
| **OSS** | Network events | 1 row per dropped call/outage per cell | Dropped-call clusters | ● | | ● | ● |
| **OSS** (configuration management) | Network config changes | 1 row per change | Antenna tilt change, site decommissioned | ○ | | ● | ● |
| **OSS** | Planned maintenance / outages | 1 row per window | Scheduled downtime by area | ○ | | ● | ○ |
| **OSS** | Network trouble tickets | 1 row per incident | Incident type, time to resolve | ● | | ● | ○ |
| **OSS** | Transport / backhaul faults | 1 row per fault | Fibre cuts, microwave link failures | ○ | | ● | ● |
| **Digital channels** | App / web engagement | 1 row per session | Cancellation page visits, plan comparisons | ● | ● | ○ | ○ |
| **External / CX** | Surveys / NPS | 1 row per response | Detractor scores, verbatims | ● | ● | | |
| **External** | Credit / KYC | 1 row per customer | Credit band, verification status | ○ | ● | | |
| **External** | Competitor / market data | Per region per month | Competitor offers, new network launches | ● | ○ | ○ | |
| **Derived** (from CDRs) | Call graph | Subscriber pairs | Contacts who recently churned | ● | ○ | | ○ |

## Key notes

1. **OSS data is per cell, not per subscriber.** Alarms, KPIs and config changes describe network elements. To use them for a customer, join through the subscriber's home or most-used cells (from NSS location data) and matching time windows. This mapping should be a shared data-preparation step that all agents reuse rather than rebuild.

2. **OSS and NSS sources answer the "why" in the usage-decline mission.** The strongest evidence that network experience explains a decline:
   - per-subscriber QoE degradation;
   - alarms or outages on the customer's home cell during the decline window;
   - throttling events (a decline caused by a fair-usage limit is not a network problem);
   - planned maintenance (likely a temporary decline);
   - config changes such as an antenna tilt (can cause a sudden, lasting coverage loss).

3. **Volumes differ hugely.** PM counters and probe data can reach billions of rows per day, while alarms and tickets are far smaller. Pre-aggregate per cell per day before joining to a 40M-subscriber base.

4. **Strongest churn signals** are usually port-out requests, contract end dates, complaints and recharge gaps. A usage decline alone is a weaker signal, and must not be presented as a churn probability or proof of cause.

5. **Privacy and governance.** Location, call graph, credit data and survey verbatims carry consent and regulatory constraints (for example India's DPDP Act). They should be tenant-configurable and access-controlled, not used by default.

6. **Origin labels vary by operator.** The OCS is sometimes classed under NSS, and probe/DPI platforms may sit under OSS or NSS depending on the vendor. Treat the Origin column as the typical origin.

---

## Customer golden table (one row per subscriber)

**Grain:** one current snapshot row per eligible subscriber (typically daily refresh). This is the shared artefact agents read for whole-base screening; expensive joins from BSS/OSS/NSS happen here once, not per agent.

**Primary key:** `customer_id` (same as CRM `subscriber_id` / billing account key in most operators).

**Assessment alignment:** supports the usage-decline mission (cheap deterministic scan → shortlist → selective reasoning), preserves full-base coverage, separates **usage decline** from **validated churn probability**, and carries evidence fields for “network vs policy vs commercial” explanations.

### Field groups

| Group | Fields | Rolled up from (see table above) | Primary use cases |
| --- | --- | --- | --- |
| **Keys & snapshot** | `customer_id`, `tenant_id`, `snapshot_date`, `updated_at`, `is_eligible` | CRM + refresh job | All |
| **Profile & commercial** | `account_type`, `segment`, `region_code`, `tenure_months`, `plan_name`, `plan_tier`, `plan_data_quota_gb`, `monthly_spend`, `contract_end_date`, `days_to_contract_end` | CRM, subscription, contract, billing | Churn, upsell, ranking |
| **Usage (current vs prior window)** | `usage_current_gb`, `usage_prior_gb`, `usage_voice_mins_current`, `usage_voice_mins_prior`, `roaming_gb_30d` | CDR / session aggregates | Usage decline, anomaly, upsell |
| **Billing & prepaid behaviour** | `bill_amount_current`, `bill_amount_prior`, `bill_shock_flag`, `recharge_gap_days`, `payment_failures_30d`, `dunning_stage`, `plan_change_90d` | Billing, payments, recharges, plan history | Churn, usage decline |
| **Network experience (subscriber-facing)** | `network_issues_30d`, `network_issue_flag`, `dropped_calls_30d`, `volte_failures_30d`, `attach_failures_30d`, `qoe_score_current`, `qoe_score_prior`, `qoe_delta` | NSS events, IMS, probes (QoE) | Usage decline “why”, anomaly |
| **Network context (cell-mapped OSS)** | `home_cell_id`, `cell_outage_hours_30d`, `cell_alarm_count_30d`, `maintenance_hours_30d`, `cell_config_change_flag` | Location + OSS alarms/PM/maintenance/config | Usage decline “why” |
| **Policy (not network fault)** | `throttling_events_30d`, `fair_usage_limit_hit_flag` | PCRF/PCF | Explains decline without blaming radio |
| **Care & intent** | `care_contacts_30d`, `open_complaints`, `port_out_request_flag`, `sim_swap_events_30d` | Care, MNP, SIM swap | Churn, anomaly |
| **Digital & campaigns** | `app_sessions_30d`, `cancellation_page_visits_30d`, `offers_sent_90d`, `offers_accepted_90d` | App/web, campaign history | Churn, upsell |
| **Peer context (anomaly)** | `cohort_key`, `usage_vs_cohort_zscore` | Derived from segment + region cohort | Anomaly |
| **Governance (optional, tenant-gated)** | `credit_band`, `nps_last_score`, `consent_marketing`, `consent_location` | External / surveys | Upsell, regulated features |

**Derived at scan time (not stored, or stored in a sidecar):** `usage_decline_pct`, `priority_score`, LLM narrative — keeps golden table stable and auditable.

**Do not store by default:** raw CDRs, per-session probe rows, or unvalidated `churn_probability` from an ad-hoc prompt. If a model score is added, use `churn_model_score` + `churn_model_version` with training snapshot date.

### Column dictionary (recommended types)

| Column | Type | Description |
| --- | --- | --- |
| `customer_id` | string | Unique subscriber identifier |
| `tenant_id` | string | Operator / MVNO for isolation |
| `snapshot_date` | date | Business date this row represents |
| `updated_at` | datetime | Row version for incremental refresh & dedupe |
| `is_eligible` | boolean | In base for agent run (active, not excluded by policy) |
| `account_type` | enum | `prepaid` \| `postpaid` |
| `segment` | enum | `consumer` \| `sme` \| `enterprise` |
| `region_code` | string | Circle / state / market |
| `tenure_months` | int | Months since activation |
| `plan_name` | string | Commercial plan label |
| `plan_tier` | string | e.g. `299`, `499`, `999` for ranking |
| `plan_data_quota_gb` | float | Included data allowance |
| `monthly_spend` | float | ARPU / last invoice or recharge run-rate |
| `contract_end_date` | date | Nullable if no contract |
| `days_to_contract_end` | int | Nullable; strong churn signal when low |
| `usage_current_gb` | float | Data usage in current window (e.g. last 30d) |
| `usage_prior_gb` | float | Data usage in prior window |
| `usage_voice_mins_current` | float | Voice minutes current window |
| `usage_voice_mins_prior` | float | Voice minutes prior window |
| `roaming_gb_30d` | float | Roaming data volume |
| `bill_amount_current` | float | Last bill or cycle charge |
| `bill_amount_prior` | float | Previous cycle |
| `bill_shock_flag` | boolean | Bill up sharply vs prior |
| `recharge_gap_days` | int | Days since last recharge (prepaid); null postpaid |
| `payment_failures_30d` | int | Failed payment count |
| `dunning_stage` | int | 0=none, higher=collections |
| `plan_change_90d` | enum | `upgrade` \| `downgrade` \| `none` |
| `network_issues_30d` | int | Count of network-related incidents (tickets + drops cluster) |
| `network_issue_flag` | boolean | True if issues exceed tenant threshold |
| `dropped_calls_30d` | int | Dropped call count |
| `volte_failures_30d` | int | VoLTE/VoWiFi setup or drop failures |
| `attach_failures_30d` | int | Registration/attach failures |
| `qoe_score_current` | float | 0–100 experienced quality (probe-derived) |
| `qoe_score_prior` | float | Prior window QoE |
| `qoe_delta` | float | `current − prior` (negative = worsening) |
| `home_cell_id` | string | Primary serving cell for OSS joins |
| `cell_outage_hours_30d` | float | Outage duration on home cell in window |
| `cell_alarm_count_30d` | int | Alarms on home cell |
| `maintenance_hours_30d` | float | Planned maintenance on home cell |
| `cell_config_change_flag` | boolean | Config change on home cell in window |
| `throttling_events_30d` | int | Policy throttle events |
| `fair_usage_limit_hit_flag` | boolean | FUP/limit hit (decline may be policy-driven) |
| `care_contacts_30d` | int | Care interactions |
| `open_complaints` | int | Unresolved complaints |
| `port_out_request_flag` | boolean | MNP port-out initiated |
| `sim_swap_events_30d` | int | SIM swap count |
| `app_sessions_30d` | int | App logins/sessions |
| `cancellation_page_visits_30d` | int | Digital cancellation intent |
| `offers_sent_90d` | int | Campaign offers delivered |
| `offers_accepted_90d` | int | Offers accepted |
| `cohort_key` | string | e.g. `consumer\|MH\|post499` for peer stats |
| `usage_vs_cohort_zscore` | float | Standardised vs cohort median usage |
| `churn_model_score` | float | Optional; only if model registered — **not** a LLM guess |
| `churn_model_version` | string | Optional model artefact id |

### Sample rows (illustrative)

Compact view for docs; full generator output lives under `examples/data/`.

| customer_id | account_type | plan_name | tenure_months | usage_current_gb | usage_prior_gb | monthly_spend | network_issues_30d | network_issue_flag | throttling_events_30d | fair_usage_limit_hit_flag | qoe_delta | port_out_request_flag | plan_change_90d | usage_vs_cohort_zscore | updated_at |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- | --- | ---: | --- |
| S001 | postpaid | Postpaid 499 | 26 | 4.1 | 12.3 | 499 | 7 | true | 0 | false | -18.2 | false | none | -2.4 | 2026-10-28 |
| S002 | prepaid | Prepaid 299 | 8 | 15.0 | 14.2 | 299 | 0 | false | 0 | false | 0.5 | false | none | 0.1 | 2026-10-29 |
| S003 | postpaid | Postpaid 999 | 14 | 2.0 | 28.0 | 999 | 1 | false | 12 | true | -4.0 | false | downgrade | -1.8 | 2026-10-29 |
| S004 | postpaid | Postpaid 499 | 38 | 9.5 | 10.1 | 499 | 2 | false | 0 | false | -1.0 | true | none | -0.3 | 2026-10-27 |

**How these rows support agents**

- **S001** — Classic assessment candidate: large usage drop + network signals + QoE worsening → prioritise for review; LLM explains evidence, does not invent churn probability.
- **S002** — Stable usage; whole-base scan passes without shortlist.
- **S003** — Usage drop with **FUP/throttling**; mission logic should label `likely_factor=policy`, not radio fault.
- **S004** — Moderate usage change but **port-out** and tenure/plan context → churn workflow, not usage-decline primary.

### Refresh & quality rules (shared pipeline)

- **Dedupe:** one row per `customer_id`; keep latest `updated_at` (handles duplicate feeds).
- **Incremental:** merge changed batch by `customer_id`; full rebuild weekly or on schema change.
- **Nulls:** missing usage → exclude from decline % but keep in coverage counts; impute only with documented defaults.
- **Traceability:** persist `snapshot_date`, source batch ids, and cell-mapping version used for OSS fields.

---

## Implemented in nexus-simulator

The **default** telecom product surface is three FDW plugins: **BSS**, **NSS**, and **OSS**. They share `plugins/telco_seed_pools.py` for deterministic subscriber/cell identity and implement **Telco AI Backbone** generation: Table / File / API / Stream shapes aligned with [`data/Telco-Data/samples.js`](../data/Telco-Data/samples.js) (fixtures in [`src/nexus_simulator/data/telco/sample_fixtures.json`](../src/nexus_simulator/data/telco/sample_fixtures.json); regenerate with `node scripts/export_telco_samples_fixtures.js`).

| Plugin | Legacy schema (normalized) | Atlas backbone schema | API prefix | Registry key |
| --- | --- | --- | --- | --- |
| BSS | `bss_crm` | `telco_atlas_bss` | `/api/v1/bss-simulator` | `bss` |
| NSS | `nss_core` | `telco_atlas_nss` | `/api/v1/nss-simulator` | `nss` |
| OSS | `oss_network` | `telco_atlas_oss` | `/api/v1/oss-simulator` | `oss` |

**Backbone APIs (per layer):** `GET /api/v1/{bss|nss|oss}-simulator/backbone/catalog`, `POST .../backbone/generate`, `GET .../backbone/artifacts`, `GET .../backbone/files`, `GET .../backbone/file?path=...`, SSE `GET .../backbone/stream/{topic}`. The reference atlas HTML is served at `/telco-atlas/`.

**Ordered seed:** `POST /api/v1/telco/seed-all` runs **BSS → NSS → OSS** by default. Optional query params `include_golden=true` and/or `include_sources=true` add `telco_golden` and/or `telco_sources` when those plugins are enabled in config.

**Env knobs:** `TELCO_SUBSCRIBERS` (default 500), `TELCO_CELLS` (100), `TELCO_HISTORY_DAYS` (60), `TELCO_SEED` (42). Plan-scale demo: `TELCO_SUBSCRIBERS=5000 TELCO_CELLS=500 TELCO_HISTORY_DAYS=90`. Disable layers with `BSS_SIMULATOR_ENABLED=false` (and NSS/OSS equivalents).

**FDW:** `GET /api/fdw/tables?source=bss|nss|oss` (plus `telco_golden` or `telco_sources` when registered).

**TMF index:** merged from backbone generation across the three layers; `GET /tmf-api/*` resolves stored bodies.

**Scenarios:** `telco.usage-decline`, `telco.churn-portout`, `telco.upsell-ready`, `telco.policy-throttle` under `scenarios/catalog/telco-customer-intelligence.yaml`. The `source-outage` step calls `seed_scenario("outage_backhaul")` on **OSS** or **NSS** (or legacy `telco_sources` when present).

### Optional legacy plugins

| Plugin | When enabled | Notes |
| --- | --- | --- |
| **Telco Golden** | `TELCO_GOLDEN_SIMULATOR_ENABLED=true` (CLI) | `telco_intelligence` rollup in `telco_golden/rollup.py`; admin at `/api/v1/telco-golden-simulator`. |
| **Telco Sources** | `TELCO_SOURCES_SIMULATOR_ENABLED=true` | Standalone `/api/v1/telco-sources/*` profile + generate; same pool-driven identity as backbone. |

Atlas catalog for legacy sources: [`data/telco/atlas_catalog.json`](../data/telco/atlas_catalog.json) (regenerate via `scripts/export_telco_atlas.py`).
