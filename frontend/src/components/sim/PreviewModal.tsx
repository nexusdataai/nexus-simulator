/**
 * Shows the content of a generated file, an API answer or the events of a
 * stream. Tabular content (CSV, JSON list) is shown as a table.
 */
import * as React from 'react';
import { Button } from '@/components/ui/button';
import { ModalOverlay, ModalPanel } from '@/components/ds/Modal';
import { CodeBlock, InlineError } from '@/components/ds/kit';
import { Icon } from '@/components/ds/Icon';
import { cell, errorText, num } from '@/core/format';

export interface PreviewTarget {
  title: string;
  /** Second line: path, URL or topic. */
  subtitle?: string;
  family?: string | null;
  /** Loads the content as text. */
  load: () => Promise<string>;
  /** Optional link that opens the raw source in a new tab. */
  href?: string;
  hrefLabel?: string;
  /** File name, used to detect CSV / JSON. */
  name?: string;
}

type Parsed =
  | { kind: 'table'; headers: string[]; rows: string[][] }
  | { kind: 'text'; text: string };

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { cur += '"'; i++; } else quoted = !quoted;
    } else if (ch === ',' && !quoted) { out.push(cur.trim()); cur = ''; } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

function tableFromList(value: unknown): Parsed | null {
  if (!Array.isArray(value) || !value.length || typeof value[0] !== 'object' || value[0] === null) return null;
  const headers: string[] = [];
  value.forEach(r => Object.keys(r as object).forEach(k => { if (!headers.includes(k)) headers.push(k); }));
  return { kind: 'table', headers, rows: value.map(r => headers.map(h => cell((r as any)[h]))) };
}

function parse(text: string, name = ''): Parsed {
  const trimmed = text.trim();
  const lower = name.toLowerCase();
  if (lower.endsWith('.json') || trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const value = JSON.parse(trimmed);
      return tableFromList(value) || { kind: 'text', text: JSON.stringify(value, null, 2) };
    } catch { /* not JSON: fall through */ }
  }
  const isBinaryOrKenanDump =
    lower.endsWith('.dat') ||
    trimmed.startsWith('HDR') ||
    trimmed.startsWith('-- File:') ||
    /\b(moCallRecord|pGWRecord|sCSCFRecord|TAP3)\b/.test(trimmed);
  if (
    !isBinaryOrKenanDump
    && (lower.endsWith('.csv') || (trimmed.includes(',') && trimmed.includes('\n')))
  ) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    const headers = splitCsvLine(lines[0] || '');
    if (headers.length > 1 && lines.length > 1) return { kind: 'table', headers, rows: lines.slice(1).map(splitCsvLine) };
  }
  return { kind: 'text', text };
}

export function PreviewModal({ target, onClose }: { target: PreviewTarget | null; onClose: () => void }) {
  const [parsed, setParsed] = React.useState<Parsed | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    if (!target) return;
    let alive = true;
    setParsed(null); setError(null);
    target.load()
      .then(t => { if (alive) setParsed(parse(t, target.name)); })
      .catch(e => { if (alive) setError(errorText(e)); });
    return () => { alive = false; };
  }, [target]);

  React.useEffect(() => load(), [load]);

  if (!target) return null;
  return (
    <ModalOverlay onClose={onClose}>
      <ModalPanel label={target.title} className="max-w-4xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="break-all font-mono text-md font-medium text-foreground">{target.title}</h2>
            <p className="mt-1 break-all text-xs text-muted-foreground">
              {target.family && <span className="text-foreground">{target.family}</span>}
              {target.family && target.subtitle ? ' · ' : ''}
              {target.subtitle && <span className="font-mono">{target.subtitle}</span>}
            </p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close"><Icon name="close" /></Button>
        </header>

        <div className="scroll-thin min-h-0 flex-1 overflow-auto">
          {error && <div className="p-5"><InlineError onRetry={load}>{error}</InlineError></div>}
          {!error && !parsed && (
            <div className="space-y-2 p-5" aria-busy="true">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="shimmer h-7 rounded-md bg-surface-2" />)}</div>
          )}
          {parsed?.kind === 'table' && (
            <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
              <thead>
                <tr>{parsed.headers.map(h => <th key={h} className="sticky top-0 whitespace-nowrap border-b border-border bg-popover px-3 py-2 text-left text-xs font-medium text-muted-foreground first:pl-5">{h}</th>)}</tr>
              </thead>
              <tbody>
                {parsed.rows.map((r, i) => (
                  <tr key={i} className="hover:bg-surface-2/60">
                    {parsed.headers.map((_, j) => <td key={j} title={(r[j] || '').length > 40 ? r[j] : undefined} className="max-w-[280px] truncate border-b border-border px-3 py-2 first:pl-5">{r[j] || '—'}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {parsed?.kind === 'text' && <div className="p-5"><CodeBlock maxHeight={520} wrap>{parsed.text || '(empty)'}</CodeBlock></div>}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="num text-xs text-muted-foreground">{parsed?.kind === 'table' ? `${num(parsed.rows.length)} rows · ${parsed.headers.length} columns` : ''}</span>
          <div className="flex gap-2">
            {target.href && (
              <Button variant="outline" size="sm" asChild>
                <a href={target.href} target="_blank" rel="noreferrer">{target.hrefLabel || 'Open in a new tab'} <Icon name="external-link" /></a>
              </Button>
            )}
            <Button size="sm" onClick={onClose}>Close</Button>
          </div>
        </footer>
      </ModalPanel>
    </ModalOverlay>
  );
}
