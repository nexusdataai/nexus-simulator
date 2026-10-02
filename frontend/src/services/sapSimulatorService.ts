/**
 * SAP Simulator Service
 *
 * API client for the SAP S/4HANA Simulator backend.
 * API Base Path: /api/v1/sap-simulator/
 */

export interface SimulatorStatus {
  enabled: boolean;
  loaded: boolean;
  bucket: string;
  prefix: string;
  schema: string;
  table_count: number;
  tables_with_data: number;
  total_rows: number;
  dump_timestamp?: string | null;
  last_loaded?: string | null;
  dump_available?: boolean;
  dump_tables?: number;
  dump_rows?: number;
}

export interface AdminResponse {
  success: boolean;
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

export interface ObjectSummary {
  schemaName: string;
  tableName: string;
  columnCount: number;
  rowCount: number;
}

export interface ObjectsResponse {
  objects: ObjectSummary[];
  message?: string;
}

export interface ObjectRecordsResponse {
  schemaName: string;
  tableName: string;
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}

export interface ColumnInfo {
  columnName: string;
  dataType: string;
  isNullable: boolean;
  ordinalPosition: number;
}

export interface ColumnsResponse {
  schemaName: string;
  tableName: string;
  columns: ColumnInfo[];
}

export interface StepEntry {
  timestamp: string;
  message: string;
  status: 'running' | 'done' | 'error';
}

export interface LoadStatus {
  running: boolean;
  steps: StepEntry[];
  result?: Record<string, unknown>;
}

export interface SimulatorError {
  message: string;
  type: 'network' | 'config' | 'api' | 'unknown';
  status?: number;
  details?: unknown;
}

interface ServiceConfig {
  baseUrl: string;
  timeout: number;
}

let cachedConfig: ServiceConfig | null = null;
let configLoadPromise: Promise<ServiceConfig | null> | null = null;

const DEFAULT_API_URL = '';
const SIMULATOR_API_PATH = '/api/v1/sap-simulator';

class SapSimulatorService {
  private async loadConfig(): Promise<ServiceConfig> {
    if (cachedConfig) return cachedConfig;
    if (configLoadPromise) {
      const r = await configLoadPromise;
      if (r) return r;
    }
    configLoadPromise = (async () => {
      try {
        const res = await fetch('/config.json', { cache: 'no-store', headers: { Accept: 'application/json' } });
        if (!res.ok) return null;
        const cfg = await res.json();
        cachedConfig = { baseUrl: cfg.api?.baseUrl || DEFAULT_API_URL, timeout: cfg.api?.timeout || 30000 };
        return cachedConfig;
      } catch { return null; }
    })();
    const result = await configLoadPromise;
    return result ?? { baseUrl: DEFAULT_API_URL, timeout: 30000 };
  }

  private async url(endpoint: string): Promise<string> {
    const cfg = await this.loadConfig();
    return `${cfg.baseUrl}${SIMULATOR_API_PATH}${endpoint}`;
  }

  private headers(): Record<string, string> {
    return { 'Content-Type': 'application/json', Accept: 'application/json' };
  }

  private toError(err: unknown, ctx: string): SimulatorError {
    if (err instanceof Error) {
      if (err.name === 'AbortError') return { message: `${ctx}: Request timed out`, type: 'network' };
      if (err.message.includes('fetch') || err.message.includes('network'))
        return { message: `${ctx}: Network error`, type: 'network' };
      return { message: `${ctx}: ${err.message}`, type: 'unknown', details: err };
    }
    return { message: `${ctx}: Unknown error`, type: 'unknown', details: err };
  }

  private async request<T>(url: string, opts: RequestInit = {}, ctx: string, timeoutMs?: number): Promise<T> {
    const cfg = await this.loadConfig();
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), timeoutMs ?? cfg.timeout);
    try {
      const res = await fetch(url, { ...opts, signal: controller.signal, headers: { ...this.headers(), ...opts.headers } });
      clearTimeout(tid);
      if (res.status === 503) throw { message: 'Simulator is disabled on the server', type: 'config', status: 503 } as SimulatorError;
      if (res.status === 404) throw { message: 'Endpoint not available', type: 'config', status: 404 } as SimulatorError;
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `${ctx}: ${res.status} ${res.statusText}`);
      }
      return (await res.json()) as T;
    } catch (err) {
      clearTimeout(tid);
      if ((err as SimulatorError).type) throw err;
      throw this.toError(err, ctx);
    }
  }

  async getStatus(): Promise<SimulatorStatus> {
    return this.request<SimulatorStatus>(await this.url('/status'), { method: 'GET' }, 'Get status');
  }

  async loadData(): Promise<AdminResponse> {
    return this.request<AdminResponse>(await this.url('/load'), { method: 'POST' }, 'Load data', 120000);
  }

  async getLoadStatus(): Promise<LoadStatus> {
    return this.request<LoadStatus>(await this.url('/load/status'), { method: 'GET' }, 'Get load status');
  }

  async resetData(): Promise<AdminResponse> {
    return this.request<AdminResponse>(await this.url('/reset'), { method: 'POST' }, 'Reset data', 120000);
  }

  async getObjects(): Promise<ObjectsResponse> {
    return this.request<ObjectsResponse>(await this.url('/objects'), { method: 'GET' }, 'Get objects');
  }

  async getObjectRecords(schema: string, table: string, limit = 50, offset = 0): Promise<ObjectRecordsResponse> {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.request<ObjectRecordsResponse>(
      await this.url(`/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}?${qs}`),
      { method: 'GET' }, 'Get object records',
    );
  }

  async getObjectColumns(schema: string, table: string): Promise<ColumnsResponse> {
    return this.request<ColumnsResponse>(
      await this.url(`/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}/columns`),
      { method: 'GET' }, 'Get columns',
    );
  }
}

export const sapSimulatorService = new SapSimulatorService();
export default sapSimulatorService;
