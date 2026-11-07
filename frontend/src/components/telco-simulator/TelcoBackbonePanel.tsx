import { useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, Loader2, Play, RefreshCw, Settings2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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

const DELIVERY_MODES = ['Table', 'File', 'API', 'Stream'] as const;
type DeliveryMode = (typeof DELIVERY_MODES)[number];

type CatalogRow = {
  system_key: string;
  slug: string;
  deliveries: string[];
};

type BackboneCatalog = {
  layer: string;
  vendors: Record<string, string>;
  vendor_default: string;
  systems: CatalogRow[];
};

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
  /** When set, Tables pane lists FDW objects like the legacy panel (click row for data preview). */
  simulatorService?: CPQSimulatorService;
  simulatorTitle?: string;
  simulatorSubtitle?: string;
}

/** Parent folder for generated file paths (e.g. incoming/bss/slug/file.csv → /incoming/bss/slug) */
function destinationFolderFromPath(path: string | undefined): string {
  if (!path) return '';
  const n = path.replace(/\\/g, '/').trim();
  const i = n.lastIndexOf('/');
  if (i <= 0) return '/';
  return n.slice(0, i);
}

/** Match backend: incoming/{layer}/{slug}/... */
function inferSystemKeyFromFilePath(catalog: BackboneCatalog, path: string | undefined): string | null {
  if (!path) return null;
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  if (parts[0] !== 'incoming' || parts.length < 3) return null;
  const slug = parts[2];
  const row = catalog.systems.find((r) => r.slug === slug);
  return row?.system_key ?? null;
}

function resolveProductFamily(
  catalog: BackboneCatalog,
  systemKey: string | null | undefined,
  filePath?: string | null,
): { key: string; slug?: string } | null {
  const key = (systemKey && systemKey.trim()) || inferSystemKeyFromFilePath(catalog, filePath || undefined);
  if (!key) return null;
  const slug = catalog.systems.find((r) => r.system_key === key)?.slug;
  return { key, slug };
}

function ProductFamilyLine({
  catalog,
  systemKey,
  filePath,
}: {
  catalog: BackboneCatalog;
  systemKey?: string | null;
  filePath?: string | null;
}) {
  const fam = resolveProductFamily(catalog, systemKey, filePath);
  if (!fam) {
    return (
      <div className="flex flex-wrap items-center gap-1.5 mt-1">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Product family</span>
        <span className="text-[10px] text-muted-foreground">—</span>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-1">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Product family</span>
      <Badge variant="secondary" className="text-[10px] font-normal px-1.5 py-0 max-w-[min(100%,28rem)] truncate" title={fam.key}>
        {fam.key}
      </Badge>
      {fam.slug ? (
        <code className="text-[9px] text-muted-foreground truncate max-w-[12rem]" title={fam.slug}>
          {fam.slug}
        </code>
      ) : null}
    </div>
  );
}

function deliverySetFromCatalog(d: string[]): Set<DeliveryMode> {
  const s = new Set<DeliveryMode>();
  for (const m of DELIVERY_MODES) {
    if (d.includes(m)) s.add(m);
  }
  return s;
}

function vendorBadge(catalog: BackboneCatalog, code: string | null | undefined) {
  if (!code) return null;
  const label = catalog.vendors[code];
  if (!label) return <span className="text-muted-foreground">({code})</span>;
  return (
    <span className="text-muted-foreground">
      {label} ({code})
    </span>
  );
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
  }, [fetchSummary, apiBase]);

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

  const fileDestinationNote = useMemo(() => {
    const paths = (summary?.files || []).map((f) => f.path).filter(Boolean) as string[];
    const folders = new Set(paths.map(destinationFolderFromPath).filter(Boolean));
    if (folders.size === 1) return Array.from(folders)[0];
    return null;
  }, [summary?.files]);

  const handleSelectAtlasTable = useCallback((schema: string, table: string) => {
    setBrowseSchema(schema);
    setBrowseTable(table);
    setBrowserOpen(true);
  }, []);

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

      <section aria-label="Generated data">
        <h2 className="text-sm font-semibold mb-3">Generated data</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="shadow-none flex flex-col min-h-[280px] md:col-span-2">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">Tables</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">
                Atlas schema <code className="text-[10px]">{atlasSchema}</code>
                {simulatorService && (
                  <span className="block mt-1">
                    Click a table to preview rows (same FDW list as before). Generate with Table delivery to populate.
                  </span>
                )}
              </p>
            </CardHeader>
            <CardContent className="px-2 pb-4 pt-2 flex-1 min-h-0 max-h-[min(55vh,520px)] overflow-y-auto">
              {simulatorService ? (
                <div className="[&_.rounded-md.border]:text-sm">
                  <SAPObjectsTable
                    objects={atlasObjects}
                    isLoading={loadingFdwObjects}
                    error={fdwObjectsError}
                    onSelectObject={handleSelectAtlasTable}
                    title={`Atlas tables (${atlasSchema})`}
                    emptyMessage={`No tables in ${atlasSchema} yet. Configure backbone with Table delivery and Generate.`}
                    filterPlaceholder={`Filter ${atlasSchema} tables...`}
                  />
                </div>
              ) : summary?.tables?.length ? (
                <div className="px-2 text-[11px] space-y-1">
                  {summary.tables.map((t, i) => (
                    <div key={`${t.schema}.${t.table}.${i}`} className="font-mono text-[10px] break-all">
                      {t.schema}.{t.table} <span className="text-muted-foreground">({t.rows ?? 0} rows)</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-[11px] px-2">Open Configure backbone, pick Table deliveries, then Generate.</p>
              )}
            </CardContent>
          </Card>

          <Card className="shadow-none flex flex-col min-h-[280px]">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">Files</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">
                Generated files are written under the simulator export prefix (e.g. S3{' '}
                <code className="text-[10px]">…/telco-backbone/&lt;layer&gt;/&lt;run_id&gt;/files/</code>
                ). Destination folder per file:
              </p>
              {fileDestinationNote && summary?.files && summary.files.length > 1 && (
                <p className="text-[10px] text-muted-foreground mt-1 font-mono break-all">
                  All in this run: <span className="text-foreground">{fileDestinationNote}</span>
                </p>
              )}
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-3 flex-1 overflow-y-auto max-h-[360px] text-[11px] space-y-3">
              {summary?.files?.length ? (
                summary.files.map((f, i) => {
                  const folder = destinationFolderFromPath(f.path);
                  return (
                    <div key={`${f.path}-${i}`} className="border-b border-border/60 pb-2 last:border-0 last:pb-0">
                      <ProductFamilyLine catalog={catalog} systemKey={f.system_key} filePath={f.path} />
                      <div className="font-medium mt-0.5">{f.name || f.path?.split('/').pop()}</div>
                      {f.vendor_code && (
                        <div className="text-[10px] text-muted-foreground mt-0.5">Vendor: {vendorBadge(catalog, f.vendor_code)}</div>
                      )}
                      <div className="text-[10px] text-muted-foreground font-mono mt-0.5 break-all">
                        <span className="text-muted-foreground">Destination: </span>
                        {folder || '—'}
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">Enable File delivery for a family, then Generate.</p>
              )}
            </CardContent>
          </Card>

          <Card className="shadow-none flex flex-col min-h-[280px]">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">APIs</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">
                Vendor routes under <code className="text-[10px]">{apiBase}/vendor-api/</code>
              </p>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-3 flex-1 overflow-y-auto max-h-[360px] text-[11px] space-y-2">
              {summary?.apis?.length ? (
                summary.apis.map((a, i) => {
                  const rp = (a.route_path || '').replace(/^\//, '');
                  const href = `${apiBase}/vendor-api/${rp}`;
                  return (
                    <div key={`${a.method}-${a.route_path}-${i}`} className="space-y-1">
                      <ProductFamilyLine catalog={catalog} systemKey={a.system_key} />
                      {a.vendor_code && (
                        <div className="text-muted-foreground text-[10px]">Vendor: {vendorBadge(catalog, a.vendor_code)}</div>
                      )}
                      <div>
                        <span className="text-muted-foreground">{a.method}</span>{' '}
                        <a href={href} className="text-primary break-all" target="_blank" rel="noreferrer">
                          {href}
                        </a>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">Enable API delivery for a family, then Generate.</p>
              )}
            </CardContent>
          </Card>

          <Card className="shadow-none flex flex-col min-h-[280px]">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">Streams</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">SSE replay (dev)</p>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-3 flex-1 overflow-y-auto max-h-[360px] text-[11px] space-y-2">
              {summary?.streams?.length ? (
                summary.streams.map((srow, i) => {
                  const enc = encodeURIComponent(srow.topic || '');
                  const href = `${apiBase}/backbone/stream/${enc}`;
                  return (
                    <div key={`${srow.topic}-${i}`} className="space-y-1">
                      <ProductFamilyLine catalog={catalog} systemKey={srow.system_key} />
                      {srow.vendor_code && (
                        <div className="text-[10px] text-muted-foreground">Vendor: {vendorBadge(catalog, srow.vendor_code)}</div>
                      )}
                      <div>
                        <span className="text-muted-foreground">{srow.event_count ?? 0} events</span> —{' '}
                        <code className="text-[10px] break-all">{srow.topic}</code>
                      </div>
                      <a href={href} className="text-primary text-[10px] break-all" target="_blank" rel="noreferrer">
                        {href}
                      </a>
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">Enable Stream delivery for a family, then Generate.</p>
              )}
            </CardContent>
          </Card>
        </div>
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
