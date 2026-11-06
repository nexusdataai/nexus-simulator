import { useState, useEffect, useCallback, useRef } from 'react';
import { useToast } from '../../hooks/use-toast';
import type { CPQSimulatorService } from '../../services/cpqSimulatorService';
import type {
  SimulatorStatus,
  ObjectSummary,
  SimulatorError,
  StepEntry,
} from '../../services/sapSimulatorService';

export interface CPQSimulatorPanelState {
  status: SimulatorStatus | null;
  objects: ObjectSummary[];
  loadingStatus: boolean;
  loadingObjects: boolean;
  statusError: string | null;
  objectsError: string | null;
}

/** Shared state + actions for CPQ/telco FDW simulator panels (full page or embedded). */
export function useCPQSimulatorPanel(service: CPQSimulatorService | null) {
  const { toast } = useToast();

  const [state, setState] = useState<CPQSimulatorPanelState>({
    status: null,
    objects: [],
    loadingStatus: !!service,
    loadingObjects: false,
    statusError: null,
    objectsError: null,
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
    if (!service) return;
    setState((s) => ({ ...s, loadingStatus: true, statusError: null }));
    try {
      const status = await service.getStatus();
      setState((s) => ({ ...s, status, loadingStatus: false }));
      setConnectionError(null);
    } catch (err) {
      const e = err as SimulatorError;
      const msg = e.message || 'Failed to connect';
      setState((s) => ({ ...s, loadingStatus: false, statusError: msg }));
      if (e.type === 'network') setConnectionError(msg);
    }
  }, [service]);

  const fetchObjects = useCallback(async () => {
    if (!service) return;
    setState((s) => ({ ...s, loadingObjects: true, objectsError: null }));
    try {
      const res = await service.getObjects();
      setState((s) => ({ ...s, objects: res.objects, loadingObjects: false }));
    } catch (err) {
      setState((s) => ({
        ...s,
        loadingObjects: false,
        objectsError: (err as SimulatorError).message || 'Failed',
      }));
    }
  }, [service]);

  const refreshAll = useCallback(async () => {
    await fetchStatus();
    await fetchObjects();
  }, [fetchStatus, fetchObjects]);

  useEffect(() => {
    if (!service) {
      setState({
        status: null,
        objects: [],
        loadingStatus: false,
        loadingObjects: false,
        statusError: null,
        objectsError: null,
      });
      return;
    }
    refreshAll();
  }, [service, refreshAll]);

  useEffect(() => {
    return () => {
      if (loadPollRef.current) clearInterval(loadPollRef.current);
    };
  }, []);

  const pollLoadStatus = useCallback(() => {
    if (!service) return;
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
        setIsSeeding(false);
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
          setLoadRunning(false);
          setIsLoadingData(false);
          setIsSeeding(false);
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
          setLoadRunning(false);
          setIsLoadingData(false);
          setIsSeeding(false);
          toast({ title: 'Lost connection', variant: 'destructive' });
        }
      }
    };
    tick();
    loadPollRef.current = setInterval(tick, 2000);
  }, [refreshAll, service, toast]);

  const handleLoad = async () => {
    if (!service) return;
    setIsLoadingData(true);
    setLoadRunning(true);
    setLoadSteps([]);
    try {
      await service.loadData();
      pollLoadStatus();
    } catch (err) {
      setIsLoadingData(false);
      setLoadRunning(false);
      toast({
        title: 'Load Failed',
        description: (err as SimulatorError).message,
        variant: 'destructive',
      });
    }
  };

  const handleSeed = async () => {
    if (!service) return;
    setIsSeeding(true);
    setLoadRunning(true);
    setLoadSteps([]);
    try {
      await service.seedData();
      pollLoadStatus();
    } catch (err) {
      setIsSeeding(false);
      setLoadRunning(false);
      toast({
        title: 'Seed Failed',
        description: (err as SimulatorError).message,
        variant: 'destructive',
      });
    }
  };

  const handleReset = async () => {
    if (!service) return;
    setIsResetting(true);
    setLoadRunning(true);
    setLoadSteps([]);
    try {
      await service.resetData();
      pollLoadStatus();
    } catch (err) {
      setIsResetting(false);
      setLoadRunning(false);
      toast({
        title: 'Reset Failed',
        description: (err as SimulatorError).message,
        variant: 'destructive',
      });
    } finally {
      setIsResetting(false);
    }
  };

  const handleSelectObject = (schema: string, table: string) => {
    setSelectedSchema(schema);
    setSelectedTable(table);
    setBrowserOpen(true);
  };

  return {
    state,
    isLoadingData,
    isSeeding,
    isResetting,
    connectionError,
    loadSteps,
    loadRunning,
    browserOpen,
    selectedSchema,
    selectedTable,
    setBrowserOpen,
    refreshAll,
    fetchStatus,
    handleLoad,
    handleSeed,
    handleReset,
    handleSelectObject,
  };
}
