import { useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, Loader2, Play, RefreshCw, Settings2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SAPObjectsTable } from '@/components/sap-simulator/SAPObjectsTable';
import { SAPDataBrowserModal } from '@/components/sap-simulator/SAPDataBrowserModal';
import type { CPQSimulatorService } from '@/services/cpqSimulatorService';
import type { ObjectSummary } from '@/services/sapSimulatorService';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { BackboneCatalog } from './telcoBackboneTypes';
import { TelcoBackboneApisTable, TelcoBackboneFilesTable, TelcoBackboneStreamsTable } from './TelcoBackboneSummaryTables';
import {
  TelcoBackboneArtifactPreviewDialog,
  type PreviewTarget,
} from './TelcoBackboneArtifactPreviewDialog';
import { SimulatorArtifactStatusCard } from '@/components/simulator-shared/SimulatorArtifactStatusCard';
import { artifactMetaFromStatus } from '@/components/simulator-shared/simulatorArtifactMeta';
import { artifactKpiStats, KpiStatGrid } from '@/components/simulator-shared/artifactKpiStats';
import { SimulatorDeliveryTabs } from '@/components/simulator-shared/SimulatorDeliveryTabs';
import type { SimulatorStatus } from '@/services/sapSimulatorService';

const DELIVERY_MODES = ['Table', 'File', 'API', 'Stream'] as const;
type DeliveryMode = (typeof DELIVERY_MODES)[number];

type SummaryRow = {
  schema?: string;
  table?: string;
  rows?: number;
  method?: string;
  route_path?: string;
  system_key?: string;
  fixture_path?: string;
  name?: string;
  path?: string;
  topic?: string;
  event_count?: number;
  vendor_code?: string | null;
};

type BackboneSummary = {
  layer: string;
  run_id: string | null;
  generated_at: string | null;
  vendor_code: string | null;
  vendor_label: string | null;
  tables: SummaryRow[];
  apis: SummaryRow[];
  files: SummaryRow[];
  streams: SummaryRow[];
};

interface Props {
  /** e.g. '/api/v1/bss-simulator' */
  apiBase: string;
  /** When set, Table Data pane lists atlas tables (click row for data preview). */
  simulatorService?: CPQSimulatorService;
  simulatorTitle?: string;
  simulatorSubtitle?: string;
}

function deliverySetFromCatalog(d: string[]): Set<DeliveryMode> {
  const s = new Set<DeliveryMode>();
  for (const m of DELIVERY_MODES) {
    if (d.includes(m)) s.add(m);
  }
  return s;
}

export function TelcoBackbonePanel({ apiBase, simulatorService, simulatorTitle, simulatorSubtitle }: Props) {
  const [catalog, setCatalog] = useState<BackboneCatalog | null>(null);
  const [included, setIncluded] = useState<Set<string>>(new Set());
  const [systemDeliveries, setSystemDeliveries] = useState<Record<string, Set<DeliveryMode>>>({});
  /** Per product family — used when generating that family's artifacts */
  const [systemVendors, setSystemVendors] = useState<Record<string, string>>({});
  /** Fallback when adding a row — also sent as vendor_code for merge-only edge cases */
  const [defaultVendor, setDefaultVendor] = useState('');
  const [configOpen, setConfigOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastGenerate, setLastGenerate] = useState<Record<string, unknown> | null>(null);
  const [summary, setSummary] = useState<BackboneSummary | null>(null);
  const [refreshingSummary, setRefreshingSummary] = useState(false);

  const [fdwObjects, setFdwObjects] = useState<ObjectSummary[]>([]);
  const [loadingFdwObjects, setLoadingFdwObjects] = useState(false);
  const [fdwObjectsError, setFdwObjectsError] = useState<string | null>(null);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browseSchema, setBrowseSchema] = useState('');
  const [browseTable, setBrowseTable] = useState('');
  const [artifactPreview, setArtifactPreview] = useState<PreviewTarget>(null);
  const [artifactPreviewOpen, setArtifactPreviewOpen] = useState(false);
  const [backboneStatus, setBackboneStatus] = useState<SimulatorStatus | null>(null);
  const [loadingBackboneStatus, setLoadingBackboneStatus] = useState(false);
  const [backboneStatusError, setBackboneStatusError] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    const res = await fetch(`${apiBase}/backbone/catalog`);
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as BackboneCatalog;
    setCatalog(data);
    const inc = new Set<string>();
    const sd: Record<string, Set<DeliveryMode>> = {};
    const sv: Record<string, string> = {};
    const def = data.vendor_default || 'H';
    for (const row of data.systems) {
      inc.add(row.system_key);
      sd[row.system_key] = deliverySetFromCatalog(row.deliveries);
      sv[row.system_key] = def;
    }
    setIncluded(inc);
    setSystemDeliveries(sd);
    setSystemVendors(sv);
    setDefaultVendor(def);
  }, [apiBase]);

  const fetchSummary = useCallback(async () => {
    setRefreshingSummary(true);
    try {
      const res = await fetch(`${apiBase}/backbone/summary`);
      if (!res.ok) throw new Error(await res.text());
      const s = (await res.json()) as BackboneSummary;
      if (s.run_id) setSummary(s);
      else setSummary(null);
    } catch {
      setSummary(null);
    } finally {
      setRefreshingSummary(false);
    }
  }, [apiBase]);

  const fetchBackboneStatus = useCallback(async () => {
    setLoadingBackboneStatus(true);
    setBackboneStatusError(null);
    try {
      const res = await fetch(`${apiBase}/backbone/status`);
      if (!res.ok) throw new Error(await res.text());
      setBackboneStatus((await res.json()) as SimulatorStatus);
    } catch (e) {
      setBackboneStatus(null);
      setBackboneStatusError((e as Error).message || 'Failed to load status');
    } finally {
      setLoadingBackboneStatus(false);
    }
  }, [apiBase]);

  const fetchFdwObjects = useCallback(async () => {
    if (!simulatorService) return;
    setLoadingFdwObjects(true);
    setFdwObjectsError(null);
    try {
      const res = await simulatorService.getObjects();
      setFdwObjects(res.objects || []);
    } catch (e) {
      setFdwObjects([]);
      setFdwObjectsError((e as Error).message || 'Failed to load tables');
    } finally {
      setLoadingFdwObjects(false);
    }
  }, [simulatorService]);

  useEffect(() => {
    loadCatalog().catch((e) => setError(String(e)));
  }, [loadCatalog]);

  useEffect(() => {
    fetchSummary().catch(() => {});
    fetchBackboneStatus().catch(() => {});
  }, [fetchSummary, fetchBackboneStatus, apiBase]);

  useEffect(() => {
    fetchFdwObjects();
  }, [fetchFdwObjects, summary?.run_id]);

  const canGenerate = useMemo(() => {
    if (!catalog || included.size === 0) return false;
    for (const k of included) {
      const row = catalog.systems.find((r) => r.system_key === k);
      const allowed = row?.deliveries || [];
      const sel = systemDeliveries[k];
      if (!sel) continue;
      for (const m of sel) {
        if (allowed.includes(m)) return true;
      }
    }
    return false;
  }, [catalog, included, systemDeliveries]);

  const toggleInclude = (key: string) => {
    setIncluded((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else {
        n.add(key);
        setSystemVendors((sv) => ({ ...sv, [key]: sv[key] || defaultVendor }));
      }
      return n;
    });
  };

  const toggleMode = (systemKey: string, mode: DeliveryMode) => {
    setSystemDeliveries((prev) => {
      const cur = new Set(prev[systemKey] || []);
      if (cur.has(mode)) cur.delete(mode);
      else cur.add(mode);
      return { ...prev, [systemKey]: cur };
    });
  };

  const setRowVendor = (systemKey: string, code: string) => {
    setSystemVendors((prev) => ({ ...prev, [systemKey]: code }));
  };

  const applyDefaultVendorToAll = () => {
    if (!catalog) return;
    const next: Record<string, string> = {};
    for (const row of catalog.systems) {
      next[row.system_key] = defaultVendor;
    }
    setSystemVendors(next);
  };

  const generate = async () => {
    if (!catalog) return;
    setBusy(true);
    setError(null);
    try {
      const system_deliveries: Record<string, string[]> = {};
      const system_vendors: Record<string, string> = {};
      const systems: string[] = [];
      for (const k of included) {
        const modes = Array.from(systemDeliveries[k] || []).filter((m) =>
          catalog.systems.find((r) => r.system_key === k)?.deliveries.includes(m),
        );
        if (modes.length === 0) continue;
        systems.push(k);
        system_deliveries[k] = modes;
        const v = (systemVendors[k] || defaultVendor || catalog.vendor_default).trim().toUpperCase().slice(0, 1);
        if (v) system_vendors[k] = v;
      }
      const res = await fetch(`${apiBase}/backbone/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systems,
          system_deliveries,
          system_vendors,
          vendor_code: (defaultVendor || catalog.vendor_default).trim().toUpperCase().slice(0, 1),
          refresh_identity: false,
          include_legacy_tables: false,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as Record<string, unknown>;
      setLastGenerate(data);
      const bb = data.backbone as Record<string, unknown> | undefined;
      if (bb && typeof bb.summary === 'object' && bb.summary !== null) {
        setSummary(bb.summary as BackboneSummary);
      } else {
        await fetchSummary();
      }
      await fetchFdwObjects();
      await fetchBackboneStatus();
      setConfigOpen(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const vendorOptions = catalog ? Object.entries(catalog.vendors).sort((a, b) => a[1].localeCompare(b[1])) : [];

  const atlasSchema = useMemo(
    () => (catalog ? `telco_atlas_${catalog.layer.toLowerCase()}` : ''),
    [catalog],
  );

  const atlasObjects = useMemo(() => {
    if (!simulatorService || !atlasSchema) return [];
    return fdwObjects.filter((o) => o.schemaName === atlasSchema);
  }, [simulatorService, atlasSchema, fdwObjects]);

  const handleSelectAtlasTable = useCallback((schema: string, table: string) => {
    setBrowseSchema(schema);
    setBrowseTable(table);
    setBrowserOpen(true);
  }, []);

  const openArtifactPreview = useCallback((target: PreviewTarget) => {
    setArtifactPreview(target);
    setArtifactPreviewOpen(true);
  }, []);

  const artifactMeta = useMemo(() => artifactMetaFromStatus(backboneStatus), [backboneStatus]);
  const kpiStats = useMemo(() => (artifactMeta ? artifactKpiStats(artifactMeta) : []), [artifactMeta]);

  const tableTabCounts = useMemo(() => {
    const fromSummary = summary?.tables?.length ?? 0;
    const fromFdw = atlasObjects.length;
    return fromFdw > 0 ? fromFdw : fromSummary;
  }, [summary?.tables, atlasObjects.length]);

  if (!catalog) {
    return (
      <div className="p-6 text-sm text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading backbone catalog…
      </div>
    );
  }

  return (
    <div className="min-h-full bg-background px-4 py-6 space-y-6 max-w-[1400px] mx-auto">
      {(simulatorTitle || simulatorSubtitle) && (
        <div>
          {simulatorTitle && <h1 className="text-2xl font-bold tracking-tight">{simulatorTitle}</h1>}
          {simulatorSubtitle && <p className="text-sm text-muted-foreground mt-1">{simulatorSubtitle}</p>}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          Layer <code className="text-[11px]">{catalog.layer}</code>
          {summary?.vendor_label && (
            <>
              {' · '}
              Last run: {summary.vendor_label}
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setConfigOpen(true)}>
            <Settings2 className="h-4 w-4 mr-2" />
            Configure backbone
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              fetchSummary();
              fetchFdwObjects();
              fetchBackboneStatus();
            }}
            disabled={refreshingSummary || loadingFdwObjects}
          >
            {refreshingSummary || loadingFdwObjects ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Refresh results
          </Button>
          <Button type="button" size="sm" disabled={busy || !canGenerate} onClick={generate}>
            {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
            Generate
          </Button>
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SimulatorArtifactStatusCard
          meta={artifactMeta}
          isLoading={loadingBackboneStatus}
          error={backboneStatusError}
          onRefresh={() => {
            void fetchBackboneStatus();
          }}
        />
        <KpiStatGrid stats={kpiStats} />
      </div>

      <Dialog open={configOpen} onOpenChange={setConfigOpen}>
        <DialogContent className="max-w-[min(100vw-2rem,56rem)] max-h-[min(90vh,720px)] flex flex-col gap-0 p-0 sm:rounded-lg">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Backbone configuration</DialogTitle>
            <DialogDescription>
              Select product families, a vendor per family, and delivery types (Table, File, API, Stream). Atlas reference:{' '}
              <a href="/telco-atlas/" target="_blank" rel="noreferrer" className="text-primary inline-flex items-center gap-1">
                Telco AI Backbone <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            </DialogDescription>
          </DialogHeader>
          <div className="px-6 flex-1 min-h-0 overflow-y-auto space-y-4 pb-2">
            <div className="flex flex-wrap items-end gap-3 text-xs">
              <label className="flex flex-col gap-1">
                <span className="text-muted-foreground font-medium">Default vendor</span>
                <span className="text-[10px] text-muted-foreground">Used for new selections and as API fallback</span>
                <select
                  value={defaultVendor}
                  onChange={(e) => setDefaultVendor(e.target.value)}
                  className="rounded border border-border bg-background px-2 py-1.5 text-xs min-w-[200px]"
                >
                  {vendorOptions.map(([code, label]) => (
                    <option key={code} value={code}>
                      {label} ({code})
                    </option>
                  ))}
                </select>
              </label>
              <Button type="button" variant="secondary" size="sm" className="text-xs h-8" onClick={applyDefaultVendorToAll}>
                Set all families to default
              </Button>
            </div>
            <div className="overflow-x-auto rounded-md border border-border bg-background">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="p-2 font-medium w-10" />
                    <th className="p-2 font-medium min-w-[160px]">Product family</th>
                    <th className="p-2 font-medium min-w-[140px]">Vendor</th>
                    {DELIVERY_MODES.map((m) => (
                      <th key={m} className="p-2 font-medium text-center w-[64px]">
                        {m}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {catalog.systems.map((row) => {
                    const sel = included.has(row.system_key);
                    const rowModes = systemDeliveries[row.system_key] || new Set();
                    const v = systemVendors[row.system_key] || defaultVendor;
                    return (
                      <tr key={row.system_key} className="border-b border-border/80 hover:bg-muted/30">
                        <td className="p-2 align-middle">
                          <input
                            type="checkbox"
                            checked={sel}
                            onChange={() => toggleInclude(row.system_key)}
                            aria-label={`Include ${row.system_key}`}
                          />
                        </td>
                        <td className="p-2 align-middle">
                          <div className="font-medium leading-tight">{row.system_key}</div>
                          {row.slug && <div className="text-muted-foreground text-[10px] mt-0.5">{row.slug}</div>}
                        </td>
                        <td className="p-1 align-middle">
                          <select
                            value={v}
                            disabled={!sel}
                            onChange={(e) => setRowVendor(row.system_key, e.target.value)}
                            className="w-full max-w-[160px] rounded border border-border bg-background px-1 py-1 text-[10px] disabled:opacity-40"
                          >
                            {vendorOptions.map(([code, label]) => (
                              <option key={code} value={code}>
                                {label} ({code})
                              </option>
                            ))}
                          </select>
                        </td>
                        {DELIVERY_MODES.map((mode) => {
                          const allowed = row.deliveries.includes(mode);
                          const on = rowModes.has(mode);
                          return (
                            <td key={mode} className="p-1 text-center align-middle">
                              <input
                                type="checkbox"
                                disabled={!allowed || !sel}
                                checked={on && sel}
                                onChange={() => toggleMode(row.system_key, mode)}
                                title={!allowed ? 'Not available for this family in atlas/fixture' : mode}
                                className="disabled:opacity-30"
                              />
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <DialogFooter className="px-6 py-4 border-t bg-muted/20 shrink-0 gap-2 sm:justify-between">
            <p className="text-[11px] text-muted-foreground mr-auto">
              {canGenerate ? 'Ready to generate.' : 'Enable at least one family and delivery type.'}
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setConfigOpen(false)}>
                Close
              </Button>
              <Button type="button" size="sm" disabled={busy || !canGenerate} onClick={generate}>
                {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
                Generate
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <section aria-label="Generated data" className="space-y-3">
        <h2 className="text-sm font-semibold">Generated data</h2>
        <SimulatorDeliveryTabs
          counts={{
            table: tableTabCounts,
            file: summary?.files?.length ?? artifactMeta?.fileCount,
            api: summary?.apis?.length ?? artifactMeta?.apiCount,
            stream: summary?.streams?.length ?? artifactMeta?.streamCount,
          }}
          tables={
            <div className="space-y-2">
                <p className="text-[11px] text-muted-foreground px-1">
                  Atlas schema <code className="text-[10px]">{atlasSchema}</code> — click a table to preview rows.
                </p>
                <div className="max-h-[min(55vh,520px)] overflow-y-auto [&_.rounded-md.border]:text-sm">
                  {simulatorService ? (
                    <SAPObjectsTable
                      objects={atlasObjects}
                      isLoading={loadingFdwObjects}
                      error={fdwObjectsError}
                      onSelectObject={handleSelectAtlasTable}
                      title={`Table Data (${atlasSchema})`}
                      emptyMessage={`No table data in ${atlasSchema} yet. Configure backbone with Table delivery and Generate.`}
                      filterPlaceholder={`Filter table data in ${atlasSchema}...`}
                    />
                  ) : (
                    <p className="text-muted-foreground text-[11px] px-2">Table browser unavailable.</p>
                  )}
                </div>
            </div>
          }
          files={
            <TelcoBackboneFilesTable
              catalog={catalog}
              files={summary?.files ?? []}
              onPreviewFile={openArtifactPreview}
            />
          }
          apis={
            <TelcoBackboneApisTable
              catalog={catalog}
              apis={summary?.apis ?? []}
              apiBase={apiBase}
              onPreviewApi={openArtifactPreview}
            />
          }
          streams={
            <TelcoBackboneStreamsTable
              catalog={catalog}
              streams={summary?.streams ?? []}
              apiBase={apiBase}
              onPreviewStream={openArtifactPreview}
            />
          }
        />
      </section>

      {simulatorService && (
        <SAPDataBrowserModal
          isOpen={browserOpen}
          schema={browseSchema}
          table={browseTable}
          onClose={() => setBrowserOpen(false)}
          service={simulatorService}
        />
      )}

      <TelcoBackboneArtifactPreviewDialog
        open={artifactPreviewOpen}
        onOpenChange={setArtifactPreviewOpen}
        target={artifactPreview}
        apiBase={apiBase}
      />

      {lastGenerate && (
        <details className="text-xs border rounded-md p-3 bg-muted/30">
          <summary className="cursor-pointer font-medium text-sm">Last run details</summary>
          {(() => {
            const bb = (lastGenerate.backbone as Record<string, unknown> | undefined) || {};
            const runId = typeof bb.run_id === 'string' ? bb.run_id : null;
            const s3 = bb.s3 as { s3_enabled?: boolean; base_key?: string } | undefined;
            const samplePath = typeof bb.sample_vendor_api_path === 'string' ? bb.sample_vendor_api_path : null;
            const vendorUrl =
              samplePath != null && samplePath !== ''
                ? `${apiBase}/vendor-api/${samplePath.replace(/^\//, '')}`
                : null;
            return (
              <div className="mt-3 space-y-2">
                {runId && (
                  <div>
                    <span className="text-muted-foreground">run_id:</span>{' '}
                    <code className="text-[11px] break-all">{runId}</code>
                  </div>
                )}
                {s3?.s3_enabled && s3.base_key && (
                  <div>
                    <span className="text-muted-foreground">S3:</span>{' '}
                    <code className="text-[11px] break-all">{s3.base_key}</code>
                  </div>
                )}
                {!s3?.s3_enabled && (
                  <p className="text-muted-foreground text-[11px]">
                    No simulator bucket configured — artifacts may live in Redis only.
                  </p>
                )}
                <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                  {typeof bb.tables === 'number' && <span>tables: {bb.tables}</span>}
                  {typeof bb.files === 'number' && <span>files: {bb.files}</span>}
                  {typeof bb.vendor_api_paths === 'number' && <span>APIs: {bb.vendor_api_paths}</span>}
                  {typeof bb.stream_topics === 'number' && <span>streams: {bb.stream_topics}</span>}
                </div>
                {vendorUrl && samplePath && (
                  <div>
                    <span className="text-muted-foreground">Sample API: </span>
                    <a href={vendorUrl} className="text-primary text-[11px] break-all" target="_blank" rel="noreferrer">
                      {vendorUrl}
                    </a>
                  </div>
                )}
                <pre className="text-[10px] bg-muted p-2 rounded overflow-auto max-h-40 mt-2">{JSON.stringify(lastGenerate, null, 2)}</pre>
              </div>
            );
          })()}
        </details>
      )}
    </div>
  );
}
