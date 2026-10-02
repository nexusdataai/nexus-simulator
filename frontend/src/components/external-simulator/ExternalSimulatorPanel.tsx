import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  RefreshCw, Loader2, Database, FileText, Globe, Radio,
  Upload, ChevronRight, CheckCircle2, XCircle,
} from 'lucide-react';
import {
  externalSimulatorService,
  type ExternalSimulatorStatus,
  type ExternalObjectSummary,
  type ExternalRecordsResponse,
} from '../../services/externalSimulatorService';

const SYSTEM_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  Google_Drive: { label: 'Google Drive', icon: Globe, color: 'text-red-400' },
  Social_Listening: { label: 'Social Listening', icon: Radio, color: 'text-pink-400' },
  File_Uploads: { label: 'File Uploads', icon: Upload, color: 'text-purple-400' },
};

export function ExternalSimulatorPanel() {
  const [status, setStatus] = useState<ExternalSimulatorStatus | null>(null);
  const [objects, setObjects] = useState<ExternalObjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedTable, setSelectedTable] = useState<ExternalObjectSummary | null>(null);
  const [records, setRecords] = useState<ExternalRecordsResponse | null>(null);
  const [recordsLoading, setRecordsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, o] = await Promise.all([
        externalSimulatorService.getStatus(),
        externalSimulatorService.getObjects().catch(() => ({ objects: [] })),
      ]);
      setStatus(s);
      setObjects(o.objects || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const pollUntilLoaded = useCallback(async () => {
    for (let i = 0; i < 15; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const s = await externalSimulatorService.getStatus();
        if (s.loaded) { await refresh(); return; }
      } catch { /* retry */ }
    }
    await refresh();
  }, [refresh]);

  const handleSeed = async () => {
    setSeeding(true);
    setError(null);
    try {
      await externalSimulatorService.seedData();
      await pollUntilLoaded();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  };

  const handleReset = async () => {
    setSeeding(true);
    setError(null);
    try {
      await externalSimulatorService.resetData();
      await pollUntilLoaded();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  };

  const handleSelectTable = async (obj: ExternalObjectSummary) => {
    setSelectedTable(obj);
    setRecordsLoading(true);
    try {
      const data = await externalSimulatorService.getRecords(obj.schemaName, obj.tableName, 20);
      setRecords(data);
    } catch {
      setRecords(null);
    } finally {
      setRecordsLoading(false);
    }
  };

  const grouped = objects.reduce<Record<string, ExternalObjectSummary[]>>((acc, o) => {
    (acc[o.system] ??= []).push(o);
    return acc;
  }, {});

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">External Source Simulators</h2>
          <p className="text-sm text-muted-foreground">
            Google Drive, Social Listening, and File Uploads — unified in-memory simulator
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleSeed} disabled={seeding}>
            {seeding ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Database className="h-4 w-4 mr-1" />}
            Seed Data
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset} disabled={seeding}>
            Reset
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Status Cards */}
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <div className="flex items-center gap-2 mt-1">
                    {status.loaded ? (
                      <Badge className="bg-green-100 text-green-800 border-green-200">
                        <CheckCircle2 className="h-3 w-3 mr-1" />Loaded
                      </Badge>
                    ) : (
                      <Badge variant="outline">
                        <XCircle className="h-3 w-3 mr-1" />Not Loaded
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground">Tables</p>
              <p className="text-2xl font-bold">{status.table_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground">Total Rows</p>
              <p className="text-2xl font-bold">{status.total_rows.toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground">Last Loaded</p>
              <p className="text-sm font-medium">{status.last_loaded ? new Date(status.last_loaded).toLocaleString() : 'Never'}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* System breakdown + table list + data browser */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: table list grouped by system */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Tables by System</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[400px]">
              {Object.entries(grouped).length === 0 && !loading && (
                <div className="p-4 text-sm text-muted-foreground text-center">
                  No tables loaded. Click "Seed Data" to generate synthetic data.
                </div>
              )}
              {Object.entries(grouped).map(([sys, tables]) => {
                const meta = SYSTEM_META[sys] || { label: sys, icon: Database, color: 'text-muted-foreground' };
                const Icon = meta.icon;
                return (
                  <div key={sys} className="border-b last:border-b-0">
                    <div className="flex items-center gap-2 px-4 py-2 bg-muted/30">
                      <Icon className={`h-4 w-4 ${meta.color}`} />
                      <span className="text-xs font-semibold">{meta.label}</span>
                      <Badge variant="outline" className="text-[10px] ml-auto">
                        {tables.reduce((s, t) => s + t.rowCount, 0).toLocaleString()} rows
                      </Badge>
                    </div>
                    {tables.map(t => (
                      <button
                        key={t.tableName}
                        onClick={() => handleSelectTable(t)}
                        className={`w-full flex items-center justify-between px-4 py-2 text-left text-sm hover:bg-muted/20 transition-colors ${selectedTable?.tableName === t.tableName ? 'bg-primary/10 border-l-2 border-primary' : ''}`}
                      >
                        <div className="flex items-center gap-2">
                          <FileText className="h-3 w-3 text-muted-foreground" />
                          <span>{t.tableName}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{t.rowCount} rows</span>
                          <ChevronRight className="h-3 w-3" />
                        </div>
                      </button>
                    ))}
                  </div>
                );
              })}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Right: data browser */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {selectedTable ? `${selectedTable.tableName}` : 'Select a table to preview data'}
            </CardTitle>
            {selectedTable && (
              <p className="text-xs text-muted-foreground">
                {SYSTEM_META[selectedTable.system]?.label || selectedTable.system} — {selectedTable.rowCount} rows, {selectedTable.columnCount} columns
              </p>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[400px]">
              {recordsLoading ? (
                <div className="flex items-center justify-center h-full"><Loader2 className="h-5 w-5 animate-spin" /></div>
              ) : records && records.rows.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-muted/30 sticky top-0">
                        {Object.keys(records.rows[0]).map(col => (
                          <th key={col} className="px-3 py-2 text-left text-muted-foreground font-medium whitespace-nowrap">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {records.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-muted/20">
                          {Object.values(row).map((val, j) => (
                            <td key={j} className="px-3 py-1.5 font-mono whitespace-nowrap max-w-[200px] truncate">{String(val ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {records.total > records.rows.length && (
                    <div className="p-2 text-center text-xs text-muted-foreground">
                      Showing {records.rows.length} of {records.total} rows
                    </div>
                  )}
                </div>
              ) : selectedTable ? (
                <div className="flex items-center justify-center h-full text-sm text-muted-foreground">No data available</div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-sm text-muted-foreground gap-2">
                  <Database className="h-8 w-8 opacity-30" />
                  <span>Click a table on the left to browse data</span>
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default ExternalSimulatorPanel;
