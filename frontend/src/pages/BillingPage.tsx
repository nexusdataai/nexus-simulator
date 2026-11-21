import * as React from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Chips, InlineError, SearchInput, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { Icon } from '@/components/ds/Icon';
import { MethodTag } from '@/components/sim/BackbonePanel';
import { PreviewModal, type PreviewTarget } from '@/components/sim/PreviewModal';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { simByService } from '@/config/simulators';
import { errorText, num } from '@/core/format';
import {
  absoluteUrl,
  getBillingOverview,
  seedBillingTelco,
  sendRaw,
  systemApi,
  type BillingInputFeed,
  type BillingOverview,
} from '@/services/api';

type Layer = 'all' | 'BSS' | 'OSS' | 'NSS';
type DataView = 'feeds' | 'tables' | 'files' | 'apis' | 'streams';

const th = 'px-4 py-2.5 text-left text-xs font-medium text-muted-foreground';
const td = 'px-4 py-2.5 align-top text-sm';

function dirOf(path?: string) {
  const p = String(path || '').replace(/\\/g, '/');
  const i = p.lastIndexOf('/');
  return i <= 0 ? '/' : p.slice(0, i);
}

function BillingHelpDialog({ feeds, ontologyNote }: { feeds: BillingInputFeed[]; ontologyNote?: string }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 shrink-0 p-0" aria-label="Billing help">
          <Icon name="help" className="h-4 w-4 text-muted-foreground" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Billing input (simulator)</DialogTitle>
          <DialogDescription>
            Documentation for this page. The main view lists only live data from BSS, NSS, and OSS.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm text-muted-foreground">
          {ontologyNote && <p className="text-foreground/90">{ontologyNote}</p>}
          <p>
            Final billing tables (CMF, CDR_DATA, BILL_INVOICE, …) are built in Nexus Ontology ETL — see{' '}
            <Link to="/telco-atlas/kenan.html" className="text-primary hover:underline dark:text-brand-hi">
              billing tables reference
            </Link>
            .
          </p>
          <TableShell>
            <table className="w-full text-xs">
              <thead className="border-b border-border">
                <tr>
                  <th className={th}>Feed</th>
                  <th className={th}>Lands in (Ontology ETL)</th>
                  <th className={cn(th, 'hidden sm:table-cell')}>Format</th>
                </tr>
              </thead>
              <tbody>
                {feeds.map(f => (
                  <tr key={f.id || f.name} className="border-b border-border last:border-b-0">
                    <td className={cn(td, 'text-foreground')}>{f.name}</td>
                    <td className={td}>{f.ontology_lands_in || '—'}</td>
                    <td className={cn(td, 'hidden sm:table-cell')}>{f.format || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Billing input from BSS, OSS, and NSS (simulator-generated). */
export default function BillingPage() {
  const [data, setData] = React.useState<BillingOverview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [layer, setLayer] = React.useState<Layer>('all');
  const [view, setView] = React.useState<DataView>('feeds');
  const [q, setQ] = React.useState('');
  const [seeding, setSeeding] = React.useState(false);
  const [attempt, setAttempt] = React.useState(0);
  const [openTable, setOpenTable] = React.useState<TableListRow | null>(null);
  const [preview, setPreview] = React.useState<PreviewTarget | null>(null);

  React.useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getBillingOverview(layer === 'all' ? undefined : layer)
      .then(d => { if (alive) setData(d); })
      .catch(e => { if (alive) setError(errorText(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [layer, attempt]);

  const totals = data?.totals;
  const by = totals?.by_layer;

  const feedCount = React.useMemo(() => {
    const list = data?.input_feeds || [];
    return layer === 'all' ? list.length : list.filter(f => f.layer === layer).length;
  }, [data?.input_feeds, layer]);

  const feeds = React.useMemo(() => {
    const list = data?.input_feeds || [];
    const needle = q.trim().toLowerCase();
    return list.filter(f => {
      if (layer !== 'all' && f.layer !== layer) return false;
      if (!needle) return true;
      const blob = [
        f.name,
        f.layer,
        ...(f.delivery || []),
        ...(f.artifacts || []).map(a => a.tableName || a.name || a.route_path || a.topic),
      ].join(' ');
      return blob.toLowerCase().includes(needle);
    });
  }, [data?.input_feeds, layer, q]);

  const tableRows = React.useMemo((): TableListRow[] => (data?.tables || []).map(t => ({
    service: t.service,
    schemaName: t.schemaName ?? '',
    tableName: t.tableName ?? '',
    columnCount: t.columnCount,
    rowCount: t.rowCount,
    applications: t.applications,
    billing_target: t.billing_target,
    system_key: t.system_key,
  })), [data?.tables]);

  const match = (...parts: (string | null | undefined)[]) => {
    const needle = q.trim().toLowerCase();
    return !needle || parts.some(p => String(p || '').toLowerCase().includes(needle));
  };

  const files = (data?.files || []).filter(f => match(f.name, f.path, f.system_key, f.service));
  const apis = (data?.apis || []).filter(a => match(a.route_path, a.method, a.system_key, a.service));
  const streams = (data?.streams || []).filter(s => match(s.topic, s.system_key, s.service));

  const openSim = simByService(openTable?.service);
  const rowSource = React.useMemo(() => (openSim ? systemApi(openSim.apiPath) : undefined), [openSim]);

  const seedBilling = async () => {
    setSeeding(true);
    try {
      await seedBillingTelco();
      toast.success('Generated billing input for BSS, NSS, and OSS.');
      setAttempt(a => a + 1);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSeeding(false);
    }
  };

  const openFile = async (service: string, path: string, name: string, family?: string | null) => {
    const sim = simByService(service);
    if (!sim) return;
    const api = systemApi(sim.apiPath);
    setPreview({
      title: name,
      name,
      subtitle: path,
      family: family || null,
      load: () => api.backboneFile(path),
    });
  };

  const openApi = async (service: string, route: string, method: string, family?: string | null) => {
    const sim = simByService(service);
    if (!sim) return;
    const api = systemApi(sim.apiPath);
    const path = api.vendorApiPath(route);
    setPreview({
      title: `${method} /${route.replace(/^\//, '')}`,
      subtitle: path,
      family: family || null,
      href: await absoluteUrl(path),
      hrefLabel: `Open ${method} in a new tab`,
      load: async () => {
        const r = await sendRaw(path, method);
        if (!r.ok) throw new Error(`The API answered ${r.status} ${r.statusText}`);
        return r.text();
      },
    });
  };

  const openStream = async (service: string, topic: string, family?: string | null) => {
    const sim = simByService(service);
    if (!sim) return;
    const api = systemApi(sim.apiPath);
    const path = api.streamReplayPath(topic);
    setPreview({
      title: topic,
      subtitle: path,
      family: family || null,
      href: await absoluteUrl(path),
      hrefLabel: 'Open live replay in a new tab',
      load: async () => JSON.stringify(await api.backboneStreamEvents(topic)),
    });
  };

  const openArtifact = (a: NonNullable<BillingInputFeed['artifacts']>[number]) => {
    const svc = a.service || '';
    if (a.kind === 'table' && a.schemaName && a.tableName) {
      setOpenTable({
        service: svc,
        schemaName: a.schemaName,
        tableName: a.tableName,
        rowCount: a.rowCount,
        system_key: a.system_key,
      });
      return;
    }
    if (a.kind === 'file' && a.path) {
      const name = a.name || a.path.split('/').pop() || a.path;
      void openFile(svc, a.path, name, a.system_key);
      return;
    }
    if (a.kind === 'api' && a.route_path) {
      void openApi(svc, a.route_path, a.method || 'GET', a.system_key);
      return;
    }
    if (a.kind === 'stream' && a.topic) {
      void openStream(svc, a.topic, a.system_key);
    }
  };

  const feedArtifactTotal = feeds.reduce((n, f) => n + (f.artifact_count ?? f.artifacts?.length ?? 0), 0);
  const hasAnyData = (totals?.tables ?? 0) + (totals?.files ?? 0) + feedArtifactTotal > 0;

  return (
    <div className="page space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-medium tracking-tight text-foreground">Billing</h1>
          <BillingHelpDialog feeds={data?.input_feeds || []} ontologyNote={data?.ontology_etl_note} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setAttempt(a => a + 1)} disabled={loading}>
            <Icon name="refresh" className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
          <Button size="sm" onClick={seedBilling} disabled={seeding}>
            <Icon name={seeding ? 'spinner' : 'sparkles'} className={seeding ? 'animate-spin' : ''} />
            Generate
          </Button>
        </div>
      </div>

      {error && <InlineError onRetry={() => setAttempt(a => a + 1)}>{error}</InlineError>}

      <Toolbar className="flex-wrap gap-3">
        <Chips<Layer>
          label="Source"
          value={layer}
          onChange={l => { setLayer(l); setQ(''); }}
          options={[
            { value: 'all', label: 'All', count: totals?.input_feeds },
            { value: 'BSS', label: 'BSS', count: by?.tables?.BSS },
            { value: 'OSS', label: 'OSS', count: by?.tables?.OSS },
            { value: 'NSS', label: 'NSS', count: by?.tables?.NSS },
          ]}
        />
        <Chips<DataView>
          label="Show"
          value={view}
          onChange={v => { setView(v); setQ(''); }}
          options={[
            { value: 'feeds', label: 'Feeds', count: feedCount },
            { value: 'tables', label: 'Tables', count: totals?.tables },
            { value: 'files', label: 'Files', count: totals?.files },
            { value: 'apis', label: 'APIs', count: totals?.apis },
            { value: 'streams', label: 'Streams', count: totals?.streams },
          ]}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search" className="sm:w-56" />
        <ToolbarSpacer />
        {totals && !loading && (
          <span className="num text-xs text-muted-foreground">
            {num(totals.tables)} tables · {num(totals.rows)} rows · {num(totals.files)} files · {num(totals.apis)} APIs · {num(totals.streams)} streams
          </span>
        )}
      </Toolbar>

      {!loading && !hasAnyData && (
        <p className="px-1 text-center text-sm text-muted-foreground">No billing input data.</p>
      )}

      {view === 'feeds' && (
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={th}>Feed</th>
                <th className={cn(th, 'w-14')}>Layer</th>
                <th className={th}>Delivery</th>
                <th className={th}>Artifacts</th>
                <th className={cn(th, 'text-right w-16')}>Count</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map(feed => (
                <tr key={feed.id || feed.name} className="border-b border-border last:border-b-0">
                  <td className={cn(td, 'font-medium')}>{feed.name}</td>
                  <td className={cn(td, 'text-muted-foreground')}>{feed.layer || '—'}</td>
                  <td className={cn(td, 'text-muted-foreground')}>{(feed.delivery || []).join(', ') || '—'}</td>
                  <td className={td}>
                    {feed.artifacts?.length ? (
                      <ul className="space-y-1">
                        {feed.artifacts.map((a, i) => {
                          const label = a.tableName || a.name || a.route_path || a.topic || '—';
                          const svc = a.service ? a.service.toUpperCase() : '';
                          return (
                            <li key={`${a.kind}-${i}`}>
                              <button
                                type="button"
                                onClick={() => openArtifact(a)}
                                className="text-left text-xs hover:text-primary dark:hover:text-brand-hi"
                              >
                                <span className="text-muted-foreground">{a.kind}</span>{' '}
                                <span className="font-mono">{label}</span>
                                {svc ? <span className="text-muted-foreground"> · {svc}</span> : null}
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className={cn(td, 'num text-right')}>{num(feed.artifact_count ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !feeds.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">—</p>}
        </TableShell>
      )}

      {view === 'tables' && (
        <TableList
          rows={tableRows}
          loading={loading}
          showSystem
          onOpen={setOpenTable}
          emptyText="—"
        />
      )}

      {view === 'files' && (
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={th}>System</th>
                <th className={th}>File</th>
                <th className={th}>Family</th>
                <th className={cn(th, 'hidden md:table-cell')}>Path</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f, i) => {
                const svc = f.service || '';
                const sim = simByService(svc);
                const name = f.name || f.path?.split('/').pop() || '—';
                return (
                  <tr key={`${f.path}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/60">
                    <td className={cn(td, 'text-muted-foreground')}>{sim?.short || svc}</td>
                    <td className={td}>
                      <button
                        type="button"
                        disabled={!f.path}
                        onClick={() => f.path && openFile(svc, f.path, name, f.system_key)}
                        className="break-all text-left font-medium hover:text-primary dark:hover:text-brand-hi"
                      >
                        {name}
                      </button>
                    </td>
                    <td className={cn(td, 'text-muted-foreground')}>{f.system_key || '—'}</td>
                    <td className={cn(td, 'hidden font-mono text-xs text-muted-foreground md:table-cell')}>{dirOf(f.path)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!loading && !files.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">—</p>}
        </TableShell>
      )}

      {view === 'apis' && (
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={th}>System</th>
                <th className={cn(th, 'w-20')}>Method</th>
                <th className={th}>Route</th>
                <th className={th}>Family</th>
              </tr>
            </thead>
            <tbody>
              {apis.map((a, i) => {
                const svc = a.service || '';
                const sim = simByService(svc);
                const method = (a.method || 'GET').toUpperCase();
                const route = (a.route_path || '').replace(/^\//, '');
                return (
                  <tr key={`${method}-${route}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/60">
                    <td className={cn(td, 'text-muted-foreground')}>{sim?.short || svc}</td>
                    <td className={td}><MethodTag method={method} /></td>
                    <td className={td}>
                      <button type="button" onClick={() => openApi(svc, route, method, a.system_key)} className="font-mono text-xs hover:text-primary dark:hover:text-brand-hi">
                        /{route}
                      </button>
                    </td>
                    <td className={cn(td, 'text-muted-foreground')}>{a.system_key || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!loading && !apis.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">—</p>}
        </TableShell>
      )}

      {view === 'streams' && (
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={th}>System</th>
                <th className={th}>Topic</th>
                <th className={cn(th, 'text-right')}>Events</th>
                <th className={th}>Family</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((s, i) => (
                <tr key={`${s.topic}-${i}`} className="border-b border-border last:border-b-0 hover:bg-surface-2/60">
                  <td className={cn(td, 'text-muted-foreground')}>{simByService(s.service || '')?.short || s.service}</td>
                  <td className={td}>
                    <button type="button" disabled={!s.topic} onClick={() => s.topic && openStream(s.service || '', s.topic, s.system_key)} className="font-mono text-xs hover:text-primary dark:hover:text-brand-hi">
                      {s.topic || '—'}
                    </button>
                  </td>
                  <td className={cn(td, 'num text-right')}>{num(s.event_count ?? 0)}</td>
                  <td className={cn(td, 'text-muted-foreground')}>{s.system_key || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !streams.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">—</p>}
        </TableShell>
      )}

      <RowsSheet
        open={!!openTable}
        onOpenChange={o => { if (!o) setOpenTable(null); }}
        schema={openTable?.schemaName}
        table={openTable?.tableName}
        context={openSim?.name}
        source={rowSource}
      />

      <PreviewModal target={preview} onClose={() => setPreview(null)} />
    </div>
  );
}