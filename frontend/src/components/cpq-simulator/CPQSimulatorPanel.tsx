import { Button } from '../ui/button';
import { RefreshCw, Download, Trash2, Loader2, AlertCircle, Sparkles } from 'lucide-react';

import { SAPObjectsTable } from '../sap-simulator/SAPObjectsTable';
import { SimulatorArtifactStatusCard } from '@/components/simulator-shared/SimulatorArtifactStatusCard';
import { artifactMetaFromStatus } from '@/components/simulator-shared/simulatorArtifactMeta';
import { artifactKpiStats, KpiStatGrid } from '@/components/simulator-shared/artifactKpiStats';
import { ArtifactModalityEmpty, SimulatorDeliveryTabs } from '@/components/simulator-shared/SimulatorDeliveryTabs';
import { SAPDataBrowserModal } from '../sap-simulator/SAPDataBrowserModal';
import { SAPActivityLog } from '../sap-simulator/SAPActivityLog';

import type { CPQSimulatorService } from '../../services/cpqSimulatorService';
import { useCPQSimulatorPanel } from './useCPQSimulatorPanel';

interface Props {
  service: CPQSimulatorService;
  title: string;
  subtitle: string;
}

// Generic CPQ simulator admin panel. Reuses the SAP simulator's
// status card / objects table / data browser modal / activity log
// because the response shapes are identical across simulators.
export function CPQSimulatorPanel({ service, title, subtitle }: Props) {
  const {
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
  } = useCPQSimulatorPanel(service);

  const artifactMeta = artifactMetaFromStatus(state.status);
  const stats = artifactMeta ? artifactKpiStats(artifactMeta) : [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refreshAll} disabled={state.loadingStatus}>
            <RefreshCw className={`h-4 w-4 mr-2 ${state.loadingStatus ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleSeed} disabled={isSeeding || isLoadingData || state.loadingStatus}>
            {isSeeding ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
            Seed
          </Button>
          <Button size="sm" onClick={handleLoad} disabled={isLoadingData || isSeeding || state.loadingStatus}>
            {isLoadingData ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            Load Data
          </Button>
          <Button variant="destructive" size="sm" onClick={handleReset} disabled={isResetting || state.loadingStatus}>
            {isResetting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Trash2 className="h-4 w-4 mr-2" />}
            Reset
          </Button>
        </div>
      </div>

      {connectionError && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-destructive/50 bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p>{connectionError}</p>
        </div>
      )}

      {(loadRunning || loadSteps.length > 0) && (
        <SAPActivityLog title={loadRunning ? 'Loading…' : 'Load Complete'} steps={loadSteps} running={loadRunning} />
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
          <SAPObjectsTable
            objects={state.objects}
            isLoading={state.loadingObjects}
            error={state.objectsError}
            onSelectObject={handleSelectObject}
          />
        }
        files={<ArtifactModalityEmpty modality="File" hint="CPQ simulators seed table data; file exports use telecom backbone." />}
        apis={<ArtifactModalityEmpty modality="API" />}
        streams={<ArtifactModalityEmpty modality="Stream" />}
      />
      <SAPDataBrowserModal
        isOpen={browserOpen}
        schema={selectedSchema}
        table={selectedTable}
        onClose={() => setBrowserOpen(false)}
        service={service}
      />
    </div>
  );
}
