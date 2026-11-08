/** Parse backbone file text for friendly preview (CSV table, JSON, or plain text). */

export type CsvPreview = { kind: 'csv'; headers: string[]; rows: string[][] };
export type JsonPreview = { kind: 'json'; value: unknown; asTable?: { headers: string[]; rows: string[][] } };
export type TextPreview = { kind: 'text'; content: string };

export type ContentPreview = CsvPreview | JsonPreview | TextPreview;

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      out.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

function parseCsv(text: string): CsvPreview | null {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 1) return null;
  const headers = splitCsvLine(lines[0]);
  if (headers.length < 2) return null;
  const rows = lines.slice(1).map(splitCsvLine);
  return { kind: 'csv', headers, rows };
}

export function recordsToTable(value: unknown): { headers: string[]; rows: string[][] } | undefined {
  if (!Array.isArray(value) || value.length === 0) return undefined;
  if (typeof value[0] !== 'object' || value[0] === null) return undefined;
  const headers = Object.keys(value[0] as Record<string, unknown>);
  const rows = value.map((row) =>
    headers.map((h) => {
      const v = (row as Record<string, unknown>)[h];
      if (v === null || v === undefined) return '';
      if (typeof v === 'object') return JSON.stringify(v);
      return String(v);
    }),
  );
  return { headers, rows };
}

export function previewBackboneFileContent(content: string, fileName?: string): ContentPreview {
  const trimmed = content.trim();
  const lower = (fileName || '').toLowerCase();

  if (lower.endsWith('.json') || trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const value = JSON.parse(trimmed) as unknown;
      const asTable = recordsToTable(value);
      return { kind: 'json', value, asTable };
    } catch {
      /* fall through */
    }
  }

  if (lower.endsWith('.csv') || (trimmed.includes(',') && trimmed.includes('\n'))) {
    const csv = parseCsv(content);
    if (csv && csv.rows.length > 0) return csv;
  }

  return { kind: 'text', content };
}

export function formatJsonForDisplay(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
