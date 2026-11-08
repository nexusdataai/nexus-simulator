/**
 * SFDC Simulator Service
 *
 * API client for the Salesforce FDW Simulator backend.
 * Provides admin operations against the SFDC simulator backend.
 *
 * API Base Path: /api/v1/sfdc-simulator/
 * Config API:    /api/v1/config/sfdc-mode
 */

// ============================================================================
// Type Definitions
// ============================================================================

export interface SFDCSimulatorStatus {
  enabled: boolean;
  loaded: boolean;
  bucket: string;
  prefix: string;
  table_data_prefix?: string;
  files_data_prefix?: string;
  schema: string;
  table_count: number;
  tables_with_data: number;
  total_rows: number;
  file_count?: number;
  api_count?: number;
  stream_count?: number;
  dump_timestamp?: string | null;
  last_loaded?: string | null;
  dump_available?: boolean;
  dump_tables?: number;
  dump_rows?: number;
}

export interface SFDCHealthResponse {
  status: string;
  enabled: boolean;
  bucket_configured: boolean;
  loaded: boolean;
  timestamp: string;
}

export interface SFDCAdminResponse {
  success: boolean;
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

export interface SFDCObjectSummary {
  schemaName: string;
  tableName: string;
  columnCount: number;
  rowCount: number;
}

export interface SFDCObjectsResponse {
  objects: SFDCObjectSummary[];
  message?: string;
}

export interface SFDCObjectRecordsResponse {
  schemaName: string;
  tableName: string;
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}

export interface SFDCColumnInfo {
  columnName: string;
  dataType: string;
  isNullable: boolean;
  ordinalPosition: number;
}

export interface SFDCColumnsResponse {
  schemaName: string;
  tableName: string;
  columns: SFDCColumnInfo[];
}

export interface SFDCModeResponse {
  simulator_enabled: boolean;
  mode: 'simulator' | 'real';
  source: string;
  timestamp: string;
}

export interface SFDCDumpRequest {
  source_url: string;
  schema?: string;
  tables?: string[];
  dump_all?: boolean;
  limit?: number;
}

export interface SFDCStepEntry {
  timestamp: string;
  message: string;
  status: 'running' | 'done' | 'error';
}

export interface SFDCLoadStatus {
  running: boolean;
  steps: SFDCStepEntry[];
  result?: Record<string, unknown>;
}

export interface SFDCDumpStatus {
  running: boolean;
  result?: Record<string, unknown>;
  steps?: SFDCStepEntry[];
  step?: string;
  tables_done?: number;
  tables_total?: number;
  rows_dumped?: number;
}

export interface SFDCSimulatorError {
  message: string;
  type: 'network' | 'config' | 'api' | 'unknown';
  status?: number;
  details?: unknown;
}

// ============================================================================
// Configuration
// ============================================================================

interface ServiceConfig {
  baseUrl: string;
  timeout: number;
}

let cachedConfig: ServiceConfig | null = null;
let configLoadPromise: Promise<ServiceConfig | null> | null = null;

const DEFAULT_API_URL = '';
const SIMULATOR_API_PATH = '/api/v1/sfdc-simulator';
const CONFIG_API_PATH = '/api/v1/config';

// ============================================================================
// Service Class
// ============================================================================

class SFDCSimulatorService {
  private async loadConfig(): Promise<ServiceConfig> {
    if (cachedConfig) return cachedConfig;
    if (configLoadPromise) {
      const r = await configLoadPromise;
      if (r) return r;
    }

    configLoadPromise = (async () => {
      try {
        const res = await fetch('/config.json', {
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        });
        if (!res.ok) return null;
        const cfg = await res.json();
        cachedConfig = {
          baseUrl: cfg.api?.baseUrl || DEFAULT_API_URL,
          timeout: cfg.api?.timeout || 30000,
        };
        return cachedConfig;
      } catch {
        return null;
      }
    })();

    const result = await configLoadPromise;
    return result ?? { baseUrl: DEFAULT_API_URL, timeout: 30000 };
  }

  private async url(endpoint: string): Promise<string> {
    const cfg = await this.loadConfig();
    return `${cfg.baseUrl}${SIMULATOR_API_PATH}${endpoint}`;
  }

  private async configUrl(endpoint: string): Promise<string> {
    const cfg = await this.loadConfig();
    return `${cfg.baseUrl}${CONFIG_API_PATH}${endpoint}`;
  }

  private headers(): Record<string, string> {
    return { 'Content-Type': 'application/json', Accept: 'application/json' };
  }

  private toError(err: unknown, ctx: string): SFDCSimulatorError {
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
      if (res.status === 503) throw { message: 'Simulator is disabled on the server', type: 'config', status: 503 } as SFDCSimulatorError;
      if (res.status === 404) throw { message: 'Endpoint not available', type: 'config', status: 404 } as SFDCSimulatorError;
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `${ctx}: ${res.status} ${res.statusText}`);
      }
      return (await res.json()) as T;
    } catch (err) {
      clearTimeout(tid);
      if ((err as SFDCSimulatorError).type) throw err;
      throw this.toError(err, ctx);
    }
  }

  // ── Status & Health ──────────────────────────────────────────────────────

  async getStatus(): Promise<SFDCSimulatorStatus> {
    return this.request<SFDCSimulatorStatus>(await this.url('/status'), { method: 'GET' }, 'Get status');
  }

  async getHealth(): Promise<SFDCHealthResponse> {
    return this.request<SFDCHealthResponse>(await this.url('/health'), { method: 'GET' }, 'Health check');
  }

  // ── Data Operations ──────────────────────────────────────────────────────

  async loadData(): Promise<SFDCAdminResponse> {
    return this.request<SFDCAdminResponse>(await this.url('/load'), { method: 'POST' }, 'Load data', 120000);
  }

  async getLoadStatus(): Promise<SFDCLoadStatus> {
    return this.request<SFDCLoadStatus>(await this.url('/load/status'), { method: 'GET' }, 'Get load status');
  }

  async resetData(): Promise<SFDCAdminResponse> {
    return this.request<SFDCAdminResponse>(await this.url('/reset'), { method: 'POST' }, 'Reset data', 120000);
  }

  // ── Object Browsing ──────────────────────────────────────────────────────

  async getObjects(): Promise<SFDCObjectsResponse> {
    return this.request<SFDCObjectsResponse>(await this.url('/objects'), { method: 'GET' }, 'Get objects');
  }

  async getObjectRecords(schema: string, table: string, limit = 50, offset = 0): Promise<SFDCObjectRecordsResponse> {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.request<SFDCObjectRecordsResponse>(
      await this.url(`/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}?${qs}`),
      { method: 'GET' },
      'Get object records',
    );
  }

  async getObjectColumns(schema: string, table: string): Promise<SFDCColumnsResponse> {
    return this.request<SFDCColumnsResponse>(
      await this.url(`/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}/columns`),
      { method: 'GET' },
      'Get columns',
    );
  }

  // ── Mode Toggle ──────────────────────────────────────────────────────────

  async getMode(): Promise<SFDCModeResponse> {
    return this.request<SFDCModeResponse>(await this.configUrl('/sfdc-mode'), { method: 'GET' }, 'Get SFDC mode');
  }

  async setMode(enabled: boolean): Promise<SFDCModeResponse> {
    return this.request<SFDCModeResponse>(
      await this.configUrl('/sfdc-mode'),
      { method: 'PUT', body: JSON.stringify({ enabled }) },
      'Set SFDC mode',
    );
  }

  // ── Dump ─────────────────────────────────────────────────────────────────

  async triggerDump(req: SFDCDumpRequest): Promise<SFDCAdminResponse> {
    return this.request<SFDCAdminResponse>(
      await this.url('/dump'),
      { method: 'POST', body: JSON.stringify(req) },
      'Trigger dump',
      120000,
    );
  }

  async getDumpStatus(): Promise<SFDCDumpStatus> {
    return this.request<SFDCDumpStatus>(await this.url('/dump/status'), { method: 'GET' }, 'Get dump status');
  }
}

export const sfdcSimulatorService = new SFDCSimulatorService();
export default sfdcSimulatorService;
