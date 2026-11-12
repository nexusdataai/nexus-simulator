import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { InlineError, StatusPill, TableShell } from '@/components/ds/kit';
import { SectionHeader } from '@/components/ds/primitives';
import { AnimatedNumber } from '@/components/ds/AnimatedNumber';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { confirmDialog } from '@/components/ds/confirm';
import { DOMAINS, SIMULATORS, type SimulatorDef } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { ago, compact, dateTime, errorText, num } from '@/core/format';
import { listSimulators, seedAllTelco, type SimStatus } from '@/services/api';

function statusOf(s?: SimStatus): { word: string; label: string } {
  if (!s) return { word: 'unknown', label: 'No answer' };
  if (!s.enabled) return { word: 'disabled', label: 'Switched off' };
  if (!s.loaded) return { word: 'pending', label: 'Not loaded' };
  return { word: 'healthy', label: 'Loaded' };
}

/* --------------------------------------------------------- volume drawing */

/** One hue, lighter for each smaller system. */
const shade = (i: number) => `hsl(var(--brand) / ${Math.max(0.22, 1 - i * 0.1)})`;

/** One bar showing how the rows are shared between the systems. */
function VolumeBar({ items, onOpen }: { items: { sim: SimulatorDef; rows: number }[]; onOpen: (id: string) => void }) {
  const total = items.reduce((a, b) => a + b.rows, 0) || 1;
  const sorted = [...items].sort((a, b) => b.rows - a.rows);
  const [hot, setHot] = React.useState<string | null>(null);
  return (
    <div>
      <div className="grow-x flex h-11 w-full gap-[3px] overflow-hidden rounded-lg" role="img" aria-label="Share of rows per system">
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
                  onFocus={() => setHot(sim.id)}
                  onBlur={() => setHot(null)}
                  aria-label={`${sim.name}: ${num(rows)} rows`}
                  style={{ width: `${Math.max(pct, 1.2)}%`, backgroundColor: shade(i), opacity: hot && hot !== sim.id ? 0.4 : 1 }}
                  className="h-full min-w-[6px] transition-opacity duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-foreground"
                />
              </TooltipTrigger>
              <TooltipContent side="top">
                <span className="font-medium">{sim.name}</span> · <span className="num">{num(rows)}</span> rows · <span className="num">{pct.toFixed(pct < 1 ? 1 : 0)}%</span>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
        {sorted.map(({ sim, rows }, i) => (
          <li key={sim.id}>
            <button
              type="button"
              onClick={() => onOpen(sim.id)}
              onMouseEnter={() => setHot(sim.id)}
              onMouseLeave={() => setHot(null)}
              className={cn('flex items-center gap-2 rounded text-sm transition-opacity duration-200', hot && hot !== sim.id && 'opacity-50')}
            >
              <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: shade(i) }} aria-hidden="true" />
              <span className="text-muted-foreground">{sim.short}</span>
              <span className="num text-foreground">{compact(rows)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ page */

export default function OverviewPage() {
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(listSimulators);
  const [seeding, setSeeding] = React.useState(false);

  const byService = React.useMemo(() => new Map((data || []).map(s => [String(s.service), s])), [data]);
  const known = SIMULATORS.map(sim => ({ sim, s: byService.get(sim.service) }));

  const totals = React.useMemo(() => {
    const list = data || [];
    return {
      systems: list.length,
      loaded: list.filter(s => s.enabled && s.loaded).length,
      tables: list.reduce((a, s) => a + (s.table_count || 0), 0),
      rows: list.reduce((a, s) => a + (s.total_rows || 0), 0),
      extras: list.reduce((a, s) => a + (s.file_count || 0) + (s.api_count || 0) + (s.stream_count || 0), 0),
    };
  }, [data]);

  const open = (id: string) => nav(`/simulators/${id}`);

  const seedTelco = async () => {
    const ok = await confirmDialog({
      title: 'Seed all telecom systems?',
      description: 'This regenerates the BSS, NSS and OSS practice data on the server. Anything using that data will see the new rows.',
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

  return (
    <div className="page space-y-8">
      {/* Headline: written as a sentence, numbers inline */}
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-sm font-medium text-muted-foreground">Enterprise simulator</h1>
          <p className="mt-2 max-w-3xl text-2xl font-medium leading-9 tracking-tight text-foreground sm:text-3xl sm:leading-[2.6rem]">
            <AnimatedNumber value={data ? totals.loaded : null} className="num" /> of {data ? totals.systems : '—'} systems are loaded, holding{' '}
            <AnimatedNumber value={data ? totals.tables : null} className="num text-primary dark:text-brand-hi" /> tables and{' '}
            <AnimatedNumber value={data ? totals.rows : null} className="num text-primary dark:text-brand-hi" /> rows of practice data.
          </p>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Replicas of the enterprise systems Nexus AI connects to. Use them to test connectors, journeys and solutions without touching a real system.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={reload} disabled={loading} className="shrink-0">
          <Icon name="refresh" className={cn(loading && 'animate-spin')} /> Refresh
        </Button>
      </header>

      {error && <InlineError onRetry={reload}>Could not load the systems. {error}</InlineError>}

      {data && totals.rows > 0 && (
        <section aria-label="Where the rows are">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="text-md font-medium text-foreground">Where the rows are</h2>
            <span className="text-xs text-muted-foreground">Select a system to open it</span>
          </div>
          <VolumeBar items={known.filter(k => k.s).map(k => ({ sim: k.sim, rows: k.s!.total_rows || 0 }))} onOpen={open} />
        </section>
      )}

      {DOMAINS.map(domain => {
        const rows = known.filter(k => k.sim.domain === domain.id);
        return (
          <section key={domain.id} aria-labelledby={`domain-${domain.id}`} className="space-y-3">
            <SectionHeader
              title={domain.title}
              description={domain.description}
              actions={domain.id === 'telecom' ? (
                <Button variant="outline" size="sm" onClick={seedTelco} disabled={seeding}>
                  <Icon name={seeding ? 'spinner' : 'sparkles'} className={cn(seeding && 'animate-spin')} /> Seed all telecom
                </Button>
              ) : undefined}
            />
            <TableShell>
              <table className="w-full text-sm">
                <thead className="border-b border-border text-xs text-muted-foreground">
                  <tr>
                    <th id={`domain-${domain.id}`} className="px-4 py-2.5 text-left font-medium">System</th>
                    <th className="px-4 py-2.5 text-left font-medium">Status</th>
                    <th className="px-4 py-2.5 text-right font-medium">Tables with data</th>
                    <th className="px-4 py-2.5 text-right font-medium">Rows</th>
                    <th className="hidden px-4 py-2.5 text-right font-medium lg:table-cell">Files · APIs · Streams</th>
                    <th className="hidden px-4 py-2.5 text-right font-medium md:table-cell">Data from</th>
                    <th className="w-8" aria-hidden="true" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ sim, s }) => {
                    const st = statusOf(s);
                    return (
                      <tr
                        key={sim.id}
                        tabIndex={0}
                        role="link"
                        aria-label={`Open ${sim.name}`}
                        onClick={() => open(sim.id)}
                        onKeyDown={e => { if (e.key === 'Enter') open(sim.id); }}
                        className="group cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-surface-2/70 focus-visible:bg-surface-2/70 focus-visible:outline-none"
                      >
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-3">
                            <SystemLogo system={sim.logo} size="md" />
                            <div className="min-w-0">
                              <div className="font-medium text-foreground group-hover:text-primary dark:group-hover:text-brand-hi">{sim.name}</div>
                              <div className="hidden max-w-md truncate text-xs text-muted-foreground sm:block">{sim.description}</div>
                            </div>
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3.5">
                          {loading && !data ? <span className="text-subtle-foreground">…</span> : <StatusPill status={st.word}>{st.label}</StatusPill>}
                        </td>
                        <td className="num whitespace-nowrap px-4 py-3.5 text-right">
                          {s ? <>{num(s.tables_with_data)} <span className="text-subtle-foreground">/ {num(s.table_count)}</span></> : '—'}
                        </td>
                        <td className="num px-4 py-3.5 text-right text-foreground">{num(s?.total_rows)}</td>
                        <td className="num hidden whitespace-nowrap px-4 py-3.5 text-right text-muted-foreground lg:table-cell">
                          {s ? `${num(s.file_count)} · ${num(s.api_count)} · ${num(s.stream_count)}` : '—'}
                        </td>
                        <td className="hidden whitespace-nowrap px-4 py-3.5 text-right text-muted-foreground md:table-cell" title={dateTime(s?.dump_timestamp)}>
                          {ago(s?.dump_timestamp)}
                        </td>
                        <td className="pr-3 text-subtle-foreground"><Icon name="chevron-right" className="transition-transform group-hover:translate-x-0.5" /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableShell>
          </section>
        );
      })}
    </div>
  );
}
