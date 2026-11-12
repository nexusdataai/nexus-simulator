import * as React from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { InlineError } from '@/components/ds/kit';
import { Icon, type IconName } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { confirmDialog } from '@/components/ds/confirm';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { SystemFacts, SystemHeader } from '@/components/sim/SystemHeader';
import { BackbonePanel } from '@/components/sim/BackbonePanel';
import { DEFAULT_SIM, DOMAINS, SIMULATORS, simById, type SimAction, type SimulatorDef } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { compact, errorText } from '@/core/format';
import { listSimulators, systemApi } from '@/services/api';

const LAST_KEY = 'nexus-simulator:last-system';

const ACTIONS: Record<SimAction, { label: string; icon: IconName; title: (n: string) => string; description: string; confirm: string; done: string; destructive?: boolean }> = {
  load: {
    label: 'Load data', icon: 'download',
    title: n => `Load ${n} data?`,
    description: 'This loads the saved data dump into the simulator on the server. Anyone using this system will see the reloaded data.',
    confirm: 'Load data', done: 'Data loaded.',
  },
  seed: {
    label: 'Seed data', icon: 'sparkles',
    title: n => `Seed ${n} with fresh data?`,
    description: 'This generates a new set of practice data for this system on the server.',
    confirm: 'Seed data', done: 'Fresh data seeded.',
  },
  reset: {
    label: 'Reset', icon: 'trash',
    title: n => `Reset ${n}?`,
    description: 'This clears the data this system holds in memory on the server. Load or seed it again to bring data back.',
    confirm: 'Reset system', done: 'System reset.', destructive: true,
  },
};

/* ------------------------------------------------------- standard system */

function SystemPanel({ sim }: { sim: SimulatorDef }) {
  const api = React.useMemo(() => systemApi(sim.apiPath), [sim.apiPath]);
  const status = useLoad(api.status, [api]);
  const objects = useLoad(api.objects, [api]);
  const [busy, setBusy] = React.useState<SimAction | null>(null);
  const [openTable, setOpenTable] = React.useState<TableListRow | null>(null);

  const refresh = () => { status.reload(); objects.reload(); };

  const act = async (kind: SimAction) => {
    const a = ACTIONS[kind];
    const ok = await confirmDialog({ title: a.title(sim.name), description: a.description, confirmLabel: a.confirm, destructive: a.destructive });
    if (!ok) return;
    setBusy(kind);
    try {
      const r = await api[kind]();
      toast.success(typeof r?.message === 'string' ? r.message : `${sim.name}: ${a.done}`);
      refresh();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <SystemHeader
        sim={sim}
        status={status.data}
        loading={status.loading}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={refresh} disabled={status.loading || objects.loading}>
              <Icon name="refresh" className={cn((status.loading || objects.loading) && 'animate-spin')} /> Refresh
            </Button>
            {sim.actions.map(kind => {
              const a = ACTIONS[kind];
              const working = busy === kind;
              return (
                <Button
                  key={kind}
                  size="sm"
                  variant={kind === 'reset' ? 'outline' : 'default'}
                  disabled={busy !== null}
                  onClick={() => act(kind)}
                  className={cn(kind === 'reset' && 'text-destructive hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive')}
                >
                  <Icon name={working ? 'spinner' : a.icon} className={cn(working && 'animate-spin')} /> {a.label}
                </Button>
              );
            })}
          </>
        }
      />

      {status.error && <InlineError onRetry={status.reload}>Could not load the status. {status.error}</InlineError>}
      <SystemFacts status={status.data} />

      <section aria-label="Tables" className="space-y-3">
        <h2 className="text-md font-medium text-foreground">Tables</h2>
        {objects.error && <InlineError onRetry={objects.reload}>Could not load the tables. {objects.error}</InlineError>}
        <TableList rows={objects.data || []} loading={objects.loading} onOpen={setOpenTable} emptyText="This system has no tables yet. Load or seed data to fill it." />
      </section>

      <RowsSheet
        open={!!openTable}
        onOpenChange={o => { if (!o) setOpenTable(null); }}
        schema={openTable?.schemaName}
        table={openTable?.tableName}
        context={sim.name}
        source={api}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ page */

export default function SystemsPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const sim = simById(id);
  const catalog = useLoad(listSimulators);
  const rowsOf = React.useMemo(() => new Map((catalog.data || []).map(s => [String(s.service), s.total_rows])), [catalog.data]);

  React.useEffect(() => { if (sim) try { sessionStorage.setItem(LAST_KEY, sim.id); } catch { /* private mode */ } }, [sim]);

  if (!sim) {
    let last: string | null = null;
    try { last = sessionStorage.getItem(LAST_KEY); } catch { /* private mode */ }
    return <Navigate to={`/simulators/${simById(last)?.id || DEFAULT_SIM}`} replace />;
  }

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      {/* System switcher: a rail on desktop, a scrolling strip on phones */}
      <nav aria-label="Systems" className="shrink-0 border-b border-border bg-background lg:sticky lg:top-0 lg:h-[calc(100dvh-var(--topbar-h))] lg:w-60 lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <div className="scrollbar-hide flex gap-1 overflow-x-auto px-3 py-2 lg:block lg:space-y-5 lg:overflow-visible lg:px-3 lg:py-5">
          {DOMAINS.map(domain => (
            <div key={domain.id} className="flex shrink-0 items-center gap-1 lg:block">
              <div className="eyebrow hidden px-2 pb-1.5 lg:block">{domain.title}</div>
              <div className="flex gap-1 lg:block lg:space-y-px">
                {SIMULATORS.filter(s => s.domain === domain.id).map(s => {
                  const on = s.id === sim.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => nav(`/simulators/${s.id}`)}
                      aria-current={on ? 'page' : undefined}
                      className={cn(
                        'flex h-9 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:w-full lg:px-2',
                        on ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
                      )}
                    >
                      <SystemLogo system={s.logo} size="sm" />
                      <span className="min-w-0 flex-1 truncate text-left">{s.name}</span>
                      <span className="num hidden text-xs text-subtle-foreground lg:block">{compact(rowsOf.get(s.service))}</span>
                    </button>
                  );
                })}
              </div>
              <span className="mx-2 h-5 w-px shrink-0 bg-border last:hidden lg:hidden" aria-hidden="true" />
            </div>
          ))}
        </div>
      </nav>

      <div className="min-w-0 flex-1">
        <div className="page">
          {sim.backbone ? <BackbonePanel key={sim.id} sim={sim} /> : <SystemPanel key={sim.id} sim={sim} />}
        </div>
      </div>
    </div>
  );
}
