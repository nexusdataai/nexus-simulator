/**
 * All calls to the nexus-simulator backend live here. Screens never call
 * fetch directly, so a change in the API is a change in one file.
 *
 * The API base comes from /config.json (api.baseUrl), the same file the
 * previous front end read, so deployment does not change.
 */

/* ------------------------------------------------------------------ types */

export interface SimStatus {
  service?: string;
  enabled: boolean;
  loaded: boolean;
  bucket?: string;
  prefix?: string;
  table_data_prefix?: string;
  files_data_prefix?: string;
  schema?: string;
  table_count: number;
  tables_with_data: number;
  total_rows: number;
  file_count: number;
  api_count: number;
  stream_count: number;
  dump_timestamp?: string | null;
  last_loaded?: string | null;
  backbone_run_id?: string | null;
  backbone_generated_at?: string | null;
  vendor_label?: string | null;
  vendor_code?: string | null;
  /** External sources: feed item count (social listening). */
  social_item_count?: number;
  /** External sources: per-source counts (files or feed). */
  source_counts?: Record<string, number>;
  mapping_table_count?: number;
}

export interface ExternalSourceDef {
  id: string;
  name: string;
  description: string;
  file_count: number;
  feed_count: number;
}

export interface ExternalArtifactFile {
  name: string;
  path: string;
  source_id: string;
  source_label?: string;
  kind?: string;
  table?: string;
  id?: string;
  size_kb?: number;
  metadata?: Record<string, unknown>;
}

export interface SocialFeedItem {
  id: string;
  source_id: string;
  kind: string;
  table?: string;
  title: string;
  summary: string;
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TableRef {
  schemaName: string;
  tableName: string;
  columnCount?: number | null;
  rowCount?: number | null;
  /** e.g. ``billing`` — Kenan BP–relevant tables from Telco-Data. */
  applications?: string[];
  billing_target?: string | null;
  system_key?: string | null;
}

export interface CatalogTable extends TableRef {
  /** Backend service key ("sfdc", "oracle", ...). */
  service: string;
}

export interface TableRows {
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}

export interface TableColumn {
  columnName: string;
  dataType: string;
  isNullable?: boolean;
  ordinalPosition?: number;
}

export interface BackboneSystem {
  system_key: string;
  slug?: string;
  deliveries: string[];
  billing?: boolean;
  billing_target?: string;
  applications?: string[];
}
export interface BackboneCatalog {
  layer: string;
  vendors: Record<string, string>;
  vendor_default: string;
  systems: BackboneSystem[];
  billing_module?: { id: string; label: string };
}
export interface BackboneFile { name?: string; path?: string; system_key?: string | null; vendor_code?: string | null }
export interface BackboneApi { method?: string; route_path?: string; system_key?: string | null; vendor_code?: string | null }
export interface BackboneStream { topic?: string; event_count?: number; system_key?: string | null; vendor_code?: string | null }
export interface BackboneSummary {
  layer?: string;
  run_id?: string | null;
  generated_at?: string | null;
  vendor_code?: string | null;
  vendor_label?: string | null;
  tables?: { schema: string; table: string; rows: number }[];
  files?: BackboneFile[];
  apis?: BackboneApi[];
  streams?: BackboneStream[];
}

export interface ScenarioStep {
  id: string;
  title: string;
  plugin: string;
  tables: string[];
  action: string;
  index?: number;
  /** Present on previewed steps: rows that would be added per table. */
  planned?: Record<string, number>;
}
export interface Scenario {
  id: string;
  solutionId: string;
  solutionTitle: string;
  title: string;
  summary?: string;
  kpis: string[];
  steps: ScenarioStep[];
  plugins: string[];
  stepCount: number;
}
export interface ScenarioWrite {
  plugin: string;
  pluginLabel?: string;
  schema?: string;
  table: string;
  action?: string;
  added?: number;
  count?: number;
  updated?: number;
  deleted?: number;
  beforeCount?: number | null;
  afterCount?: number | null;
  recordIds?: (string | number)[];
}
export interface ScenarioStepResult {
  stepId: string;
  message?: string;
  written?: ScenarioWrite[];
  bound?: { name: string; count: number; sample: unknown[] }[];
}
export interface ScenarioRun {
  runId: string;
  scenarioId: string;
  status: string;
  completedSteps?: string[];
  results: ScenarioStepResult[];
  summary?: { totalAdded: number; tablesTouched: number; tables: ScenarioWrite[]; reverted?: ScenarioWrite[] };
  reverted?: ScenarioWrite[];
}

export interface VendorMethod { method: string; path: string; kind: string }
export interface VendorApi {
  id: string;
  system: string;
  name: string;
  table: string;
  schema: string;
  rowCount: number;
  columnCount?: number;
  pk?: string;
  docsUrl?: string;
  methods: VendorMethod[];
}

/* ------------------------------------------------------------- transport */

let basePromise: Promise<string> | null = null;

function apiBase(): Promise<string> {
  if (!basePromise) {
    basePromise = fetch('/config.json', { cache: 'no-store', headers: { Accept: 'application/json' } })
      .then(r => (r.ok ? r.json() : {}))
      .then((c: any) => String(c?.api?.baseUrl || ''))
      .catch(() => '');
  }
  return basePromise;
}

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const base = await apiBase();
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
    const text = await res.text();
    let body: any = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = null; }
    if (!res.ok) {
      if (res.status === 503) throw new ApiError('This simulator is switched off on the server.', 503);
      const detail = body?.detail;
      throw new ApiError(typeof detail === 'string' ? detail : `The server answered ${res.status} ${res.statusText}`.trim(), res.status);
    }
    if (body === null) throw new ApiError('The server did not return data for this request.', res.status);
    return body as T;
  } catch (e: any) {
    if (e instanceof ApiError) throw e;
    if (e?.name === 'AbortError') throw new ApiError('The request took too long. Please try again.');
    throw new ApiError('Could not reach the simulator service. Check your connection and try again.');
  } finally {
    window.clearTimeout(timer);
  }
}

const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
const enc = encodeURIComponent;
const LONG = 120000;

/** Full URL for links that open in a new tab (API routes, stream replay). */
export async function absoluteUrl(path: string): Promise<string> {
  return `${await apiBase()}${path}`;
}

/* --------------------------------------------------------------- catalog */

export const listSimulators = () => request<{ total: number; items: SimStatus[] }>('/api/v1/simulators').then(r => r.items || []);

export const getSimulatorTables = (service: string) =>
  request<SimStatus & { tables?: any[] }>(`/api/v1/simulators/${enc(service)}`).then(r =>
    (r.tables || []).map((t): CatalogTable => ({
      service,
      schemaName: t.schemaName ?? t.schema,
      tableName: t.tableName ?? t.table,
      columnCount: t.columnCount ?? t.columns ?? null,
      rowCount: t.rowCount ?? t.rows ?? null,
      applications: t.applications ?? undefined,
      billing_target: t.billing_target ?? t.billingTarget ?? null,
      system_key: t.system_key ?? t.systemKey ?? null,
    })),
  );

export const seedBillingTelco = () => request<{ message?: string }>('/api/v1/telco/seed-billing', post(), LONG);

export interface BillingFeed {
  id: string;
  name: string;
  layer: string;
  source_lineage?: string;
  key_data?: string;
  format?: string;
  delivery?: string[];
  intake?: string;
  lands_in?: string;
  tmf_sid?: string;
  simulated_rows?: number;
  table_count?: number;
  linked_tables?: { service: string; schema?: string; table?: string; rows?: number }[];
}

export interface BillingOverview {
  feeds: BillingFeed[];
  tables: (TableRef & { service: string; schema?: string; table?: string; rows?: number })[];
  totals?: {
    feeds: number;
    tables: number;
    rows: number;
    by_layer?: { tables: Record<string, number>; rows: Record<string, number> };
  };
}

export const getBillingOverview = (layer?: string) =>
  request<BillingOverview>(`/api/v1/telco/billing${layer ? `?layer=${enc(layer)}` : ''}`);

export const seedAllTelco = () => request<{ message?: string }>('/api/v1/telco/seed-all', post(), LONG);

/* ------------------------------------------------------------ one system */

export function systemApi(apiPath: string) {
  return {
    status: () => request<SimStatus>(`${apiPath}/status`),
    load: () => request<any>(`${apiPath}/load`, post(), LONG),
    seed: () => request<any>(`${apiPath}/seed`, post(), LONG),
    reset: () => request<any>(`${apiPath}/reset`, post(), LONG),
    objects: () => request<{ objects: TableRef[] }>(`${apiPath}/objects`).then(r => r.objects || []),
    rows: (schema: string, table: string, limit = 50, offset = 0) =>
      request<TableRows>(`${apiPath}/objects/${enc(schema)}/${enc(table)}?limit=${limit}&offset=${offset}`),
    columns: (schema: string, table: string) =>
      request<{ columns: TableColumn[] }>(`${apiPath}/objects/${enc(schema)}/${enc(table)}/columns`).then(r => r.columns || []),

    /* Telco AI Backbone (BSS / NSS / OSS only) */
    backboneCatalog: () => request<BackboneCatalog>(`${apiPath}/backbone/catalog`),
    backboneSummary: () => request<BackboneSummary>(`${apiPath}/backbone/summary`),
    backboneStatus: () => request<SimStatus>(`${apiPath}/backbone/status`),
    backboneGenerate: (body: unknown) => request<any>(`${apiPath}/backbone/generate`, post(body), LONG),
    backboneStreamEvents: (topic: string) => request<{ events?: unknown[] }>(`${apiPath}/backbone/stream-events?topic=${enc(topic)}`).then(r => r.events || []),
    backboneFile: async (path: string) => {
      const res = await fetch(`${await apiBase()}${apiPath}/backbone/file?path=${enc(path)}`);
      if (!res.ok) throw new ApiError(`Could not open the file (${res.status}).`, res.status);
      return res.text();
    },

    /** External sources (files + social feed). */
    sources: () => request<{ sources: ExternalSourceDef[] }>(`${apiPath}/sources`).then(r => r.sources || []),
    files: (source?: string) =>
      request<{ files: ExternalArtifactFile[] }>(
        `${apiPath}/files${source ? `?source=${enc(source)}` : ''}`,
      ).then(r => r.files || []),
    social: (limit = 100) =>
      request<{ items: SocialFeedItem[] }>(`${apiPath}/social?limit=${limit}`).then(r => r.items || []),
    filePreview: (path: string) =>
      request<{ content: string }>(`${apiPath}/files/preview?path=${enc(path)}`).then(r => r.content || ''),

    vendorApiPath: (route: string) => `${apiPath}/vendor-api/${route.replace(/^\//, '')}`,
    streamReplayPath: (topic: string) => `${apiPath}/backbone/stream/${enc(topic)}`,
  };
}

export type SystemApi = ReturnType<typeof systemApi>;

/* -------------------------------------------------------------- scenarios */

export const listScenarios = () =>
  request<{ solutions: { id: string; title: string }[]; items: Scenario[] }>('/api/v1/scenarios');

export const previewScenario = (id: string) =>
  request<{ steps: ScenarioStep[] }>(`/api/v1/scenarios/${enc(id)}/preview`, post({ limit: 10 })).then(r => r.steps || []);

export const runScenario = (id: string, body: { stepId?: string; runId?: string }) =>
  request<ScenarioRun>(`/api/v1/scenarios/${enc(id)}/run`, post({ ...body, limit: 10 }), LONG);

export const revertScenarioRun = (runId: string) =>
  request<ScenarioRun>(`/api/v1/scenarios/runs/${enc(runId)}/revert`, post(), LONG);

/* ------------------------------------------------------------ vendor APIs */

export const listVendorApis = (system: string) =>
  request<{ items: VendorApi[] }>(`/api/v1/vendor-apis?system=${enc(system)}`, {}, 60000).then(r => r.items || []);

export const vendorApiSample = (id: string) =>
  request<{ row?: Record<string, unknown> }>(`/api/v1/vendor-apis/${enc(id)}/sample`).then(r => r.row || {});

/** Send any request and return the raw outcome (used by the API test bench). */
export async function sendRaw(path: string, method: string, body?: string): Promise<{ status: number; statusText: string; ok: boolean; text: string; ms: number }> {
  const base = /^https?:/.test(path) ? '' : await apiBase();
  const started = performance.now();
  const res = await fetch(`${base}${path}`, {
    method,
    headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: ['GET', 'HEAD', 'DELETE'].includes(method) ? undefined : body,
  });
  const text = await res.text();
  return { status: res.status, statusText: res.statusText, ok: res.ok, text, ms: Math.round(performance.now() - started) };
}

export const vendorBatch = (body: unknown) => sendRaw('/api/v1/vendor-apis/batch', 'POST', JSON.stringify(body));

/* ---------------------------------------------------------------- service */

export const getHealth = () => request<Record<string, unknown>>('/health');
export const getReadiness = () => request<Record<string, unknown>>('/readiness');
