import * as React from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { DetailSheet, InlineError, SearchInput, StatusPill } from '@/components/ds/kit';
import { EmptyState } from '@/components/ds/primitives';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { simName, simByService } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { errorText, num, plural } from '@/core/format';
import {
  listScenarios, previewScenario, revertScenarioRun, runScenario,
  type Scenario, type ScenarioRun, type ScenarioStep, type ScenarioStepResult, type ScenarioWrite,
} from '@/services/api';

/** "telco-customer-intelligence" → "Telco customer intelligence". */
function pretty(title: string) {
  if (/\s/.test(title) || !/[-_]/.test(title)) return title;
  const s = title.replace(/[-_]+/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const ACTION_WORD: Record<string, string> = {
  select: 'Uses existing rows',
  append: 'Adds rows',
  update: 'Changes rows',
  delete: 'Removes rows',
};

function useIsWide() {
  const query = '(min-width: 1280px)';
  const [wide, setWide] = React.useState(() => window.matchMedia(query).matches);
  React.useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setWide(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return wide;
}

function Systems({ plugins, className }: { plugins: string[]; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      {plugins.map(p => <SystemLogo key={p} system={simByService(p)?.logo || p} size="sm" />)}
    </span>
  );
}

/* ---------------------------------------------------------- run results */

const added = (w: ScenarioWrite) => w.added ?? w.count ?? 0;

function WriteLine({ w }: { w: ScenarioWrite }) {
  const n = added(w);
  const ids = w.recordIds || [];
  return (
    <li className="border-b border-border py-2 text-sm last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span className="font-mono text-xs text-foreground">{w.schema ? `${w.schema}.` : ''}{w.table}</span>
        <span className="text-xs text-muted-foreground">{w.pluginLabel || simName(w.plugin)}</span>
        <span className="num ml-auto flex gap-3 text-xs">
          {n > 0 && <span className="text-success">+{num(n)} added</span>}
          {(w.updated ?? 0) > 0 && <span className="text-warning">{num(w.updated)} changed</span>}
          {(w.deleted ?? 0) > 0 && <span className="text-destructive">−{num(w.deleted)} removed</span>}
          {w.beforeCount != null && w.afterCount != null && <span className="text-muted-foreground">{num(w.beforeCount)} → {num(w.afterCount)} rows</span>}
        </span>
      </div>
      {ids.length > 0 && (
        <div className="mt-1 break-all font-mono text-xs text-subtle-foreground">
          {ids.join(', ')}{n > ids.length ? ` and ${num(n - ids.length)} more` : ''}
        </div>
      )}
    </li>
  );
}

function StepResult({ result }: { result: ScenarioStepResult }) {
  const writes = (result.written || []).filter(w => added(w) > 0 || (w.deleted ?? 0) > 0 || (w.updated ?? 0) > 0);
  const bound = result.bound || [];
  if (!writes.length && !bound.length && !result.message) return null;
  return (
    <div className="mt-2 rounded-lg bg-surface-2/60 px-3 py-2">
      {result.message && <p className="text-xs text-muted-foreground">{result.message}</p>}
      {bound.map(b => (
        <div key={b.name} className="py-1 text-xs">
          <span className="text-muted-foreground">Picked from existing data: </span>
          <span className="font-medium text-foreground">{num(b.count)} {b.name}</span>
          {b.sample?.length > 0 && <div className="mt-0.5 break-all font-mono text-subtle-foreground">{b.sample.map(String).join(', ')}{b.count > b.sample.length ? ` and ${num(b.count - b.sample.length)} more` : ''}</div>}
        </div>
      ))}
      {writes.length > 0 && <ul>{writes.map(w => <WriteLine key={`${w.plugin}-${w.table}`} w={w} />)}</ul>}
    </div>
  );
}

/* ---------------------------------------------------------------- detail */

interface DetailProps {
  scenario: Scenario;
  steps: ScenarioStep[];
  run: ScenarioRun | null;
  busy: string | null;
  error: string | null;
  onRun: (stepId?: string) => void;
  onRevert: () => void;
}

function ScenarioBody({ scenario, steps, run, busy, error, onRun }: DetailProps) {
  const done = new Set(run?.completedSteps || []);
  const results = new Map((run?.results || []).map(r => [r.stepId, r]));
  const reverted = run?.status === 'reverted';
  const revertedRows = run?.reverted || run?.summary?.reverted || [];

  return (
    <div className="space-y-6">
      {scenario.kpis.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Moves these measures: <span className="text-foreground">{scenario.kpis.join(', ')}</span>
        </p>
      )}

      {run && (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <StatusPill status={run.status} />
            {run.summary && !reverted && (
              <span className="text-sm text-muted-foreground">
                <span className="num font-medium text-foreground">{num(run.summary.totalAdded)}</span> rows added in{' '}
                <span className="num font-medium text-foreground">{plural(run.summary.tablesTouched, 'table')}</span>
              </span>
            )}
            <span className="ml-auto truncate font-mono text-xs text-subtle-foreground" title="Run id">{run.runId}</span>
          </div>
          {reverted && revertedRows.length > 0 && (
            <>
              <p className="mt-2 text-xs text-muted-foreground">The added rows were removed. The original data is unchanged.</p>
              <ul className="mt-1">{revertedRows.map(w => <WriteLine key={`rev-${w.plugin}-${w.table}`} w={w} />)}</ul>
            </>
          )}
        </div>
      )}

      <ol className="relative">
        {steps.map((step, i) => {
          const isDone = done.has(step.id);
          const working = busy === step.id;
          const planned = Object.entries(step.planned || {}).filter(([, n]) => Number(n) > 0);
          const result = results.get(step.id);
          return (
            <li key={step.id} className="relative flex gap-4 pb-6 last:pb-0">
              {i < steps.length - 1 && <span className={cn('absolute left-[13px] top-8 h-[calc(100%-32px)] w-px', isDone ? 'bg-success/40' : 'bg-border-strong')} aria-hidden="true" />}
              <span className={cn(
                'num relative mt-0.5 flex h-[27px] w-[27px] shrink-0 items-center justify-center rounded-full border text-xs font-medium',
                isDone ? 'border-success/40 bg-success/10 text-success' : working ? 'border-brand/50 bg-brand/10 text-primary dark:text-brand-hi' : 'border-border-strong bg-card text-muted-foreground',
              )}>
                {isDone ? <Icon name="check" className="h-3 w-3" /> : working ? <span className="dot-live" /> : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-foreground">{step.title}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <SystemLogo system={simByService(step.plugin)?.logo || step.plugin} size="xs" />
                      <span>{simName(step.plugin)}</span>
                      <span aria-hidden="true">·</span>
                      <span>{ACTION_WORD[step.action] || step.action}</span>
                      <span aria-hidden="true">·</span>
                      <span className="break-all font-mono">{step.tables.join(', ')}</span>
                    </div>
                    {!isDone && planned.length > 0 && (
                      <div className="num mt-1 text-xs text-muted-foreground">
                        Will add {planned.map(([t, n]) => `${num(n)} to ${t}`).join(', ')}
                      </div>
                    )}
                  </div>
                  {isDone ? (
                    <span className="text-xs font-medium text-success">Done</span>
                  ) : (
                    <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => onRun(step.id)}>
                      <Icon name={working ? 'spinner' : 'play'} className={cn(working && 'animate-spin')} /> Run step
                    </Button>
                  )}
                </div>
                {result && <StepResult result={result} />}
              </div>
            </li>
          );
        })}
      </ol>

      {error && <InlineError>{error}</InlineError>}

      <p className="text-xs text-muted-foreground">
        Added rows are saved on the server and marked with <code className="font-mono">_scenario_id</code> and <code className="font-mono">_scenario_run_id</code>, so you can find them under Tables and remove them with Revert.
      </p>
    </div>
  );
}

function ScenarioActions({ run, busy, onRun, onRevert }: Pick<DetailProps, 'run' | 'busy' | 'onRun' | 'onRevert'>) {
  const canRevert = !!run && run.status !== 'reverted';
  return (
    <>
      <Button variant="outline" size="sm" disabled={!canRevert || busy !== null} onClick={onRevert}>
        <Icon name={busy === 'revert' ? 'spinner' : 'history'} className={cn(busy === 'revert' && 'animate-spin')} /> Revert this run
      </Button>
      <Button size="sm" disabled={busy !== null || run?.status === 'completed'} onClick={() => onRun()}>
        <Icon name={busy === 'remaining' ? 'spinner' : 'play'} className={cn(busy === 'remaining' && 'animate-spin')} />
        {run && run.status !== 'reverted' && (run.completedSteps?.length || 0) > 0 ? 'Run remaining steps' : 'Run all steps'}
      </Button>
    </>
  );
}

/* ------------------------------------------------------------------ page */

export default function ScenariosPage() {
  const { data, error, loading, reload } = useLoad(listScenarios);
  const [params, setParams] = useSearchParams();
  const [solution, setSolution] = React.useState('');
  const [q, setQ] = React.useState('');
  const wide = useIsWide();

  const [preview, setPreview] = React.useState<ScenarioStep[]>([]);
  const [run, setRun] = React.useState<ScenarioRun | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [runError, setRunError] = React.useState<string | null>(null);

  const all = data?.items || [];
  const solutions = data?.solutions || [];
  const selectedId = params.get('scenario');
  const selected = all.find(s => s.id === selectedId) || null;

  const list = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter(s => (!solution || s.solutionId === solution)
      && (!needle || `${s.title} ${s.summary || ''} ${s.solutionTitle} ${s.plugins.join(' ')} ${s.kpis.join(' ')}`.toLowerCase().includes(needle)));
  }, [all, solution, q]);

  const groups = React.useMemo(() => {
    const map = new Map<string, { title: string; items: Scenario[] }>();
    list.forEach(s => {
      if (!map.has(s.solutionId)) map.set(s.solutionId, { title: pretty(s.solutionTitle), items: [] });
      map.get(s.solutionId)!.items.push(s);
    });
    return Array.from(map.entries());
  }, [list]);

  const select = (id: string | null) => {
    setParams(prev => {
      const next = new URLSearchParams(prev);
      if (id) next.set('scenario', id); else next.delete('scenario');
      return next;
    }, { replace: true });
  };

  // On a wide screen always show one scenario beside the list.
  React.useEffect(() => {
    if (wide && !selected && list.length) select(list[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wide, selected, list]);

  // Load what each step would add whenever another scenario is opened.
  React.useEffect(() => {
    setPreview([]); setRunError(null);
    if (!selectedId) return;
    let alive = true;
    previewScenario(selectedId).then(s => { if (alive) setPreview(s); }).catch(() => { /* the plain step list is still shown */ });
    return () => { alive = false; };
  }, [selectedId]);

  const activeRun = selected && run && run.scenarioId === selected.id ? run : null;

  const doRun = async (stepId?: string) => {
    if (!selected) return;
    setBusy(stepId || 'remaining'); setRunError(null);
    try {
      const r = await runScenario(selected.id, { stepId, runId: activeRun && activeRun.status !== 'reverted' ? activeRun.runId : undefined });
      setRun(r);
      toast.success(r.status === 'completed' ? `${selected.title}: all steps done.` : `${selected.title}: step done.`);
    } catch (e) {
      setRunError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  const doRevert = async () => {
    if (!run?.runId) return;
    setBusy('revert'); setRunError(null);
    try {
      setRun(await revertScenarioRun(run.runId));
      toast.success('Run reverted. The added rows were removed.');
    } catch (e) {
      setRunError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  const steps = selected ? (preview.length ? preview : selected.steps) : [];
  const detailProps: DetailProps | null = selected ? { scenario: selected, steps, run: activeRun, busy, error: runError, onRun: doRun, onRevert: doRevert } : null;

  return (
    <div className="page">
      <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-lg font-medium tracking-tight text-foreground">Scenarios</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            A scenario adds a small, marked set of rows on top of the loaded data to recreate a business situation, such as overdue invoices or a churn risk. Run it, test your solution, then revert.
          </p>
        </div>
        <SearchInput value={q} onChange={setQ} placeholder="Search scenarios" className="sm:w-64" />
      </header>

      {error && <InlineError onRetry={reload}>Could not load the scenarios. {error}</InlineError>}

      <div className="grid gap-8 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        {/* List */}
        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap gap-1.5">
            {[{ id: '', title: 'All solutions' }, ...solutions].map(s => {
              const on = solution === s.id;
              const count = s.id ? all.filter(x => x.solutionId === s.id).length : all.length;
              return (
                <button
                  key={s.id || 'all'}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSolution(s.id)}
                  className={cn(
                    'inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    on ? 'border-foreground/25 bg-accent font-medium text-foreground' : 'border-border text-muted-foreground hover:border-border-strong hover:text-foreground',
                  )}
                >
                  {pretty(s.title)} <span className="num text-xs text-subtle-foreground">{count}</span>
                </button>
              );
            })}
          </div>

          {loading && !data && <div className="space-y-2" aria-busy="true">{Array.from({ length: 7 }).map((_, i) => <div key={i} className="shimmer h-14 rounded-lg bg-surface-2" />)}</div>}

          {groups.map(([sid, group]) => (
            <section key={sid} className="mb-6 last:mb-0">
              <h2 className="eyebrow mb-1 px-3">{group.title}</h2>
              <ul className="border-t border-border">
                {group.items.map(s => {
                  const on = selected?.id === s.id;
                  return (
                    <li key={s.id} className="border-b border-border">
                      <button
                        type="button"
                        onClick={() => select(s.id)}
                        aria-current={on ? 'true' : undefined}
                        className={cn(
                          'group relative flex w-full items-start gap-3 px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                          on ? 'bg-accent/70' : 'hover:bg-surface-2/70',
                        )}
                      >
                        {on && <span className="absolute inset-y-0 left-0 w-0.5 bg-primary" aria-hidden="true" />}
                        <div className="min-w-0 flex-1">
                          <div className={cn('text-sm font-medium', on ? 'text-foreground' : 'text-foreground group-hover:text-primary dark:group-hover:text-brand-hi')}>{s.title}</div>
                          {s.summary && <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{s.summary}</p>}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
                          <Systems plugins={s.plugins} />
                          <span className="num text-xs text-subtle-foreground">{plural(s.stepCount, 'step')}</span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}

          {!loading && data && list.length === 0 && (
            <EmptyState title="No scenario matches" description="Try another word or choose All solutions." />
          )}
        </div>

        {/* Detail beside the list on wide screens */}
        {wide && (
          <div className="min-w-0">
            {detailProps ? (
              <div className="sticky top-6 rounded-xl border border-border bg-card shadow-xs">
                <div className="border-b border-border px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-xs text-muted-foreground">{pretty(detailProps.scenario.solutionTitle)}</div>
                      <h2 className="mt-0.5 text-lg font-medium text-foreground">{detailProps.scenario.title}</h2>
                    </div>
                    <Systems plugins={detailProps.scenario.plugins} className="pt-1" />
                  </div>
                  {detailProps.scenario.summary && <p className="mt-1.5 text-sm text-muted-foreground">{detailProps.scenario.summary}</p>}
                </div>
                <div className="scroll-thin max-h-[calc(100dvh-var(--topbar-h)-260px)] min-h-[240px] overflow-y-auto px-5 py-5">
                  <ScenarioBody {...detailProps} />
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3">
                  <ScenarioActions {...detailProps} />
                </div>
              </div>
            ) : !loading && (
              <EmptyState title="Select a scenario" description="Its steps and the rows it adds appear here." />
            )}
          </div>
        )}
      </div>

      {/* Detail in a side sheet on smaller screens */}
      {!wide && detailProps && (
        <DetailSheet
          open
          onOpenChange={o => { if (!o) select(null); }}
          title={detailProps.scenario.title}
          description={detailProps.scenario.summary}
          meta={<><span className="text-xs text-muted-foreground">{pretty(detailProps.scenario.solutionTitle)}</span><Systems plugins={detailProps.scenario.plugins} /></>}
          footer={<ScenarioActions {...detailProps} />}
        >
          <ScenarioBody {...detailProps} />
        </DetailSheet>
      )}
    </div>
  );
}
