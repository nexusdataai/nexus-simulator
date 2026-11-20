/**
 * Telecom layers (BSS / NSS / OSS): data is generated from the Telco AI
 * Backbone atlas as tables, files, APIs and streams.
 */
import * as React from 'react';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { Chips, CodeBlock, InlineError, SearchInput, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { ModalOverlay, ModalPanel } from '@/components/ds/Modal';
import { Icon } from '@/components/ds/Icon';
import { confirmDialog } from '@/components/ds/confirm';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { PreviewModal, type PreviewTarget } from '@/components/sim/PreviewModal';
import { SystemHeader, SystemFacts } from '@/components/sim/SystemHeader';
import type { SimulatorDef } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { dateTime, errorText, num } from '@/core/format';
import { absoluteUrl, sendRaw, systemApi, type BackboneCatalog, type BackboneSummary } from '@/services/api';

const DELIVERIES = ['Table', 'File', 'API', 'Stream'] as const;
type Delivery = typeof DELIVERIES[number];
type View = 'generated' | 'all' | 'files' | 'apis' | 'streams';

const selectCls =
  'h-8 rounded-md border border-border-strong bg-card px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40';
const checkCls = 'h-4 w-4 rounded border-border-strong accent-[hsl(var(--primary))] disabled:opacity-30';
const th = 'px-4 py-2.5 text-left text-xs font-medium text-muted-foreground';
const td = 'px-4 py-2.5 align-top';

function dirOf(path?: string) {
  const p = String(path || '').replace(/\\/g, '/');
  const i = p.lastIndexOf('/');
  return i <= 0 ? '/' : p.slice(0, i);
}

/** Family of a file when the backend did not set it: incoming/<x>/<slug>/… */
function familyOf(catalog: BackboneCatalog | null, key?: string | null, path?: string) {
  if (key) return key;
  const parts = String(path || '').replace(/\\/g, '/').split('/').filter(Boolean);
  if (parts[0] !== 'incoming' || parts.length < 3) return null;
  return catalog?.systems.find(s => s.slug === parts[2])?.system_key || null;
}

/* ------------------------------------------------------ configure dialog */

interface ConfigState {
  included: Set<string>;
  deliveries: Record<string, Set<Delivery>>;
  vendors: Record<string, string>;
  defaultVendor: string;
}

function initialConfig(catalog: BackboneCatalog): ConfigState {
  const def = catalog.vendor_default || Object.keys(catalog.vendors)[0] || 'H';
  const deliveries: Record<string, Set<Delivery>> = {};
  const vendors: Record<string, string> = {};
  catalog.systems.forEach(s => {
    deliveries[s.system_key] = new Set(DELIVERIES.filter(d => s.deliveries.includes(d)));
    vendors[s.system_key] = def;
  });
  return { included: new Set(catalog.systems.map(s => s.system_key)), deliveries, vendors, defaultVendor: def };
}

function buildRequest(catalog: BackboneCatalog, cfg: ConfigState) {
  const systems: string[] = [];
  const system_deliveries: Record<string, string[]> = {};
  const system_vendors: Record<string, string> = {};
  catalog.systems.forEach(s => {
    if (!cfg.included.has(s.system_key)) return;
    const picked = Array.from(cfg.deliveries[s.system_key] || []).filter(d => s.deliveries.includes(d));
    if (!picked.length) return;
    systems.push(s.system_key);
    system_deliveries[s.system_key] = picked;
    system_vendors[s.system_key] = (cfg.vendors[s.system_key] || cfg.defaultVendor).toUpperCase().slice(0, 1);
  });
  return {
    systems, system_deliveries, system_vendors,
    vendor_code: cfg.defaultVendor.toUpperCase().slice(0, 1),
    refresh_identity: false,
    include_legacy_tables: false,
  };
}

function ConfigureDialog({ catalog, cfg, setCfg, onClose, onGenerate, generating }: {
  catalog: BackboneCatalog; cfg: ConfigState; setCfg: React.Dispatch<React.SetStateAction<ConfigState>>;
  onClose: () => void; onGenerate: () => void; generating: boolean;
}) {
  const vendors = Object.entries(catalog.vendors).sort((a, b) => a[1].localeCompare(b[1]));
  const ready = buildRequest(catalog, cfg).systems.length > 0;

  const toggleFamily = (key: string) => setCfg(c => {
    const included = new Set(c.included);
    if (included.has(key)) included.delete(key); else included.add(key);
    return { ...c, included };
  });
  const toggleDelivery = (key: string, d: Delivery) => setCfg(c => {
    const set = new Set(c.deliveries[key] || []);
    if (set.has(d)) set.delete(d); else set.add(d);
    return { ...c, deliveries: { ...c.deliveries, [key]: set } };
  });

  return (
    <ModalOverlay onClose={onClose}>
      <ModalPanel label="Backbone configuration" className="max-w-4xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-lg font-medium text-foreground">Backbone configuration</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose the product families to generate, the vendor each one imitates and how the data is delivered.{' '}
              <a href="/telco-atlas/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline dark:text-brand-hi">
                Telco AI Backbone reference <Icon name="external-link" className="h-3 w-3" />
              </a>
            </p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close"><Icon name="close" /></Button>
        </header>

        <div className="flex flex-wrap items-end gap-3 border-b border-border bg-surface-2/40 px-5 py-3">
          <label className="text-xs font-medium text-muted-foreground">
            <span className="mb-1.5 block">Default vendor</span>
            <select value={cfg.defaultVendor} onChange={e => setCfg(c => ({ ...c, defaultVendor: e.target.value }))} className={cn(selectCls, 'min-w-[200px]')}>
              {vendors.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}
            </select>
          </label>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCfg(c => ({ ...c, vendors: Object.fromEntries(catalog.systems.map(s => [s.system_key, c.defaultVendor])) }))}
          >
            Use this vendor for every family
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCfg(c => {
              const billing = new Set(catalog.systems.filter(s => s.billing).map(s => s.system_key));
              return { ...c, included: billing.size ? billing : c.included };
            })}
          >
            Billing families only
          </Button>
        </div>

        <div className="scroll-thin min-h-0 flex-1 overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 border-b border-border bg-popover">
              <tr>
                <th className={cn(th, 'w-10')}><span className="sr-only">Include</span></th>
                <th className={th}>Product family</th>
                <th className={th}>Vendor</th>
                {DELIVERIES.map(d => <th key={d} className={cn(th, 'w-16 text-center')}>{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {catalog.systems.map(s => {
                const on = cfg.included.has(s.system_key);
                return (
                  <tr key={s.system_key} className={cn('border-b border-border last:border-b-0', !on && 'text-muted-foreground')}>
                    <td className="px-4 py-2.5">
                      <input type="checkbox" className={checkCls} checked={on} onChange={() => toggleFamily(s.system_key)} aria-label={`Include ${s.system_key}`} />
                    </td>
                    <td className="px-4 py-2.5">
                      <div className={cn('font-medium', on && 'text-foreground')}>{s.system_key}</div>
                      {s.slug && <div className="font-mono text-xs text-subtle-foreground">{s.slug}</div>}
                      {s.billing && (
                        <div className="mt-1 text-xs text-muted-foreground" title={s.billing_target}>
                          <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-primary">Billing</span>
                          {s.billing_target && <span className="ml-1.5">{s.billing_target}</span>}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <select
                        value={cfg.vendors[s.system_key] || cfg.defaultVendor}
                        disabled={!on}
                        onChange={e => setCfg(c => ({ ...c, vendors: { ...c.vendors, [s.system_key]: e.target.value } }))}
                        aria-label={`Vendor for ${s.system_key}`}
                        className={cn(selectCls, 'w-full max-w-[180px]')}
                      >
                        {vendors.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}
                      </select>
                    </td>
                    {DELIVERIES.map(d => {
                      const available = s.deliveries.includes(d);
                      return (
                        <td key={d} className="px-4 py-2.5 text-center">
                          {available ? (
                            <input
                              type="checkbox"
                              className={checkCls}
                              disabled={!on}
                              checked={on && !!cfg.deliveries[s.system_key]?.has(d)}
                              onChange={() => toggleDelivery(s.system_key, d)}
                              aria-label={`${d} for ${s.system_key}`}
                            />
                          ) : (
                            <span className="text-subtle-foreground" title="Not available for this family">–</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="text-xs text-muted-foreground">{ready ? 'Ready to generate.' : 'Select at least one family and one delivery type.'}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
            <Button size="sm" disabled={!ready || generating} onClick={onGenerate}>
              <Icon name={generating ? 'spinner' : 'play'} className={cn(generating && 'animate-spin')} /> Generate
            </Button>
          </div>
        </footer>
      </ModalPanel>
    </ModalOverlay>
  );
}

/* ------------------------------------------------------------------ panel */

export function BackbonePanel({ sim, billingOnly }: { sim: SimulatorDef; billingOnly?: boolean }) {
  const api = React.useMemo(() => systemApi(sim.apiPath), [sim.apiPath]);
  const catalog = useLoad(api.backboneCatalog, [api]);
  const status = useLoad(api.backboneStatus, [api]);
  const summary = useLoad<BackboneSummary>(() => api.backboneSummary().catch(() => ({})), [api]);
  const objects = useLoad(api.objects, [api]);

  const [cfg, setCfg] = React.useState<ConfigState | null>(null);
  const [configOpen, setConfigOpen] = React.useState(false);
  const [generating, setGenerating] = React.useState(false);
  const [lastRun, setLastRun] = React.useState<any>(null);
  const [view, setView] = React.useState<View>(billingOnly ? 'all' : 'generated');
  const [module, setModule] = React.useState<'all' | 'billing'>(billingOnly ? 'billing' : 'all');
  const [q, setQ] = React.useState('');
  const [openTable, setOpenTable] = React.useState<TableListRow | null>(null);
  const [preview, setPreview] = React.useState<PreviewTarget | null>(null);

  React.useEffect(() => {
    if (!catalog.data) return;
    if (!cfg) {
      const base = initialConfig(catalog.data);
      if (billingOnly) {
        const billing = new Set(catalog.data.systems.filter(s => s.billing).map(s => s.system_key));
        setCfg({ ...base, included: billing.size ? billing : base.included });
      } else setCfg(base);
    }
  }, [catalog.data, cfg, billingOnly]);

  const cat = catalog.data;
  const billingFamilies = React.useMemo(
    () => new Set((cat?.systems || []).filter(s => s.billing).map(s => s.system_key)),
    [cat],
  );
  const isBillingFamily = (key?: string | null) => !billingOnly || (key ? billingFamilies.has(key) : false);
  const sum = summary.data?.run_id ? summary.data : null;
  const atlasSchema = cat ? `telco_atlas_${cat.layer.toLowerCase()}` : '';
  const allTables = objects.data || [];
  const billingRows = (list: TableListRow[]) =>
    module === 'billing' ? list.filter(t => t.applications?.includes('billing')) : list;
  const atlasTables = billingRows(allTables.filter(t => t.schemaName === atlasSchema));
  const kenanTables = billingRows(allTables.filter(t => t.schemaName === 'kenan_bp'));
  const files = React.useMemo(
    () => (sum?.files || []).filter(f => isBillingFamily(f.system_key)),
    [sum?.files, billingOnly, billingFamilies],
  );
  const apis = React.useMemo(
    () => (sum?.apis || []).filter(a => isBillingFamily(a.system_key)),
    [sum?.apis, billingOnly, billingFamilies],
  );
  const streams = React.useMemo(
    () => (sum?.streams || []).filter(s => isBillingFamily(s.system_key)),
    [sum?.streams, billingOnly, billingFamilies],
  );
  const vendorName = (code?: string | null) => (code ? `${cat?.vendors[code] || code} (${code})` : '—');

  const refresh = () => { status.reload(); summary.reload(); objects.reload(); };

  const generate = async (ask: boolean) => {
    if (!cat || !cfg) return;
    const body = buildRequest(cat, cfg);
    if (!body.systems.length) { setConfigOpen(true); return; }
    if (ask) {
      const ok = await confirmDialog({
        title: `Generate ${sim.name} data?`,
        description: `This replaces the generated ${sim.name} tables, files, APIs and streams on the server for ${body.systems.length} product ${body.systems.length === 1 ? 'family' : 'families'}.`,
        confirmLabel: 'Generate',
      });
      if (!ok) return;
    }
    setGenerating(true);
    try {
      const result = await api.backboneGenerate(body);
      setLastRun(result);
      setConfigOpen(false);
      toast.success(`${sim.name} data generated.`);
      refresh();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setGenerating(false);
    }
  };

  const match = (...parts: (string | null | undefined)[]) => {
    const needle = q.trim().toLowerCase();
    return !needle || parts.some(p => String(p || '').toLowerCase().includes(needle));
  };

  const openApi = async (route: string, method: string, family: string | null) => {
    const path = api.vendorApiPath(route);
    setPreview({
      title: `${method} /${route.replace(/^\//, '')}`,
      subtitle: path,
      family,
      href: await absoluteUrl(path),
      hrefLabel: `Open ${method} in a new tab`,
      load: async () => {
        const r = await sendRaw(path, method);
        if (!r.ok) throw new Error(`The API answered ${r.status} ${r.statusText}`);
        return r.text;
      },
    });
  };
  const openStream = async (topic: string, family: string | null) => {
    const path = api.streamReplayPath(topic);
    setPreview({
      title: topic,
      subtitle: `Replay: ${path}`,
      family,
      href: await absoluteUrl(path),
      hrefLabel: 'Open live replay in a new tab',
      load: async () => JSON.stringify(await api.backboneStreamEvents(topic)),
    });
  };

  const run = lastRun?.backbone || null;

  return (
    <div className="space-y-6">
      <SystemHeader
        sim={sim}
        status={status.data}
        loading={status.loading}
        note={cat ? (
          <>
            Layer <span className="font-mono text-xs">{cat.layer}</span>
            {status.data?.vendor_label && <> · last generated as {status.data.vendor_label}</>}
            {status.data?.backbone_generated_at && <> on {dateTime(status.data.backbone_generated_at)}</>}
          </>
        ) : undefined}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={refresh} disabled={status.loading || objects.loading}>
              <Icon name="refresh" className={cn((status.loading || objects.loading) && 'animate-spin')} /> Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={() => setConfigOpen(true)} disabled={!cat}>
              <Icon name="sliders" /> Configure backbone
            </Button>
            <Button size="sm" onClick={() => generate(true)} disabled={!cat || generating}>
              <Icon name={generating ? 'spinner' : 'play'} className={cn(generating && 'animate-spin')} /> Generate
            </Button>
          </>
        }
      />

      {catalog.error && <InlineError onRetry={catalog.reload}>Could not load the backbone catalog. {catalog.error}</InlineError>}
      {status.error && <InlineError onRetry={status.reload}>Could not load the status. {status.error}</InlineError>}

      <SystemFacts status={status.data} extra={status.data?.backbone_run_id ? [{ label: 'Generation run', value: status.data.backbone_run_id, mono: true }] : []} />

      <section aria-label="Generated data" className="space-y-3">
        <Toolbar>
          <Chips<View>
            label="Generated data"
            value={view}
            onChange={v => { setView(v); setQ(''); }}
            options={[
              { value: 'generated', label: 'Generated tables', count: atlasTables.length },
              { value: 'all', label: 'All tables', count: allTables.length },
              { value: 'files', label: 'Files', count: files.length },
              { value: 'apis', label: 'APIs', count: apis.length },
              { value: 'streams', label: 'Streams', count: streams.length },
            ]}
          />
          <ToolbarSpacer />
          {!billingOnly && (view === 'generated' || view === 'all') && allTables.some(t => t.applications?.includes('billing')) && (
            <Chips<'all' | 'billing'>
              label="Application"
              value={module}
              onChange={setModule}
              options={[
                { value: 'all', label: 'All tables', count: allTables.length },
                { value: 'billing', label: 'Billing', count: allTables.filter(t => t.applications?.includes('billing')).length },
              ]}
            />
          )}
          {(view === 'files' || view === 'apis' || view === 'streams') && (
            <SearchInput value={q} onChange={setQ} placeholder={`Search ${view}`} />
          )}
        </Toolbar>

        {objects.error && (view === 'generated' || view === 'all') && <InlineError onRetry={objects.reload}>{objects.error}</InlineError>}

        {(view === 'generated' || view === 'all') && (
          <TableList
            key={view}
            rows={view === 'generated' ? [...atlasTables, ...kenanTables] : billingRows(allTables)}
            loading={objects.loading}
            onOpen={setOpenTable}
            emptyText={view === 'generated' ? `Nothing generated in ${atlasSchema || 'the atlas schema'} yet. Configure the backbone with Table delivery, then Generate.` : 'This system has no tables yet.'}
          />
        )}

        {view === 'files' && (
          <TableShell>
            <table className="w-full text-sm">
              <thead className="border-b border-border"><tr><th className={th}>File</th><th className={th}>Product family</th><th className={cn(th, 'hidden md:table-cell')}>Destination</th><th className={th}>Vendor</th></tr></thead>
              <tbody>
                {files.filter(f => match(f.name, f.path, f.system_key)).map((f, i) => {
                  const name = f.name || f.path?.split('/').pop() || '—';
                  const family = familyOf(cat, f.system_key, f.path);
                  return (
                    <tr key={`${f.path}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/70">
                      <td className={td}>
                        <button
                          type="button"
                          disabled={!f.path}
                          onClick={() => f.path && setPreview({ title: name, subtitle: f.path, family, name, load: () => api.backboneFile(f.path!) })}
                          className="break-all text-left font-medium text-foreground hover:text-primary dark:hover:text-brand-hi"
                        >
                          {name}
                        </button>
                      </td>
                      <td className={cn(td, 'text-muted-foreground')}>{family || '—'}</td>
                      <td className={cn(td, 'hidden break-all font-mono text-xs text-muted-foreground md:table-cell')}>{dirOf(f.path)}</td>
                      <td className={cn(td, 'whitespace-nowrap text-muted-foreground')}>{vendorName(f.vendor_code)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!files.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No files yet. Turn on File delivery for a family, then Generate.</p>}
          </TableShell>
        )}

        {view === 'apis' && (
          <TableShell>
            <table className="w-full text-sm">
              <thead className="border-b border-border"><tr><th className={cn(th, 'w-20')}>Method</th><th className={th}>Route</th><th className={th}>Product family</th><th className={th}>Vendor</th></tr></thead>
              <tbody>
                {apis.filter(a => match(a.route_path, a.method, a.system_key)).map((a, i) => {
                  const method = (a.method || 'GET').toUpperCase();
                  const route = (a.route_path || '').replace(/^\//, '');
                  return (
                    <tr key={`${method}-${route}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/70">
                      <td className={td}><MethodTag method={method} /></td>
                      <td className={td}>
                        <button type="button" onClick={() => openApi(route, method, a.system_key || null)} className="break-all text-left font-mono text-xs text-foreground hover:text-primary dark:hover:text-brand-hi">
                          /{route}
                        </button>
                      </td>
                      <td className={cn(td, 'text-muted-foreground')}>{a.system_key || '—'}</td>
                      <td className={cn(td, 'whitespace-nowrap text-muted-foreground')}>{vendorName(a.vendor_code)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!apis.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No APIs yet. Turn on API delivery for a family, then Generate.</p>}
          </TableShell>
        )}

        {view === 'streams' && (
          <TableShell>
            <table className="w-full text-sm">
              <thead className="border-b border-border"><tr><th className={th}>Topic</th><th className={cn(th, 'text-right')}>Events</th><th className={th}>Product family</th><th className={th}>Vendor</th></tr></thead>
              <tbody>
                {streams.filter(s => match(s.topic, s.system_key)).map((s, i) => (
                  <tr key={`${s.topic}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/70">
                    <td className={td}>
                      <button type="button" disabled={!s.topic} onClick={() => s.topic && openStream(s.topic, s.system_key || null)} className="break-all text-left font-mono text-xs text-foreground hover:text-primary dark:hover:text-brand-hi">
                        {s.topic || '—'}
                      </button>
                    </td>
                    <td className={cn(td, 'num text-right')}>{num(s.event_count ?? 0)}</td>
                    <td className={cn(td, 'text-muted-foreground')}>{s.system_key || '—'}</td>
                    <td className={cn(td, 'whitespace-nowrap text-muted-foreground')}>{vendorName(s.vendor_code)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!streams.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No streams yet. Turn on Stream delivery for a family, then Generate.</p>}
          </TableShell>
        )}
      </section>

      {lastRun && (
        <section aria-label="Last generation" className="space-y-2">
          <h2 className="text-md font-medium text-foreground">Last generation</h2>
          <p className="text-sm text-muted-foreground">
            {typeof run?.tables === 'number' && <>{num(run.tables)} tables · </>}
            {typeof run?.files === 'number' && <>{num(run.files)} files · </>}
            {typeof run?.vendor_api_paths === 'number' && <>{num(run.vendor_api_paths)} APIs · </>}
            {typeof run?.stream_topics === 'number' && <>{num(run.stream_topics)} streams</>}
            {run?.run_id && <> · run <span className="font-mono text-xs">{run.run_id}</span></>}
          </p>
          <CodeBlock maxHeight={220}>{JSON.stringify(lastRun, null, 2)}</CodeBlock>
        </section>
      )}

      <RowsSheet
        open={!!openTable}
        onOpenChange={o => { if (!o) setOpenTable(null); }}
        schema={openTable?.schemaName}
        table={openTable?.tableName}
        context={sim.name}
        source={api}
      />
      <PreviewModal target={preview} onClose={() => setPreview(null)} />
      {configOpen && cat && cfg && (
        <ConfigureDialog catalog={cat} cfg={cfg} setCfg={setCfg as any} onClose={() => setConfigOpen(false)} onGenerate={() => generate(false)} generating={generating} />
      )}
    </div>
  );
}

/** HTTP method written as a small mono word; colour only for writes. */
export function MethodTag({ method }: { method: string }) {
  const m = method.toUpperCase();
  return (
    <span className={cn(
      'font-mono text-xs font-medium',
      m === 'GET' && 'text-primary dark:text-brand-hi',
      m === 'POST' && 'text-success',
      (m === 'PATCH' || m === 'PUT') && 'text-warning',
      m === 'DELETE' && 'text-destructive',
    )}>{m}</span>
  );
}
