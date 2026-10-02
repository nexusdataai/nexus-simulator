/**
 * CPQ Simulator Service factory
 *
 * Produces an API client for the two CPQ simulators (Trade CPQ /
 * Sourcing CPQ) by parameterising the SAP simulator client over its
 * API base path. Mirrors the shape of sapSimulatorService so the
 * SAP simulator UI sub-components can be reused unchanged.
 */

import type {
  SimulatorStatus,
  AdminResponse,
  ObjectsResponse,
  ObjectRecordsResponse,
  ColumnsResponse,
  LoadStatus,
  SimulatorError,
} from './sapSimulatorService';

interface ServiceConfig {
  baseUrl: string;
  timeout: number;
}

let cachedConfig: ServiceConfig | null = null;
let configLoadPromise: Promise<ServiceConfig | null> | null = null;

const DEFAULT_API_URL = '';

class CPQSimulatorService {
  private readonly apiPath: string;

  constructor(apiPath: string) {
    this.apiPath = apiPath;
  }

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
    return `${cfg.baseUrl}${this.apiPath}${endpoint}`;
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
  async seedData(): Promise<AdminResponse> {
    return this.request<AdminResponse>(await this.url('/seed'), { method: 'POST' }, 'Seed data', 120000);
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

export const tpmSimulatorService = new CPQSimulatorService('/api/v1/tpm-simulator');
export const sourcingSimulatorService = new CPQSimulatorService('/api/v1/sourcing-simulator');

export type { CPQSimulatorService };
