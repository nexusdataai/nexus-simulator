/**
 * Side sheet that shows the rows and columns of one table.
 * Used by Systems, Tables and the telecom generated-data lists.
 */
import * as React from 'react';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { DetailSheet, InlineError, SearchInput } from '@/components/ds/kit';
import { Icon } from '@/components/ds/Icon';
import { cell, errorText, num } from '@/core/format';
import type { TableColumn, TableRows } from '@/services/api';

export interface RowsSource {
  rows: (schema: string, table: string, limit?: number, offset?: number) => Promise<TableRows>;
  columns: (schema: string, table: string) => Promise<TableColumn[]>;
}

interface RowsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  schema?: string;
  table?: string;
  /** Line under the title, e.g. the system name. */
  context?: React.ReactNode;
  source?: RowsSource;
}

const PAGE = 50;

export function RowsSheet({ open, onOpenChange, schema, table, context, source }: RowsSheetProps) {
  const [view, setView] = React.useState<'data' | 'columns'>('data');
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<TableRows | null>(null);
  const [cols, setCols] = React.useState<TableColumn[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [find, setFind] = React.useState('');

  // Reset when another table is opened.
  React.useEffect(() => {
    setOffset(0); setData(null); setCols(null); setError(null); setFind(''); setView('data');
  }, [schema, table]);

  const load = React.useCallback(() => {
    if (!open || !source || !schema || !table) return;
    let alive = true;
    setLoading(true); setError(null);
    source.rows(schema, table, PAGE, offset)
      .then(d => { if (alive) setData(d); })
      .catch(e => { if (alive) setError(errorText(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [open, source, schema, table, offset]);

  React.useEffect(() => load(), [load]);

  React.useEffect(() => {
    if (!open || !source || !schema || !table || cols) return;
    let alive = true;
    source.columns(schema, table).then(c => { if (alive) setCols(c); }).catch(() => { if (alive) setCols([]); });
    return () => { alive = false; };
  }, [open, source, schema, table, cols]);

  const rows = data?.rows || [];
  // Column order: the declared columns first, then anything extra found in the rows.
  const headers = React.useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    (cols || []).forEach(c => { if (!seen.has(c.columnName)) { seen.add(c.columnName); out.push(c.columnName); } });
    rows.forEach(r => Object.keys(r).forEach(k => { if (!seen.has(k)) { seen.add(k); out.push(k); } }));
    return out;
  }, [cols, rows]);

  const shown = React.useMemo(() => {
    const q = find.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(r => Object.values(r).some(v => cell(v).toLowerCase().includes(q)));
  }, [rows, find]);

  const total = data?.total ?? 0;
  const from = total ? offset + 1 : 0;
  const to = Math.min(offset + PAGE, total);

  return (
    <DetailSheet
      open={open}
      onOpenChange={onOpenChange}
      xwide
      title={<span className="font-mono text-md">{table}</span>}
      description={<>{context}{context ? ' · ' : ''}<span className="font-mono text-xs">{schema}</span>{data ? ` · ${num(total)} rows` : ''}{cols?.length ? ` · ${cols.length} columns` : ''}</>}
      meta={
        <div className="flex w-full flex-wrap items-center gap-2">
          <div role="tablist" aria-label="Table view" className="flex gap-1 rounded-md bg-surface-2 p-0.5">
            {(['data', 'columns'] as const).map(v => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={cn('h-7 rounded px-2.5 text-sm transition-colors', view === v ? 'bg-card font-medium text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground')}
              >
                {v === 'data' ? 'Data' : 'Columns'}
              </button>
            ))}
          </div>
          {view === 'data' && <SearchInput value={find} onChange={setFind} placeholder="Find in these rows" className="sm:w-56" />}
        </div>
      }
      footer={view === 'data' && total > 0 ? (
        <div className="flex w-full items-center justify-between gap-3">
          <span className="num text-xs text-muted-foreground">Rows {num(from)}–{num(to)} of {num(total)}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              <Icon name="chevron-left" /> Previous
            </Button>
            <Button variant="outline" size="sm" disabled={to >= total || loading} onClick={() => setOffset(offset + PAGE)}>
              Next <Icon name="chevron-right" />
            </Button>
          </div>
        </div>
      ) : undefined}
    >
      {error && <InlineError onRetry={load}>{error}</InlineError>}

      {view === 'data' && !error && (
        loading && !data ? (
          <div className="space-y-2" aria-busy="true">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="shimmer h-8 rounded-md bg-surface-2" />)}</div>
        ) : rows.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">This table has no rows yet.</p>
        ) : (
          <div className={cn('scroll-thin -mx-5 -my-5 overflow-auto', loading && 'opacity-60')} style={{ maxHeight: 'calc(100dvh - 230px)' }}>
            <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  {headers.map(h => (
                    <th key={h} className="sticky top-0 z-10 whitespace-nowrap border-b border-border bg-popover px-3 py-2 text-left text-xs font-medium text-muted-foreground first:pl-5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((r, i) => (
                  <tr key={i} className="hover:bg-surface-2/60">
                    {headers.map(h => {
                      const v = cell(r[h]);
                      return (
                        <td key={h} title={v.length > 40 ? v : undefined} className={cn('max-w-[280px] truncate border-b border-border px-3 py-2 first:pl-5', typeof r[h] === 'number' && 'num text-right', !v && 'text-subtle-foreground')}>
                          {v || '—'}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {shown.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">No row on this page contains “{find}”.</p>}
          </div>
        )
      )}

      {view === 'columns' && (
        cols === null ? (
          <div className="space-y-2" aria-busy="true">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="shimmer h-8 rounded-md bg-surface-2" />)}</div>
        ) : cols.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">Column details are not available for this table.</p>
        ) : (
          <ol>
            {cols.map((c, i) => (
              <li key={c.columnName} className="flex items-baseline gap-3 border-b border-border py-2 text-sm last:border-b-0">
                <span className="num w-6 shrink-0 text-right text-xs text-subtle-foreground">{c.ordinalPosition ?? i + 1}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground">{c.columnName}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{c.dataType}{c.isNullable === false ? ' · required' : ''}</span>
              </li>
            ))}
          </ol>
        )
      )}
    </DetailSheet>
  );
}
