/** Formatting helpers shared by every screen. */

const NUM = new Intl.NumberFormat('en-US');
const COMPACT = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

export function num(n?: number | null): string {
  return n == null || Number.isNaN(n) ? '—' : NUM.format(n);
}

export function compact(n?: number | null): string {
  return n == null || Number.isNaN(n) ? '—' : COMPACT.format(n);
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${num(n)} ${n === 1 ? one : many}`;
}

/** "8 Nov 2026, 19:17" in the viewer's time zone. */
export function dateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** "3 days ago", "2 months ago". */
export function ago(iso?: string | null): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 90) return 'just now';
  const units: [number, string][] = [[60, 'minute'], [60, 'hour'], [24, 'day'], [30, 'month'], [12, 'year']];
  let v = s / 60;
  let label = 'minute';
  for (let i = 1; i < units.length; i++) {
    if (v < units[i][0]) break;
    v /= units[i][0];
    label = units[i][1];
  }
  const n = Math.floor(v);
  return `${n} ${label}${n === 1 ? '' : 's'} ago`;
}

/** Show a cell value from a data row as text. */
export function cell(v: unknown): string {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
