import { useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, Loader2, Play, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

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

export function TelcoBackbonePanel({ apiBase, simulatorTitle, simulatorSubtitle }: Props) {
  const [catalog, setCatalog] = useState<BackboneCatalog | null>(null);
  const [included, setIncluded] = useState<Set<string>>(new Set());
  const [systemDeliveries, setSystemDeliveries] = useState<Record<string, Set<DeliveryMode>>>({});
  const [vendorCode, setVendorCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastGenerate, setLastGenerate] = useState<Record<string, unknown> | null>(null);
  const [summary, setSummary] = useState<BackboneSummary | null>(null);
  const [refreshingSummary, setRefreshingSummary] = useState(false);

  const loadCatalog = useCallback(async () => {
    const res = await fetch(`${apiBase}/backbone/catalog`);
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as BackboneCatalog;
    setCatalog(data);
    const inc = new Set<string>();
    const sd: Record<string, Set<DeliveryMode>> = {};
    for (const row of data.systems) {
      inc.add(row.system_key);
      sd[row.system_key] = deliverySetFromCatalog(row.deliveries);
    }
    setIncluded(inc);
    setSystemDeliveries(sd);
    setVendorCode(data.vendor_default || 'H');
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

  useEffect(() => {
    loadCatalog().catch((e) => setError(String(e)));
  }, [loadCatalog]);

  useEffect(() => {
    fetchSummary().catch(() => {});
  }, [fetchSummary, apiBase]);

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
      else n.add(key);
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

  const generate = async () => {
    if (!catalog) return;
    setBusy(true);
    setError(null);
    try {
      const system_deliveries: Record<string, string[]> = {};
      const systems: string[] = [];
      for (const k of included) {
        const modes = Array.from(systemDeliveries[k] || []).filter((m) =>
          catalog.systems.find((r) => r.system_key === k)?.deliveries.includes(m),
        );
        if (modes.length === 0) continue;
        systems.push(k);
        system_deliveries[k] = modes;
      }
      const res = await fetch(`${apiBase}/backbone/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systems,
          system_deliveries,
          vendor_code: vendorCode || catalog.vendor_default,
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
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const vendorOptions = catalog ? Object.entries(catalog.vendors).sort((a, b) => a[1].localeCompare(b[1])) : [];

  const atlasSchema = catalog ? `telco_atlas_${catalog.layer.toLowerCase()}` : '';

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

      <section className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Backbone configuration</h2>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
              Choose product families and delivery types (Table, File, API, Stream), then generate. Atlas reference:{' '}
              <a href="/telco-atlas/" target="_blank" rel="noreferrer" className="text-primary inline-flex items-center gap-1">
                Telco AI Backbone <ExternalLink className="h-3 w-3" />
              </a>
            </p>
          </div>
          <div className="flex flex-wrap gap-2 items-center shrink-0">
            <button
              type="button"
              onClick={() => fetchSummary()}
              disabled={refreshingSummary}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
            >
              {refreshingSummary ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh results
            </button>
            <button
              type="button"
              disabled={busy || !canGenerate}
              onClick={generate}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Generate
            </button>
          </div>
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex items-center gap-2">
            <span className="text-muted-foreground font-medium">Vendor</span>
            <select
              value={vendorCode}
              onChange={(e) => setVendorCode(e.target.value)}
              className="rounded border border-border bg-background px-2 py-1 text-xs min-w-[180px]"
            >
              {vendorOptions.map(([code, label]) => (
                <option key={code} value={code}>
                  {label} ({code})
                </option>
              ))}
            </select>
          </label>
          <span className="text-muted-foreground">
            Layer: <code className="text-[11px]">{catalog.layer}</code>
          </span>
        </div>

        <div className="overflow-x-auto rounded-md border border-border bg-background">
          <table className="w-full text-left text-[11px]">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="p-2 font-medium w-10" />
                <th className="p-2 font-medium min-w-[200px]">Product family</th>
                {DELIVERY_MODES.map((m) => (
                  <th key={m} className="p-2 font-medium text-center w-[72px]">
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {catalog.systems.map((row) => {
                const sel = included.has(row.system_key);
                const rowModes = systemDeliveries[row.system_key] || new Set();
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
      </section>

      <section aria-label="Generated data">
        <h2 className="text-sm font-semibold mb-3">Generated data</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="shadow-none flex flex-col min-h-[280px]">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">Tables</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">
                Atlas schema <code className="text-[10px]">{atlasSchema}</code>
              </p>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-3 flex-1 overflow-y-auto max-h-[360px] text-[11px] space-y-1">
              {summary?.tables?.length ? (
                summary.tables.map((t, i) => (
                  <div key={`${t.schema}.${t.table}.${i}`} className="font-mono text-[10px] break-all">
                    {t.schema}.{t.table} <span className="text-muted-foreground">({t.rows ?? 0} rows)</span>
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground">Run Generate to create table data for your selection.</p>
              )}
            </CardContent>
          </Card>

          <Card className="shadow-none flex flex-col min-h-[280px]">
            <CardHeader className="py-3 px-4 pb-0">
              <CardTitle className="text-sm">Files</CardTitle>
              <p className="text-[11px] text-muted-foreground font-normal mt-1">Exports from the last run</p>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-3 flex-1 overflow-y-auto max-h-[360px] text-[11px] space-y-2">
              {summary?.files?.length ? (
                summary.files.map((f, i) => {
                  const p = encodeURIComponent(f.path || '');
                  const href = `${apiBase}/backbone/file?path=${p}`;
                  return (
                    <div key={`${f.path}-${i}`}>
                      <div className="font-medium">{f.name || f.path}</div>
                      <a href={href} className="text-primary break-all text-[10px]" target="_blank" rel="noreferrer">
                        {href}
                      </a>
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">Run Generate with File delivery to see files here.</p>
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
                    <div key={`${a.method}-${a.route_path}-${i}`}>
                      <span className="text-muted-foreground">{a.method}</span>{' '}
                      <a href={href} className="text-primary break-all" target="_blank" rel="noreferrer">
                        {href}
                      </a>
                      {a.system_key && <div className="text-muted-foreground text-[10px]">{a.system_key}</div>}
                    </div>
                  );
                })
              ) : (
                <p className="text-muted-foreground">Run Generate with API delivery to see endpoints here.</p>
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
                    <div key={`${srow.topic}-${i}`}>
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
                <p className="text-muted-foreground">Run Generate with Stream delivery to see topics here.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </section>

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
