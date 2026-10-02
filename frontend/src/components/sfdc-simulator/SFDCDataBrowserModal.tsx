import { useState, useEffect, useCallback } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { X, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { sfdcSimulatorService } from '../../services/sfdcSimulatorService';
import type { SFDCColumnInfo } from '../../services/sfdcSimulatorService';

export interface SFDCDataBrowserModalProps {
  isOpen: boolean;
  schema: string;
  table: string;
  onClose: () => void;
}

const PAGE_SIZE = 25;

export function SFDCDataBrowserModal({ isOpen, schema, table, onClose }: SFDCDataBrowserModalProps) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<SFDCColumnInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (off: number) => {
    setLoading(true);
    setError(null);
    try {
      const [recordsRes, colsRes] = await Promise.all([
        sfdcSimulatorService.getObjectRecords(schema, table, PAGE_SIZE, off),
        columns.length === 0 ? sfdcSimulatorService.getObjectColumns(schema, table) : Promise.resolve(null),
      ]);
      setRows(recordsRes.rows);
      setTotal(recordsRes.total);
      setOffset(off);
      if (colsRes) setColumns(colsRes.columns);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [schema, table, columns.length]);

  useEffect(() => {
    if (isOpen) {
      setColumns([]);
      setOffset(0);
      fetchData(0);
    }
  }, [isOpen, schema, table]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isOpen) return null;

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const colNames = columns.length > 0
    ? columns.sort((a, b) => a.ordinalPosition - b.ordinalPosition).map(c => c.columnName)
    : rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-background border rounded-xl shadow-2xl w-[90vw] max-w-6xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold">{table}</h2>
            <p className="text-xs text-muted-foreground">{schema} &middot; {total.toLocaleString()} row(s)</p>
          </div>
          <div className="flex items-center gap-2">
            {columns.length > 0 && (
              <div className="flex gap-1 flex-wrap max-w-md">
                {columns.slice(0, 5).map(c => (
                  <Badge key={c.columnName} variant="outline" className="text-[10px]">{c.dataType}</Badge>
                ))}
                {columns.length > 5 && <Badge variant="outline" className="text-[10px]">+{columns.length - 5}</Badge>}
              </div>
            )}
            <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4">
          {error ? (
            <div className="flex flex-col items-center py-12 text-center">
              <p className="text-sm text-destructive mb-3">{error}</p>
              <Button variant="outline" size="sm" onClick={() => fetchData(offset)}>Retry</Button>
            </div>
          ) : loading && rows.length === 0 ? (
            <div className="space-y-2">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-8 rounded" />)}</div>
          ) : colNames.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-12">No data</p>
          ) : (
            <div className="rounded-md border overflow-auto">
              <table className="w-full text-xs whitespace-nowrap">
                <thead>
                  <tr className="bg-muted/50">
                    {colNames.map(col => (
                      <th key={col} className="px-3 py-2 font-medium text-left border-r last:border-r-0">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t hover:bg-muted/20">
                      {colNames.map(col => (
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

        {/* Footer / pagination */}
        <div className="flex items-center justify-between px-5 py-3 border-t text-sm">
          <p className="text-muted-foreground">
            {loading && <Loader2 className="h-3 w-3 inline animate-spin mr-1" />}
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total.toLocaleString()}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0 || loading} onClick={() => fetchData(offset - PAGE_SIZE)}>
              <ChevronLeft className="h-4 w-4 mr-1" />Prev
            </Button>
            <span className="text-xs text-muted-foreground">Page {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => fetchData(offset + PAGE_SIZE)}>
              Next<ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SFDCDataBrowserModal;
