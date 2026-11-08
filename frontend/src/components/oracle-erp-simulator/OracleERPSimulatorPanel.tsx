import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '../ui/button';
import { useToast } from '../../hooks/use-toast';
import { RefreshCw, Download, Trash2, Loader2, AlertCircle } from 'lucide-react';

import { OracleERPObjectsTable } from './OracleERPObjectsTable';
import { SimulatorArtifactStatusCard } from '@/components/simulator-shared/SimulatorArtifactStatusCard';
import { artifactMetaFromStatus } from '@/components/simulator-shared/simulatorArtifactMeta';
import { artifactKpiStats, KpiStatGrid } from '@/components/simulator-shared/artifactKpiStats';
import { ArtifactModalityEmpty, SimulatorDeliveryTabs } from '@/components/simulator-shared/SimulatorDeliveryTabs';
import { OracleERPDataBrowserModal } from './OracleERPDataBrowserModal';
import { OracleERPActivityLog } from './OracleERPActivityLog';

import {
  oracleErpSimulatorService,
  type SimulatorStatus,
  type ObjectSummary,
  type SimulatorError,
  type StepEntry,
} from '../../services/oracleErpSimulatorService';

interface PanelState {
  status: SimulatorStatus | null;
  objects: ObjectSummary[];
  loadingStatus: boolean;
  loadingObjects: boolean;
  statusError: string | null;
  objectsError: string | null;
}

export function OracleERPSimulatorPanel() {
  const { toast } = useToast();

  const [state, setState] = useState<PanelState>({
    status: null, objects: [],
    loadingStatus: true, loadingObjects: false,
    statusError: null, objectsError: null,
  });

  const [isLoadingData, setIsLoadingData] = useState(false);
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
      const status = await oracleErpSimulatorService.getStatus();
      setState(s => ({ ...s, status, loadingStatus: false }));
      setConnectionError(null);
    } catch (err) {
      const e = err as SimulatorError;
      const msg = e.message || 'Failed to connect';
      setState(s => ({ ...s, loadingStatus: false, statusError: msg }));
      if (e.type === 'network') setConnectionError(msg);
    }
  }, []);

  const fetchObjects = useCallback(async () => {
    setState(s => ({ ...s, loadingObjects: true, objectsError: null }));
    try {
      const res = await oracleErpSimulatorService.getObjects();
      setState(s => ({ ...s, objects: res.objects, loadingObjects: false }));
    } catch (err) {
      setState(s => ({ ...s, loadingObjects: false, objectsError: (err as SimulatorError).message || 'Failed' }));
    }
  }, []);

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
        setLoadRunning(false); setIsLoadingData(false);
        toast({ title: 'Load timed out', variant: 'destructive' });
        return;
      }
      try {
        const s = await oracleErpSimulatorService.getLoadStatus();
        errorCount = 0;
        setLoadSteps(s.steps || []);
        if (!s.running) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false); setIsLoadingData(false);
          await refreshAll();
          toast({ title: s.result?.success === false ? 'Load Failed' : 'Data Loaded', description: s.result?.message as string || 'Load complete', variant: s.result?.success === false ? 'destructive' : undefined });
        }
      } catch {
        errorCount++;
        if (errorCount >= 5) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false); setIsLoadingData(false);
          toast({ title: 'Lost connection', variant: 'destructive' });
        }
      }
    };
    tick();
    loadPollRef.current = setInterval(tick, 2000);
  }, [refreshAll, toast]);

  const handleLoad = async () => {
    setIsLoadingData(true); setLoadRunning(true); setLoadSteps([]);
    try { await oracleErpSimulatorService.loadData(); pollLoadStatus(); }
    catch (err) { setIsLoadingData(false); setLoadRunning(false); toast({ title: 'Load Failed', description: (err as SimulatorError).message, variant: 'destructive' }); }
  };

  const handleReset = async () => {
    setIsResetting(true); setLoadRunning(true); setLoadSteps([]);
    try { await oracleErpSimulatorService.resetData(); pollLoadStatus(); }
    catch (err) { setIsResetting(false); setLoadRunning(false); toast({ title: 'Reset Failed', description: (err as SimulatorError).message, variant: 'destructive' }); }
    finally { setIsResetting(false); }
  };

  const handleSelectObject = (schema: string, table: string) => { setSelectedSchema(schema); setSelectedTable(table); setBrowserOpen(true); };

  const artifactMeta = artifactMetaFromStatus(state.status);
  const stats = artifactMeta ? artifactKpiStats(artifactMeta) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Oracle ERP Simulator</h1>
          <p className="text-sm text-muted-foreground">Manage in-memory Oracle ERP simulator data for finance and operations</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={state.loadingStatus}>
            <RefreshCw className={`h-4 w-4 mr-2 ${state.loadingStatus ? 'animate-spin' : ''}`} />Refresh
          </Button>
          <Button size="sm" onClick={handleLoad} disabled={isLoadingData || state.loadingStatus}>
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
        <OracleERPActivityLog title={loadRunning ? 'Loading Data from S3...' : 'Load Complete'} steps={loadSteps} running={loadRunning} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SimulatorArtifactStatusCard
          meta={artifactMeta}
          isLoading={state.loadingStatus}
          error={state.statusError}
          onRefresh={fetchStatus}
        />
        <KpiStatGrid stats={stats} />
      </div>

      <SimulatorDeliveryTabs
        counts={{
          table: artifactMeta?.tableCount,
          file: artifactMeta?.fileCount,
          api: artifactMeta?.apiCount,
          stream: artifactMeta?.streamCount,
        }}
        tables={
          <OracleERPObjectsTable
            objects={state.objects}
            isLoading={state.loadingObjects}
            error={state.objectsError}
            onSelectObject={handleSelectObject}
          />
        }
        files={<ArtifactModalityEmpty modality="File" hint="Oracle ERP simulator loads FDW table data from S3." />}
        apis={<ArtifactModalityEmpty modality="API" />}
        streams={<ArtifactModalityEmpty modality="Stream" />}
      />
      <OracleERPDataBrowserModal isOpen={browserOpen} schema={selectedSchema} table={selectedTable} onClose={() => setBrowserOpen(false)} />
    </div>
  );
}

export default OracleERPSimulatorPanel;
