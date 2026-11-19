import * as React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { InlineError, MetricStrip, StatusPill, TableShell } from '@/components/ds/kit';
import { AnimatedNumber } from '@/components/ds/AnimatedNumber';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { confirmDialog } from '@/components/ds/confirm';
import { DOMAINS, SIMULATORS, type DomainId, type SimulatorDef } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { ago, dateTime, errorText, num } from '@/core/format';
import { listSimulators, seedAllTelco, type SimStatus } from '@/services/api';

type Ecosystem = 'all' | DomainId;

function statusOf(s?: SimStatus): { word: string; label: string } {
  if (!s) return { word: 'unknown', label: 'No answer' };
  if (!s.enabled) return { word: 'disabled', label: 'Switched off' };
  if (!s.loaded) return { word: 'pending', label: 'Not loaded' };
  return { word: 'healthy', label: 'Loaded' };
}

const shade = (i: number) => `hsl(var(--brand) / ${Math.max(0.22, 1 - i * 0.1)})`;

function VolumeBar({ items, onOpen }: { items: { sim: SimulatorDef; rows: number }[]; onOpen: (id: string) => void }) {
  const total = items.reduce((a, b) => a + b.rows, 0) || 1;
  const sorted = [...items].sort((a, b) => b.rows - a.rows);
  const [hot, setHot] = React.useState<string | null>(null);
  if (!sorted.some(x => x.rows > 0)) return null;
  return (
    <div>
      <div className="grow-x flex h-9 w-full gap-0.5 overflow-hidden rounded-md" role="img" aria-label="Share of rows per system">
        {sorted.map(({ sim, rows }, i) => {
          const pct = (rows / total) * 100;
          return (
            <Tooltip key={sim.id}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => onOpen(sim.id)}
                  onMouseEnter={() => setHot(sim.id)}
                  onMouseLeave={() => setHot(null)}
                  aria-label={`${sim.name}: ${num(rows)} rows`}
                  style={{ width: `${Math.max(pct, 1.2)}%`, backgroundColor: shade(i), opacity: hot && hot !== sim.id ? 0.45 : 1 }}
                  className="h-full min-w-[5px] transition-opacity duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                />
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                {sim.short} · <span className="num">{num(rows)}</span> rows
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}

const ECOSYSTEM_TABS: { id: Ecosystem; label: string }[] = [
  { id: 'all', label: 'All ecosystems' },
  { id: 'supply-chain', label: 'Supply chain' },
  { id: 'telecom', label: 'Telecom' },
];

function domainTitle(id: Ecosystem): string {
  if (id === 'all') return 'All practice systems';
  return DOMAINS.find(d => d.id === id)?.title ?? id;
}

export default function OverviewPage() {
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const ecosystem: Ecosystem = (searchParams.get('ecosystem') as Ecosystem) || 'all';
  const setEcosystem = (v: Ecosystem) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (v === 'all') next.delete('ecosystem');
      else next.set('ecosystem', v);
      return next;
    }, { replace: true });
  };

  const { data, error, loading, reload } = useLoad(listSimulators);
  const [seeding, setSeeding] = React.useState(false);

  const byService = React.useMemo(() => new Map((data || []).map(s => [String(s.service), s])), [data]);
  const known = SIMULATORS.map(sim => ({ sim, s: byService.get(sim.service) }));

  const scoped = React.useMemo(
    () => (ecosystem === 'all' ? known : known.filter(k => k.sim.domain === ecosystem)),
    [known, ecosystem],
  );

  const totals = React.useMemo(() => {
    const list = scoped.map(k => k.s).filter(Boolean) as SimStatus[];
    return {
      systems: scoped.length,
      loaded: list.filter(s => s.enabled && s.loaded).length,
      tables: list.reduce((a, s) => a + (s.table_count || 0), 0),
      tablesWithData: list.reduce((a, s) => a + (s.tables_with_data || 0), 0),
      rows: list.reduce((a, s) => a + (s.total_rows || 0), 0),
      files: list.reduce((a, s) => a + (s.file_count || 0), 0),
      apis: list.reduce((a, s) => a + (s.api_count || 0), 0),
      streams: list.reduce((a, s) => a + (s.stream_count || 0), 0),
    };
  }, [scoped]);

  const open = (id: string) => nav(`/simulators/${id}`);

  const seedTelco = async () => {
    const ok = await confirmDialog({
      title: 'Seed all telecom systems?',
      description: 'Regenerates BSS, NSS and OSS practice data (tables, files, APIs, streams).',
      confirmLabel: 'Seed telecom',
    });
    if (!ok) return;
    setSeeding(true);
    try {
      const r = await seedAllTelco();
      toast.success(r?.message || 'Telecom systems seeded.');
      reload();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSeeding(false);
    }
  };

  const domainMeta = ecosystem !== 'all' ? DOMAINS.find(d => d.id === ecosystem) : null;

  return (
    <div className="page space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <p className="eyebrow text-subtle-foreground">Enterprise simulator</p>
          <h1 className="text-xl font-medium tracking-tight text-foreground sm:text-2xl">
            Practice data ecosystem
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {domainMeta?.description ?? 'Supply chain and telecom replicas for connectors, journeys and solutions—without touching production.'}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {ecosystem === 'telecom' && (
            <Button variant="outline" size="sm" onClick={seedTelco} disabled={seeding}>
              <Icon name={seeding ? 'spinner' : 'sparkles'} className={cn(seeding && 'animate-spin')} /> Seed telecom
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            <Icon name="refresh" className={cn(loading && 'animate-spin')} /> Refresh
          </Button>
        </div>
      </header>

      <div
        className="flex flex-wrap gap-1 rounded-lg border border-border bg-surface-2 p-1"
        role="tablist"
        aria-label="Ecosystem"
      >
        {ECOSYSTEM_TABS.map(tab => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={ecosystem === tab.id}
            onClick={() => setEcosystem(tab.id)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              ecosystem === tab.id
                ? 'bg-card text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <InlineError onRetry={reload}>Could not load the systems. {error}</InlineError>}

      {data && (
        <MetricStrip
          columns={6}
          items={[
            { label: 'Systems loaded', value: <><AnimatedNumber value={totals.loaded} className="num" /> / {totals.systems}</> },
            { label: 'Tables', value: <><span className="num">{num(totals.tablesWithData)}</span><span className="text-subtle-foreground"> / {num(totals.tables)}</span></> },
            { label: 'Rows', value: <AnimatedNumber value={totals.rows} className="num" /> },
            { label: 'Files', value: <AnimatedNumber value={totals.files} className="num" /> },
            { label: 'APIs', value: <AnimatedNumber value={totals.apis} className="num" /> },
            { label: 'Streams', value: <AnimatedNumber value={totals.streams} className="num" /> },
          ]}
        />
      )}

      {data && totals.rows > 0 && (
        <VolumeBar
          items={scoped.filter(k => k.s).map(k => ({ sim: k.sim, rows: k.s!.total_rows || 0 }))}
          onOpen={open}
        />
      )}

      <section aria-labelledby="ecosystem-systems" className="space-y-2">
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="ecosystem-systems" className="text-sm font-medium text-foreground">
            {domainTitle(ecosystem)}
          </h2>
          <span className="text-xs text-muted-foreground">Open a row for tables, files, APIs and streams</span>
        </div>
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                {ecosystem === 'all' && <th className="px-3 py-2 text-left font-medium">Ecosystem</th>}
                <th className="px-3 py-2 text-left font-medium">System</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Tables</th>
                <th className="px-3 py-2 text-right font-medium">Rows</th>
                <th className="px-3 py-2 text-right font-medium">Files</th>
                <th className="px-3 py-2 text-right font-medium">APIs</th>
                <th className="px-3 py-2 text-right font-medium">Streams</th>
                <th className="hidden px-3 py-2 text-right font-medium md:table-cell">Updated</th>
                <th className="w-6" aria-hidden="true" />
              </tr>
            </thead>
            <tbody>
              {scoped.map(({ sim, s }) => {
                const st = statusOf(s);
                const domainLabel = DOMAINS.find(d => d.id === sim.domain)?.title ?? sim.domain;
                return (
                  <tr
                    key={sim.id}
                    tabIndex={0}
                    role="link"
                    aria-label={`Open ${sim.name}`}
                    onClick={() => open(sim.id)}
                    onKeyDown={e => { if (e.key === 'Enter') open(sim.id); }}
                    className="group cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-surface-2/60 focus-visible:bg-surface-2/60 focus-visible:outline-none"
                  >
                    {ecosystem === 'all' && (
                      <td className="whitespace-nowrap px-3 py-2.5 text-xs text-muted-foreground">{domainLabel}</td>
                    )}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <SystemLogo system={sim.logo} size="sm" />
                        <div className="min-w-0">
                          <div className="font-medium text-foreground group-hover:text-primary dark:group-hover:text-brand-hi">{sim.name}</div>
                          <div className="hidden max-w-xs truncate text-xs text-muted-foreground lg:block">{sim.description}</div>
                        </div>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      {loading && !data ? <span className="text-subtle-foreground">…</span> : <StatusPill status={st.word}>{st.label}</StatusPill>}
                    </td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-right text-xs">
                      {s ? <>{num(s.tables_with_data)}<span className="text-subtle-foreground">/{num(s.table_count)}</span></> : '—'}
                    </td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-right">{num(s?.total_rows)}</td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-right text-foreground">{num(s?.file_count)}</td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-right text-foreground">{num(s?.api_count)}</td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-right text-foreground">{num(s?.stream_count)}</td>
                    <td className="hidden whitespace-nowrap px-3 py-2.5 text-right text-xs text-muted-foreground md:table-cell" title={dateTime(s?.dump_timestamp || s?.backbone_generated_at)}>
                      {ago(s?.backbone_generated_at || s?.dump_timestamp)}
                    </td>
                    <td className="pr-2 text-subtle-foreground">
                      <Icon name="chevron-right" className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableShell>
      </section>
    </div>
  );
}