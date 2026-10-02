import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { X, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Loader2 } from 'lucide-react';
import { sapSimulatorService } from '../../services/sapSimulatorService';
import type { ColumnInfo, ObjectRecordsResponse, ColumnsResponse } from '../../services/sapSimulatorService';

interface SimulatorClientLike {
  getObjectRecords: (schema: string, table: string, limit?: number, offset?: number) => Promise<ObjectRecordsResponse>;
  getObjectColumns: (schema: string, table: string) => Promise<ColumnsResponse>;
}

export interface SAPDataBrowserModalProps {
  isOpen: boolean;
  schema: string;
  table: string;
  onClose: () => void;
  service?: SimulatorClientLike;
  catalogRowCount?: number;
}

const PAGE_SIZE = 25;
const FETCH_RETRIES = 3;

function isNetworkError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return msg.includes('failed to fetch') || msg.includes('network') || msg.includes('load failed');
}

async function withRetry<T>(fn: () => Promise<T>, retries = FETCH_RETRIES): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (!isNetworkError(err) || attempt === retries - 1) throw err;
      await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
    }
  }
  throw lastErr;
}

function visiblePages(current: number, total: number, radius = 2): (number | 'ellipsis')[] {
  if (total <= 1) return [1];
  if (total <= 9) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | 'ellipsis')[] = [1];
  const start = Math.max(2, current - radius);
  const end = Math.min(total - 1, current + radius);
  if (start > 2) pages.push('ellipsis');
  for (let i = start; i <= end; i += 1) pages.push(i);
  if (end < total - 1) pages.push('ellipsis');
  pages.push(total);
  return pages;
}

export function SAPDataBrowserModal({ isOpen, schema, table, onClose, service, catalogRowCount }: SAPDataBrowserModalProps) {
  const client = service ?? sapSimulatorService;
  const clientRef = useRef(client);
  clientRef.current = client;

  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageInput, setPageInput] = useState('1');
  const columnsLoadedRef = useRef(false);
  const requestIdRef = useRef(0);

  const loadPage = useCallback(async (off: number) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const recordsRes = await withRetry(() =>
        clientRef.current.getObjectRecords(schema, table, PAGE_SIZE, off),
      );
      if (requestId !== requestIdRef.current) return;

      setRows(recordsRes.rows);
      setTotal(recordsRes.total);
      setOffset(off);
      setPageInput(String(Math.floor(off / PAGE_SIZE) + 1));

      if (!columnsLoadedRef.current) {
        withRetry(() => clientRef.current.getObjectColumns(schema, table))
          .then((colsRes) => {
            if (requestId !== requestIdRef.current) return;
            setColumns(colsRes.columns);
            columnsLoadedRef.current = true;
          })
          .catch(() => { /* columns are optional; rows already shown */ });
      }
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      const base = err instanceof Error ? err.message : 'Failed to load data';
      const hint = isNetworkError(err)
        ? 'Connection to the simulator API failed. Hard-refresh the page and re-forward port 8082 in Cursor Ports.'
        : base;
      setError(hint);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [schema, table]);

  useEffect(() => {
    if (!isOpen) return;
    columnsLoadedRef.current = false;
    setColumns([]);
    setRows([]);
    setTotal(0);
    setOffset(0);
    setPageInput('1');
    setError(null);
    loadPage(0);
  }, [isOpen, schema, table, loadPage]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pages = useMemo(() => visiblePages(page, totalPages), [page, totalPages]);

  const goToPage = useCallback((targetPage: number) => {
    const clamped = Math.min(Math.max(1, targetPage), totalPages);
    loadPage((clamped - 1) * PAGE_SIZE);
  }, [loadPage, totalPages]);

  const submitPageInput = () => {
    const parsed = Number.parseInt(pageInput, 10);
    if (Number.isFinite(parsed)) goToPage(parsed);
    else setPageInput(String(page));
  };

  const colNames = useMemo(() => {
    if (columns.length > 0) {
      return [...columns].sort((a, b) => a.ordinalPosition - b.ordinalPosition).map((c) => c.columnName);
    }
    if (rows.length > 0) return Object.keys(rows[0]);
    return [];
  }, [columns, rows]);

  const showInitialSkeleton = loading && rows.length === 0 && !error;
  const displayTotal = total > 0 ? total : (catalogRowCount ?? 0);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-background border rounded-xl shadow-2xl w-[90vw] max-w-6xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b shrink-0">
          <div>
            <h2 className="text-lg font-semibold">{table}</h2>
            <p className="text-xs text-muted-foreground">
              {schema} &middot; {displayTotal.toLocaleString()} row(s)
              {error && catalogRowCount != null && total === 0 && (
                <span className="text-destructive"> (catalog count — load failed)</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {columns.length > 0 && (
              <div className="flex gap-1 flex-wrap max-w-md">
                {columns.slice(0, 5).map((c) => <Badge key={c.columnName} variant="outline" className="text-[10px]">{c.dataType}</Badge>)}
                {columns.length > 5 && <Badge variant="outline" className="text-[10px]">+{columns.length - 5}</Badge>}
              </div>
            )}
            <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-4 min-h-[240px]">
          {error ? (
            <div className="flex flex-col items-center py-12 text-center">
              <p className="text-sm text-destructive mb-3">{error}</p>
              <Button variant="outline" size="sm" onClick={() => loadPage(offset)}>Retry</Button>
            </div>
          ) : showInitialSkeleton ? (
            <div className="space-y-2">{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-8 rounded" />)}</div>
          ) : colNames.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-12">No data</p>
          ) : (
            <div className={`rounded-md border overflow-auto relative ${loading ? 'opacity-60 pointer-events-none' : ''}`}>
              {loading && (
                <div className="absolute top-2 right-2 z-10 rounded bg-background/90 border px-2 py-1 text-xs flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> Loading…
                </div>
              )}
              <table className="w-full text-xs whitespace-nowrap">
                <thead><tr className="bg-muted/50">{colNames.map((col) => <th key={col} className="px-3 py-2 font-medium text-left border-r last:border-r-0">{col}</th>)}</tr></thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t hover:bg-muted/20">
                      {colNames.map((col) => (
                        <td key={col} className="px-3 py-1.5 border-r last:border-r-0 max-w-[300px] truncate">
                          {row[col] == null ? <span className="text-muted-foreground italic">null</span> : String(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-t text-sm shrink-0 min-h-[52px]">
          <p className="text-muted-foreground shrink-0">
            Showing {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {displayTotal.toLocaleString()}
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button variant="outline" size="icon" className="h-8 w-8 shrink-0" disabled={page <= 1 || loading} onClick={() => goToPage(1)} title="First page">
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" className="h-8 shrink-0" disabled={page <= 1 || loading} onClick={() => goToPage(page - 1)}>
              <ChevronLeft className="h-4 w-4 mr-1" />Prev
            </Button>
            {pages.map((p, idx) =>
              p === 'ellipsis' ? (
                <span key={`ellipsis-${idx}`} className="px-1 text-muted-foreground select-none">…</span>
              ) : (
                <Button
                  key={p}
                  variant={p === page ? 'default' : 'outline'}
                  size="sm"
                  className="h-8 min-w-8 px-2 shrink-0"
                  disabled={loading}
                  onClick={() => goToPage(p)}
                >
                  {p}
                </Button>
              ),
            )}
            <Button variant="outline" size="sm" className="h-8 shrink-0" disabled={page >= totalPages || loading} onClick={() => goToPage(page + 1)}>
              Next<ChevronRight className="h-4 w-4 ml-1" />
            </Button>
            <Button variant="outline" size="icon" className="h-8 w-8 shrink-0" disabled={page >= totalPages || loading} onClick={() => goToPage(totalPages)} title="Last page">
              <ChevronsRight className="h-4 w-4" />
            </Button>
            <form
              className="flex items-center gap-1 ml-1 shrink-0"
              onSubmit={(e) => { e.preventDefault(); submitPageInput(); }}
            >
              <input
                type="number"
                min={1}
                max={totalPages}
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                className="h-8 w-16 rounded-md border bg-background px-2 text-xs"
                aria-label="Go to page"
              />
              <Button type="submit" variant="outline" size="sm" className="h-8" disabled={loading}>Go</Button>
            </form>
            <span className="text-xs text-muted-foreground whitespace-nowrap ml-1 shrink-0">Page {page} / {totalPages}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SAPDataBrowserModal;
