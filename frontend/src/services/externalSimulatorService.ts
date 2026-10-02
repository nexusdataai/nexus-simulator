/**
 * External Source Simulator Service
 *
 * API client for the unified Google Drive / Social Listening / File Uploads simulator.
 * API Base Path: /api/v1/external-simulator/
 */

export interface ExternalSimulatorStatus {
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
  systems?: Record<string, { tables: number; rows: number }>;
}

export interface ExternalObjectSummary {
  schemaName: string;
  tableName: string;
  columnCount: number;
  rowCount: number;
  system: string;
}

export interface ExternalObjectsResponse {
  objects: ExternalObjectSummary[];
  message?: string;
}

export interface ExternalRecordsResponse {
  schemaName: string;
  tableName: string;
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}

let cachedConfig: { baseUrl: string } | null = null;

const API_PATH = '/api/v1/external-simulator';

async function getBaseUrl(): Promise<string> {
  if (cachedConfig) return cachedConfig.baseUrl;
  try {
    const res = await fetch('/config.json', { cache: 'no-store' });
    if (res.ok) {
      const cfg = await res.json();
      cachedConfig = { baseUrl: cfg.api?.baseUrl || '' };
      return cachedConfig.baseUrl;
    }
  } catch { /* ignore */ }
  cachedConfig = { baseUrl: '' };
  return '';
}

async function apiGet<T>(endpoint: string): Promise<T> {
  const base = await getBaseUrl();
  const res = await fetch(`${base}${API_PATH}${endpoint}`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function apiPost<T>(endpoint: string): Promise<T> {
  const base = await getBaseUrl();
  const res = await fetch(`${base}${API_PATH}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface UploadResponse {
  success: boolean;
  filename: string;
  document_type: string;
  row_id: string;
  extracted_fields: Record<string, unknown>;
  confidence: number;
  s3_key?: string | null;
}

export const externalSimulatorService = {
  getStatus: () => apiGet<ExternalSimulatorStatus>('/status'),
  seedData: () => apiPost<{ success: boolean; message: string }>('/seed'),
  loadData: () => apiPost<{ success: boolean; message: string }>('/load'),
  resetData: () => apiPost<{ success: boolean; message: string }>('/reset'),
  getObjects: () => apiGet<ExternalObjectsResponse>('/objects'),
  getRecords: (schema: string, table: string, limit = 50, offset = 0) =>
    apiGet<ExternalRecordsResponse>(
      `/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}?limit=${limit}&offset=${offset}`,
    ),
  uploadDocument: async (type: string, file: File): Promise<UploadResponse> => {
    const base = await getBaseUrl();
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${base}${API_PATH}/upload/${type}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed: ${res.statusText}`);
    }
    return res.json();
  },
};
