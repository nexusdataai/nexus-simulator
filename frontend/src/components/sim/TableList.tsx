/**
 * Searchable, sortable list of tables. One component for a single system and
 * for the cross-system catalog (pass `showSystem`).
 */
import * as React from 'react';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { SearchInput, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { simByService } from '@/config/simulators';
import { num } from '@/core/format';

export interface TableListRow {
  service?: string;
  schemaName: string;
  tableName: string;
  columnCount?: number | null;
  rowCount?: number | null;
}

type SortKey = 'rows' | 'name' | 'columns';

interface TableListProps {
  rows: TableListRow[];
  loading?: boolean;
  showSystem?: boolean;
  onOpen: (row: TableListRow) => void;
  /** Extra filters shown left of the search field. */
  filters?: React.ReactNode;
  emptyText?: string;
  className?: string;
}

const STEP = 200;

export function TableList({ rows, loading, showSystem, onOpen, filters, emptyText, className }: TableListProps) {
  const [q, setQ] = React.useState('');
  const hasEmpty = React.useMemo(() => rows.some(r => !r.rowCount), [rows]);
  const hasData = React.useMemo(() => rows.some(r => !!r.rowCount), [rows]);
  const [onlyData, setOnlyData] = React.useState(true);
  const [sort, setSort] = React.useState<SortKey>('rows');
  const [asc, setAsc] = React.useState(false);
  const [limit, setLimit] = React.useState(STEP);

  const hideEmpty = onlyData && hasData;

  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    const out = rows.filter(r => {
      if (hideEmpty && !r.rowCount) return false;
      if (!needle) return true;
      return `${r.service || ''} ${r.schemaName} ${r.tableName}`.toLowerCase().includes(needle);
    });
    const dir = asc ? 1 : -1;
    out.sort((a, b) => {
      if (sort === 'name') return dir * a.tableName.localeCompare(b.tableName);
      const av = (sort === 'rows' ? a.rowCount : a.columnCount) || 0;
      const bv = (sort === 'rows' ? b.rowCount : b.columnCount) || 0;
      return dir * (av - bv) || a.tableName.localeCompare(b.tableName);
    });
    return out;
  }, [rows, q, hideEmpty, sort, asc]);

  React.useEffect(() => { setLimit(STEP); }, [q, hideEmpty, sort, asc, rows]);

  const maxRows = React.useMemo(() => Math.max(1, ...filtered.map(r => r.rowCount || 0)), [filtered]);
  const shown = filtered.slice(0, limit);

  const head = (key: SortKey, label: string, right?: boolean) => {
    const on = sort === key;
    return (
      <th className={cn('px-4 py-2.5 text-xs font-medium text-muted-foreground', right ? 'text-right' : 'text-left')} aria-sort={on ? (asc ? 'ascending' : 'descending') : 'none'}>
        <button
          type="button"
          onClick={() => { if (on) setAsc(!asc); else { setSort(key); setAsc(key === 'name'); } }}
          className={cn('inline-flex items-center gap-1 rounded transition-colors hover:text-foreground', on && 'text-foreground')}
        >
          {label}
          <Icon name={on && asc ? 'chevron-up' : 'chevron-down'} className={cn('h-3 w-3', !on && 'opacity-0')} />
        </button>
      </th>
    );
  };

  return (
    <div className={cn('space-y-3', className)}>
      <Toolbar>
        {filters}
        <SearchInput value={q} onChange={setQ} placeholder={showSystem ? 'Search system, schema or table' : 'Search tables'} className="sm:w-72" />
        {hasEmpty && hasData && (
          <label className="flex h-8 cursor-pointer select-none items-center gap-2 rounded-md px-2 text-sm text-muted-foreground hover:text-foreground">
            <input type="checkbox" checked={onlyData} onChange={e => setOnlyData(e.target.checked)} className="h-4 w-4 rounded border-border-strong accent-[hsl(var(--primary))]" />
            Only tables with rows
          </label>
        )}
        <ToolbarSpacer />
        <span className="num text-xs text-muted-foreground" aria-live="polite">
          {loading && !rows.length ? 'Loading…' : `${num(filtered.length)} of ${num(rows.length)} tables`}
        </span>
      </Toolbar>

      <TableShell>
        <table className="w-full text-sm">
          <thead className="border-b border-border">
            <tr>
              {showSystem && <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">System</th>}
              {head('name', 'Table')}
              <th className="hidden px-4 py-2.5 text-left text-xs font-medium text-muted-foreground md:table-cell">Schema</th>
              {head('columns', 'Columns', true)}
              {head('rows', 'Rows', true)}
              <th className="hidden w-[18%] px-4 py-2.5 lg:table-cell" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {loading && !rows.length && Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className="border-b border-border last:border-b-0">
                <td colSpan={6} className="px-4 py-2.5"><div className="shimmer h-5 rounded bg-surface-2" /></td>
              </tr>
            ))}
            {shown.map(r => {
              const sim = showSystem ? simByService(r.service) : undefined;
              return (
                <tr
                  key={`${r.service || ''}.${r.schemaName}.${r.tableName}`}
                  tabIndex={0}
                  role="button"
                  aria-label={`Open ${r.tableName}`}
                  onClick={() => onOpen(r)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(r); } }}
                  className="group cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-surface-2/70 focus-visible:bg-surface-2/70 focus-visible:outline-none"
                >
                  {showSystem && (
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <span className="inline-flex items-center gap-2 text-muted-foreground"><SystemLogo system={sim?.logo || r.service} size="sm" />{sim?.short || r.service}</span>
                    </td>
                  )}
                  <td className="max-w-[320px] truncate px-4 py-2.5 font-medium text-foreground group-hover:text-primary dark:group-hover:text-brand-hi">{r.tableName}</td>
                  <td className="hidden px-4 py-2.5 font-mono text-xs text-muted-foreground md:table-cell">{r.schemaName}</td>
                  <td className="num px-4 py-2.5 text-right text-muted-foreground">{num(r.columnCount)}</td>
                  <td className={cn('num px-4 py-2.5 text-right', r.rowCount ? 'text-foreground' : 'text-subtle-foreground')}>{num(r.rowCount ?? 0)}</td>
                  <td className="hidden px-4 py-2.5 lg:table-cell">
                    <div className="h-1 overflow-hidden rounded-full bg-surface-3">
                      <div className="h-full rounded-full bg-primary/70" style={{ width: `${Math.max(r.rowCount ? 2 : 0, ((r.rowCount || 0) / maxRows) * 100)}%` }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && filtered.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">{rows.length ? 'No table matches your search.' : (emptyText || 'No tables yet.')}</p>
        )}
      </TableShell>

      {filtered.length > limit && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setLimit(limit + STEP)}>Show {Math.min(STEP, filtered.length - limit)} more</Button>
          <Button variant="ghost" size="sm" onClick={() => setLimit(filtered.length)}>Show all {num(filtered.length)}</Button>
        </div>
      )}
    </div>
  );
}
