import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Skeleton } from '../ui/skeleton';
import { Search, TableProperties, AlertTriangle } from 'lucide-react';
import type { ObjectSummary } from '../../services/sapSimulatorService';

export interface SAPObjectsTableProps {
  objects: ObjectSummary[];
  isLoading: boolean;
  error: string | null;
  onSelectObject: (schema: string, table: string) => void;
  /** Card title (default: Table Data) */
  title?: string;
  emptyMessage?: string;
  filterPlaceholder?: string;
}

type SortKey = 'schemaName' | 'tableName' | 'columnCount' | 'rowCount';

export function SAPObjectsTable({
  objects,
  isLoading,
  error,
  onSelectObject,
  title = 'Table Data',
  emptyMessage = 'No objects loaded. Click "Load Data" to load from S3.',
  filterPlaceholder = 'Filter table data...',
}: SAPObjectsTableProps) {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('tableName');
  const [sortAsc, setSortAsc] = useState(true);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let list = objects.filter(o => o.tableName.toLowerCase().includes(q) || o.schemaName.toLowerCase().includes(q));
    list.sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return list;
  }, [objects, search, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => { if (sortKey === key) { setSortAsc(!sortAsc); } else { setSortKey(key); setSortAsc(true); } };
  const sortIndicator = (key: SortKey) => sortKey === key ? (sortAsc ? ' ↑' : ' ↓') : '';

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10 rounded" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card><CardHeader><CardTitle className="text-lg">{title}</CardTitle></CardHeader>
        <CardContent><div className="flex flex-col items-center py-6 text-center"><AlertTriangle className="h-8 w-8 text-yellow-500 mb-2" /><p className="text-sm text-muted-foreground">{error}</p></div></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-2">
          <TableProperties className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-lg">{title}</CardTitle>
          <span className="text-xs text-muted-foreground">({filtered.length})</span>
        </div>
        <div className="relative w-56">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder={filterPlaceholder} value={search} onChange={e => setSearch(e.target.value)} className="pl-8 h-9 text-sm" />
        </div>
      </CardHeader>
      <CardContent>
        {objects.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">{emptyMessage}</p>
        ) : (
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="bg-muted/50 text-left">
                <th className="px-3 py-2 font-medium cursor-pointer hover:bg-muted" onClick={() => handleSort('schemaName')}>Schema{sortIndicator('schemaName')}</th>
                <th className="px-3 py-2 font-medium cursor-pointer hover:bg-muted" onClick={() => handleSort('tableName')}>Table{sortIndicator('tableName')}</th>
                <th className="px-3 py-2 font-medium text-right cursor-pointer hover:bg-muted" onClick={() => handleSort('columnCount')}>Columns{sortIndicator('columnCount')}</th>
                <th className="px-3 py-2 font-medium text-right cursor-pointer hover:bg-muted" onClick={() => handleSort('rowCount')}>Rows{sortIndicator('rowCount')}</th>
              </tr></thead>
              <tbody>
                {filtered.map(obj => (
                  <tr key={`${obj.schemaName}.${obj.tableName}`} className="border-t hover:bg-muted/30 cursor-pointer transition-colors" onClick={() => onSelectObject(obj.schemaName, obj.tableName)}>
                    <td className="px-3 py-2 text-muted-foreground">{obj.schemaName}</td>
                    <td className="px-3 py-2 font-medium">{obj.tableName}</td>
                    <td className="px-3 py-2 text-right">{obj.columnCount}</td>
                    <td className="px-3 py-2 text-right">{obj.rowCount.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default SAPObjectsTable;
