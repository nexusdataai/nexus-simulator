import * as React from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { Chips, InlineError, SearchInput, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { Icon } from '@/components/ds/Icon';
import { PageHeader } from '@/components/ds/primitives';
import { MethodTag } from '@/components/sim/BackbonePanel';
import { PreviewModal, type PreviewTarget } from '@/components/sim/PreviewModal';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { simByService } from '@/config/simulators';
import { errorText, num } from '@/core/format';
import { absoluteUrl, getBillingOverview, seedBillingTelco, sendRaw, systemApi, type BillingOverview } from '@/services/api';

type Layer = 'all' | 'BSS' | 'OSS' | 'NSS';
type DataView = 'tables' | 'files' | 'apis' | 'streams';

const th = 'px-4 py-2.5 text-left text-xs font-medium text-muted-foreground';
const td = 'px-4 py-2.5 align-top text-sm';

function dirOf(path?: string) {
  const p = String(path || '').replace(/\\/g, '/');
  const i = p.lastIndexOf('/');
  return i <= 0 ? '/' : p.slice(0, i);
}

/** Billing input from BSS, OSS, and NSS: tables, files, APIs, streams (simulator-generated). */
export default function BillingPage() {
  const [data, setData] = React.useState<BillingOverview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [layer, setLayer] = React.useState<Layer>('all');
  const [view, setView] = React.useState<DataView>('tables');
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

  return (
    <div className="page space-y-5">
      <PageHeader
        title="Billing"
        description="Simulator-generated billing input: tables, files, vendor APIs, and streams from BSS, OSS, and NSS. Seed or regenerate billing families to refresh everything below."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setAttempt(a => a + 1)} disabled={loading}>
              <Icon name="refresh" className={loading ? 'animate-spin' : ''} /> Refresh
            </Button>
            <Button size="sm" onClick={seedBilling} disabled={seeding}>
              <Icon name={seeding ? 'spinner' : 'sparkles'} className={seeding ? 'animate-spin' : ''} />
              Generate billing input
            </Button>
          </div>
        }
      />

      {error && <InlineError onRetry={() => setAttempt(a => a + 1)}>{error}</InlineError>}

      <Toolbar className="flex-wrap gap-3">
        <Chips<Layer>
          label="Source system"
          value={layer}
          onChange={l => { setLayer(l); setQ(''); }}
          options={[
            { value: 'all', label: 'All layers', count: totals?.tables },
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
            { value: 'tables', label: 'Tables', count: totals?.tables },
            { value: 'files', label: 'Files', count: totals?.files },
            { value: 'apis', label: 'APIs', count: totals?.apis },
            { value: 'streams', label: 'Streams', count: totals?.streams },
          ]}
        />
        {view !== 'tables' && <SearchInput value={q} onChange={setQ} placeholder={`Search ${view}`} className="sm:w-56" />}
        <ToolbarSpacer />
        {totals && !loading && (
          <span className="num text-xs text-muted-foreground">
            {num(totals.tables)} tables · {num(totals.rows)} rows · {num(totals.files)} files · {num(totals.apis)} APIs · {num(totals.streams)} streams
          </span>
        )}
      </Toolbar>

      {!loading && totals && totals.tables === 0 && totals.files === 0 && (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          No billing data yet. Click <strong>Generate billing input</strong> to seed BSS, NSS, and OSS with billing families
          (tables, files, APIs, and streams), or configure generation on{' '}
          <Link to="/simulators/bss" className="text-primary hover:underline dark:text-brand-hi">BSS</Link>,{' '}
          <Link to="/simulators/oss" className="text-primary hover:underline dark:text-brand-hi">OSS</Link>, or{' '}
          <Link to="/simulators/nss" className="text-primary hover:underline dark:text-brand-hi">NSS</Link>.
        </p>
      )}

      {view === 'tables' && (
        <TableList
          rows={tableRows}
          loading={loading}
          showSystem
          onOpen={setOpenTable}
          emptyText="No billing tables. Generate billing input to create atlas, legacy, and Kenan billing tables."
        />
      )}

      {view === 'files' && (
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={th}>System</th>
                <th className={th}>File</th>
                <th className={th}>Product family</th>
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
          {!loading && !files.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No billing files yet.</p>}
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
                <th className={th}>Product family</th>
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
          {!loading && !apis.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No billing APIs yet.</p>}
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
                <th className={th}>Product family</th>
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
          {!loading && !streams.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No billing streams yet.</p>}
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