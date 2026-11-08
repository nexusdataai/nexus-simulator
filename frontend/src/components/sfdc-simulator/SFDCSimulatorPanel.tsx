import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '../ui/button';
import { useToast } from '../../hooks/use-toast';
import { RefreshCw, Download, Trash2, Loader2, AlertCircle } from 'lucide-react';

import { SFDCObjectsTable } from './SFDCObjectsTable';
import { SimulatorArtifactStatusCard } from '@/components/simulator-shared/SimulatorArtifactStatusCard';
import { artifactMetaFromStatus } from '@/components/simulator-shared/simulatorArtifactMeta';
import { artifactKpiStats, KpiStatGrid } from '@/components/simulator-shared/artifactKpiStats';
import { ArtifactModalityEmpty, SimulatorDeliveryTabs } from '@/components/simulator-shared/SimulatorDeliveryTabs';
import { SFDCDataBrowserModal } from './SFDCDataBrowserModal';
import { SFDCDumpSection } from './SFDCDumpSection';
import { SFDCActivityLog } from './SFDCActivityLog';

import {
  sfdcSimulatorService,
  type SFDCSimulatorStatus,
  type SFDCObjectSummary,
  type SFDCSimulatorError,
  type SFDCStepEntry,
} from '../../services/sfdcSimulatorService';

interface PanelState {
  status: SFDCSimulatorStatus | null;
  objects: SFDCObjectSummary[];
  loadingStatus: boolean;
  loadingObjects: boolean;
  statusError: string | null;
  objectsError: string | null;
}

export function SFDCSimulatorPanel() {
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

  const [loadSteps, setLoadSteps] = useState<SFDCStepEntry[]>([]);
  const [loadRunning, setLoadRunning] = useState(false);
  const loadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    setState(s => ({ ...s, loadingStatus: true, statusError: null }));
    try {
      const status = await sfdcSimulatorService.getStatus();
      setState(s => ({ ...s, status, loadingStatus: false }));
      setConnectionError(null);
    } catch (err) {
      const e = err as SFDCSimulatorError;
      const msg = e.message || 'Failed to connect';
      setState(s => ({ ...s, loadingStatus: false, statusError: msg }));
      if (e.type === 'network') setConnectionError(msg);
    }
  }, []);

  const fetchObjects = useCallback(async () => {
    setState(s => ({ ...s, loadingObjects: true, objectsError: null }));
    try {
      const res = await sfdcSimulatorService.getObjects();
      setState(s => ({ ...s, objects: res.objects, loadingObjects: false }));
    } catch (err) {
      setState(s => ({ ...s, loadingObjects: false, objectsError: (err as SFDCSimulatorError).message || 'Failed' }));
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await fetchStatus();
    await fetchObjects();
  }, [fetchStatus, fetchObjects]);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  useEffect(() => {
    return () => { if (loadPollRef.current) clearInterval(loadPollRef.current); };
  }, []);

  const pollLoadStatus = useCallback(() => {
    if (loadPollRef.current) clearInterval(loadPollRef.current);
    let errorCount = 0;
    const startTime = Date.now();
    const MAX_POLL_MS = 5 * 60 * 1000;

    const tick = async () => {
      if (Date.now() - startTime > MAX_POLL_MS) {
        if (loadPollRef.current) clearInterval(loadPollRef.current);
        loadPollRef.current = null;
        setLoadRunning(false);
        setIsLoadingData(false);
        toast({ title: 'Load timed out', description: 'No completion signal after 5 minutes', variant: 'destructive' });
        return;
      }
      try {
        const s = await sfdcSimulatorService.getLoadStatus();
        errorCount = 0;
        setLoadSteps(s.steps || []);
        if (!s.running) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false);
          setIsLoadingData(false);
          await refreshAll();
          toast({ title: s.result?.success === false ? 'Load Failed' : 'Data Loaded', description: s.result?.message as string || 'Load complete', variant: s.result?.success === false ? 'destructive' : undefined });
        }
      } catch {
        errorCount++;
        if (errorCount >= 5) {
          if (loadPollRef.current) clearInterval(loadPollRef.current);
          loadPollRef.current = null;
          setLoadRunning(false);
          setIsLoadingData(false);
          toast({ title: 'Lost connection', description: 'Could not reach simulator status after 5 retries', variant: 'destructive' });
        }
      }
    };

    tick();
    loadPollRef.current = setInterval(tick, 2000);
  }, [refreshAll, toast]);

  const handleLoad = async () => {
    setIsLoadingData(true);
    setLoadRunning(true);
    setLoadSteps([]);
    try {
      await sfdcSimulatorService.loadData();
      pollLoadStatus();
    } catch (err) {
      setIsLoadingData(false);
      setLoadRunning(false);
      toast({ title: 'Load Failed', description: (err as SFDCSimulatorError).message, variant: 'destructive' });
    }
  };

  const handleReset = async () => {
    setIsResetting(true);
    setLoadRunning(true);
    setLoadSteps([]);
    try {
      await sfdcSimulatorService.resetData();
      pollLoadStatus();
    } catch (err) {
      setIsResetting(false);
      setLoadRunning(false);
      toast({ title: 'Reset Failed', description: (err as SFDCSimulatorError).message, variant: 'destructive' });
    } finally {
      setIsResetting(false);
    }
  };

  const handleSelectObject = (schema: string, table: string) => {
    setSelectedSchema(schema);
    setSelectedTable(table);
    setBrowserOpen(true);
  };

  const artifactMeta = artifactMetaFromStatus(state.status);
  const stats = artifactMeta ? artifactKpiStats(artifactMeta) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Salesforce Simulator</h1>
          <p className="text-sm text-muted-foreground">Manage in-memory table data for testing</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={state.loadingStatus}>
            <RefreshCw className={`h-4 w-4 mr-2 ${state.loadingStatus ? 'animate-spin' : ''}`} />Refresh
          </Button>
          <Button size="sm" onClick={handleLoad} disabled={isLoadingData || state.loadingStatus}>
            {isLoadingData ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            Load Data
          </Button>
          <Button variant="destructive" size="sm" onClick={handleReset} disabled={isResetting || state.loadingStatus}>
            {isResetting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Trash2 className="h-4 w-4 mr-2" />}
            Reset
          </Button>
        </div>
      </div>

      {/* Connection error banner */}
      {connectionError && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p>{connectionError}</p>
        </div>
      )}

      {/* Load activity log */}
      {(loadRunning || loadSteps.length > 0) && (
        <SFDCActivityLog
          title={loadRunning ? 'Loading Data from S3...' : 'Load Complete'}
          steps={loadSteps}
          running={loadRunning}
        />
      )}

      {/* Status + Statistics row */}
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
          <SFDCObjectsTable
            objects={state.objects}
            isLoading={state.loadingObjects}
            error={state.objectsError}
            onSelectObject={handleSelectObject}
          />
        }
        files={
          <ArtifactModalityEmpty
            modality="File"
            hint="Salesforce simulator loads table data from S3; file exports are not part of this plugin."
          />
        }
        apis={
          <ArtifactModalityEmpty modality="API" hint="Vendor REST stubs are available on telecom backbone simulators." />
        }
        streams={
          <ArtifactModalityEmpty modality="Stream" hint="Event streams are generated on telecom backbone simulators." />
        }
      />

      {/* Dump from live FDW */}
      <SFDCDumpSection />

      {/* Data browser modal */}
      <SFDCDataBrowserModal
        isOpen={browserOpen}
        schema={selectedSchema}
        table={selectedTable}
        onClose={() => setBrowserOpen(false)}
      />
    </div>
  );
}

export default SFDCSimulatorPanel;
