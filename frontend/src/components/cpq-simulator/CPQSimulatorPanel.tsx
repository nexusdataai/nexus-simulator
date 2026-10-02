import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '../ui/button';
import { useToast } from '../../hooks/use-toast';
import { RefreshCw, Download, Trash2, Loader2, AlertCircle, Sparkles } from 'lucide-react';

import { SAPStatusCard } from '../sap-simulator/SAPStatusCard';
import { SAPObjectsTable } from '../sap-simulator/SAPObjectsTable';
import { SAPDataBrowserModal } from '../sap-simulator/SAPDataBrowserModal';
import { SAPActivityLog } from '../sap-simulator/SAPActivityLog';

import type { CPQSimulatorService } from '../../services/cpqSimulatorService';
import type {
  SimulatorStatus,
  ObjectSummary,
  SimulatorError,
  StepEntry,
} from '../../services/sapSimulatorService';

interface Props {
  service: CPQSimulatorService;
  title: string;
  subtitle: string;
}

interface PanelState {
  status: SimulatorStatus | null;
  objects: ObjectSummary[];
  loadingStatus: boolean;
  loadingObjects: boolean;
  statusError: string | null;
  objectsError: string | null;
}

// Generic CPQ simulator admin panel. Reuses the SAP simulator's
// status card / objects table / data browser modal / activity log
// because the response shapes are identical across simulators.
export function CPQSimulatorPanel({ service, title, subtitle }: Props) {
  const { toast } = useToast();

  const [state, setState] = useState<PanelState>({
    status: null, objects: [],
    loadingStatus: true, loadingObjects: false,
    statusError: null, objectsError: null,
  });

  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const [browserOpen, setBrowserOpen] = useState(false);
  const [selectedSchema, setSelectedSchema] = useState('');
  const [selectedTable, setSelectedTable] = useState('');

  const [loadSteps, setLoadSteps] = useState<StepEntry[]>([]);
  const [loadRunning, setLoadRunning] = useState(false);
  const loadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    setState(s => ({ ...s, loadingStatus: true, statusError: null }));
    try {
      const status = await service.getStatus();
      setState(s => ({ ...s, status, loadingStatus: false }));
      setConnectionError(null);
    } catch (err) {
      const e = err as SimulatorError;
      const msg = e.message || 'Failed to connect';
      setState(s => ({ ...s, loadingStatus: false, statusError: msg }));
      if (e.type === 'network') setConnectionError(msg);
    }
  }, [service]);

  const fetchObjects = useCallback(async () => {
    setState(s => ({ ...s, loadingObjects: true, objectsError: null }));
    try {
      const res = await service.getObjects();
      setState(s => ({ ...s, objects: res.objects, loadingObjects: false }));
    } catch (err) {
      setState(s => ({ ...s, loadingObjects: false, objectsError: (err as SimulatorError).message || 'Failed' }));
    }
  }, [service]);

  const refreshAll = useCallback(async () => { await fetchStatus(); await fetchObjects(); }, [fetchStatus, fetchObjects]);
  useEffect(() => { refreshAll(); }, [refreshAll]);
  useEffect(() => { return () => { if (loadPollRef.current) clearInterval(loadPollRef.current); }; }, []);

  const pollLoadStatus = useCallback(() => {
    if (loadPollRef.current) clearInterval(loadPollRef.current);
    let errorCount = 0;
    const startTime = Date.now();
    const MAX_POLL_MS = 5 * 60 * 1000;
    const tick = async () => {
      if (Date.now() - startTime > MAX_POLL_MS) {
        if (loadPollRef.current) clearInterval(loadPollRef.current);
        loadPollRef.current = null;
        setLoadRunning(false); setIsLoadingData(false); setIsSeeding(false);
        toast({ title: 'Load timed out', variant: 'destructive' });
        return;
      }
      try {
        const s = await service.getLoadStatus();
        errorCount = 0;
        setLoadSteps(s.steps || []);
        if (!s.running) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false); setIsLoadingData(false); setIsSeeding(false);
          await refreshAll();
          const result = s.result as { success?: boolean; message?: string } | undefined;
          toast({
            title: result?.success === false ? 'Load Failed' : 'Data Loaded',
            description: result?.message ?? 'Load complete',
            variant: result?.success === false ? 'destructive' : undefined,
          });
        }
      } catch {
        errorCount++;
        if (errorCount >= 5) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false); setIsLoadingData(false); setIsSeeding(false);
          toast({ title: 'Lost connection', variant: 'destructive' });
        }
      }
    };
    tick();
    loadPollRef.current = setInterval(tick, 2000);
  }, [refreshAll, service, toast]);

  const handleLoad = async () => {
    setIsLoadingData(true); setLoadRunning(true); setLoadSteps([]);
    try { await service.loadData(); pollLoadStatus(); }
    catch (err) { setIsLoadingData(false); setLoadRunning(false); toast({ title: 'Load Failed', description: (err as SimulatorError).message, variant: 'destructive' }); }
  };

  const handleSeed = async () => {
    setIsSeeding(true); setLoadRunning(true); setLoadSteps([]);
    try { await service.seedData(); pollLoadStatus(); }
    catch (err) { setIsSeeding(false); setLoadRunning(false); toast({ title: 'Seed Failed', description: (err as SimulatorError).message, variant: 'destructive' }); }
  };

  const handleReset = async () => {
    setIsResetting(true); setLoadRunning(true); setLoadSteps([]);
    try { await service.resetData(); pollLoadStatus(); }
    catch (err) { setIsResetting(false); setLoadRunning(false); toast({ title: 'Reset Failed', description: (err as SimulatorError).message, variant: 'destructive' }); }
    finally { setIsResetting(false); }
  };

  const handleSelectObject = (schema: string, table: string) => {
    setSelectedSchema(schema); setSelectedTable(table); setBrowserOpen(true);
  };

  const stats = state.status ? [
    { label: 'Tables', value: state.status.table_count, color: 'text-blue-400' },
    { label: 'With Data', value: state.status.tables_with_data, color: 'text-green-400' },
    { label: 'Total Rows', value: state.status.total_rows.toLocaleString(), color: 'text-purple-400' },
  ] : [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={state.loadingStatus}>
            <RefreshCw className={`h-4 w-4 mr-2 ${state.loadingStatus ? 'animate-spin' : ''}`} />Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleSeed} disabled={isSeeding || isLoadingData || state.loadingStatus}>
            {isSeeding ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}Seed
          </Button>
          <Button size="sm" onClick={handleLoad} disabled={isLoadingData || isSeeding || state.loadingStatus}>
            {isLoadingData ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}Load Data
          </Button>
          <Button variant="destructive" size="sm" onClick={handleReset} disabled={isResetting || state.loadingStatus}>
            {isResetting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Trash2 className="h-4 w-4 mr-2" />}Reset
          </Button>
        </div>
      </div>

      {connectionError && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-5 w-5 shrink-0" /><p>{connectionError}</p>
        </div>
      )}

      {(loadRunning || loadSteps.length > 0) && (
        <SAPActivityLog title={loadRunning ? 'Loading…' : 'Load Complete'} steps={loadSteps} running={loadRunning} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SAPStatusCard status={state.status} isLoading={state.loadingStatus} error={state.statusError} onRefresh={fetchStatus} />
        {stats.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            {stats.map(s => (
              <div key={s.label} className="rounded-lg border bg-card p-4 flex flex-col items-center justify-center">
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <SAPObjectsTable objects={state.objects} isLoading={state.loadingObjects} error={state.objectsError} onSelectObject={handleSelectObject} />
      <SAPDataBrowserModal isOpen={browserOpen} schema={selectedSchema} table={selectedTable} onClose={() => setBrowserOpen(false)} service={service} />
    </div>
  );
}
