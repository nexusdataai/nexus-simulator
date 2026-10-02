import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Play, RotateCcw, X } from "lucide-react";

type Solution = { id: string; title: string };

type ScenarioStep = {
  id: string;
  title: string;
  plugin: string;
  tables: string[];
  action: string;
  index: number;
};

type Scenario = {
  id: string;
  solutionId: string;
  solutionTitle: string;
  title: string;
  summary: string;
  kpis: string[];
  plugins: string[];
  stepCount: number;
  steps: ScenarioStep[];
};

type PreviewStep = {
  id: string;
  title: string;
  plugin: string;
  tables: string[];
  action: string;
  planned: Record<string, number>;
  sampleBindings?: Record<string, unknown>;
  message?: string;
};

type TableWrite = {
  plugin: string;
  pluginLabel?: string;
  schema?: string;
  table: string;
  action?: string;
  added?: number;
  updated?: number;
  deleted?: number;
  beforeCount?: number;
  afterCount?: number;
  recordIds?: string[];
  count?: number;
};

type BoundItem = { name: string; count: number; sample: unknown[] };

type RunResult = {
  stepId: string;
  stepTitle?: string;
  action?: string;
  plugin?: string;
  pluginLabel?: string;
  tables?: string[];
  ok: boolean;
  message?: string;
  planned?: Record<string, number>;
  bound?: BoundItem[];
  written?: TableWrite[];
};

type RunSummary = {
  totalAdded: number;
  totalDeleted: number;
  tablesTouched: number;
  tables: TableWrite[];
  reverted?: TableWrite[];
};

type ScenarioRun = {
  runId: string;
  scenarioId: string;
  status: string;
  completedSteps: string[];
  results: RunResult[];
  summary?: RunSummary;
  reverted?: TableWrite[];
  createdAt?: string;
};

const PLUGIN_LABELS: Record<string, string> = {
  sfdc: "Salesforce",
  oracle: "Oracle ERP",
  sap: "SAP S/4HANA",
  external: "External sources",
  tpm: "TPM CPQ",
  sourcing: "Sourcing CPQ",
};

async function readJson(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return data;
}

function addedCount(w: TableWrite) {
  return w.added ?? w.count ?? 0;
}

function ChangeBadge({ kind, n }: { kind: "added" | "updated" | "deleted" | "bound"; n: number }) {
  if (!n) return null;
  const styles = {
    added: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    updated: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    deleted: "bg-red-500/15 text-red-700 dark:text-red-300",
    bound: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  };
  const labels = { added: "added", updated: "updated", deleted: "deleted", bound: "bound" };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${styles[kind]}`}>
      {n} {labels[kind]}
    </span>
  );
}

function TableChangeRow({ w }: { w: TableWrite }) {
  const label = w.pluginLabel || PLUGIN_LABELS[w.plugin] || w.plugin;
  const added = addedCount(w);
  return (
    <div className="rounded border bg-muted/30 p-2 text-xs space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground font-mono">{w.schema}.{w.table}</span>
        {w.action && <Badge variant="outline" className="text-[10px]">{w.action}</Badge>}
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        {w.beforeCount != null && w.afterCount != null && (
          <span className="text-muted-foreground">
            rows {w.beforeCount.toLocaleString()} → {w.afterCount.toLocaleString()}
          </span>
        )}
        <ChangeBadge kind="added" n={added} />
        <ChangeBadge kind="updated" n={w.updated ?? 0} />
        <ChangeBadge kind="deleted" n={w.deleted ?? 0} />
      </div>
      {(w.recordIds?.length ?? 0) > 0 && (
        <div className="font-mono text-[10px] text-muted-foreground break-all">
          IDs: {w.recordIds!.join(", ")}
          {(added > (w.recordIds?.length ?? 0)) && ` … +${added - (w.recordIds?.length ?? 0)} more`}
        </div>
      )}
    </div>
  );
}

function StepResult({ result }: { result: RunResult }) {
  const hasWrites = (result.written || []).some((w) => addedCount(w) > 0 || (w.deleted ?? 0) > 0);
  const hasBound = (result.bound || []).length > 0;
  if (!hasWrites && !hasBound && !result.message) return null;

  return (
    <div className="mt-2 space-y-2 rounded-md border border-dashed p-2 bg-background/60">
      {result.message && <div className="text-xs text-muted-foreground">{result.message}</div>}
      {hasBound && (
        <div className="space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Bound from dump</div>
          {(result.bound || []).map((b) => (
            <div key={b.name} className="text-xs">
              <span className="font-medium">{b.name}</span>
              <ChangeBadge kind="bound" n={b.count} />
              {b.sample.length > 0 && (
                <div className="font-mono text-[10px] text-muted-foreground mt-0.5 break-all">
                  {b.sample.map(String).join(", ")}
                  {b.count > b.sample.length && ` … +${b.count - b.sample.length} more`}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {hasWrites && (
        <div className="space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Database changes</div>
          {(result.written || []).map((w) => (
            <TableChangeRow key={`${w.plugin}-${w.table}`} w={w} />
          ))}
        </div>
      )}
    </div>
  );
}

function RunSummaryPanel({ run }: { run: ScenarioRun }) {
  const summary = run.summary;
  const isReverted = run.status === "reverted";
  const revertRows = run.reverted || summary?.reverted || [];

  if (!summary && !run.results.length && !revertRows.length) return null;

  return (
    <div className="rounded-lg border p-3 space-y-3 bg-muted/20">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-sm font-semibold">Run summary</div>
        <Badge variant={isReverted ? "secondary" : run.status === "completed" ? "default" : "outline"}>
          {run.status}
        </Badge>
      </div>
      {summary && !isReverted && (
        <div className="flex flex-wrap gap-3 text-xs">
          <span><strong>{summary.totalAdded}</strong> rows added</span>
          <span><strong>{summary.tablesTouched}</strong> table{summary.tablesTouched === 1 ? "" : "s"} touched</span>
          <span className="font-mono text-muted-foreground truncate max-w-full">{run.runId}</span>
        </div>
      )}
      {summary && summary.tables.length > 0 && !isReverted && (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">All changes this run</div>
          {summary.tables.map((w) => (
            <TableChangeRow key={`${w.plugin}-${w.table}`} w={w} />
          ))}
        </div>
      )}
      {isReverted && revertRows.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">Overlay rows removed (dump unchanged):</div>
          {revertRows.map((w) => (
            <TableChangeRow key={`rev-${w.plugin}-${w.table}`} w={{ ...w, action: "revert" }} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SimulatorScenariosPage() {
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [items, setItems] = useState<Scenario[]>([]);
  const [solution, setSolution] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Scenario | null>(null);
  const [preview, setPreview] = useState<PreviewStep[]>([]);
  const [run, setRun] = useState<ScenarioRun | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = solution ? `?solution=${encodeURIComponent(solution)}` : "";
      const data = await readJson(await fetch(`/api/v1/scenarios${qs}`));
      setSolutions(data.solutions || []);
      setItems(data.items || []);
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setLoading(false);
    }
  }, [solution]);

  useEffect(() => {
    load();
  }, [load]);

  const lastRunForSelected = useMemo(() => {
    if (!selected || !run || run.scenarioId !== selected.id) return null;
    return run;
  }, [selected, run]);

  const resultByStep = useMemo(() => {
    const map = new Map<string, RunResult>();
    for (const r of lastRunForSelected?.results || []) map.set(r.stepId, r);
    return map;
  }, [lastRunForSelected]);

  const open = async (item: Scenario) => {
    setSelected(item);
    setPreview([]);
    setLastError(null);
    setBusy("preview");
    try {
      const data = await readJson(
        await fetch(`/api/v1/scenarios/${encodeURIComponent(item.id)}/preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: 10 }),
        }),
      );
      setPreview(data.steps || []);
    } catch (err) {
      setLastError(String((err as Error).message || err));
    } finally {
      setBusy(null);
    }
  };

  const runStep = async (stepId?: string) => {
    if (!selected) return;
    setBusy(stepId || "remaining");
    setLastError(null);
    try {
      const data = await readJson(
        await fetch(`/api/v1/scenarios/${encodeURIComponent(selected.id)}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            stepId,
            limit: 10,
            runId: lastRunForSelected && lastRunForSelected.status !== "reverted" ? lastRunForSelected.runId : undefined,
          }),
        }),
      );
      setRun(data);
    } catch (err) {
      setLastError(String((err as Error).message || err));
    } finally {
      setBusy(null);
    }
  };

  const revert = async () => {
    if (!run?.runId) return;
    setBusy("revert");
    setLastError(null);
    try {
      const data = await readJson(
        await fetch(`/api/v1/scenarios/runs/${encodeURIComponent(run.runId)}/revert`, { method: "POST" }),
      );
      setRun(data);
    } catch (err) {
      setLastError(String((err as Error).message || err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Layout>
      <div className="p-6 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Solution Scenarios</h2>
            <p className="text-sm text-muted-foreground">
              Overlay tagged source rows onto the loaded dump. Journeys still produce Four Views tables.
            </p>
          </div>
          <Button size="sm" variant="outline" disabled={!run || busy === "revert" || run.status === "reverted"} onClick={revert}>
            {busy === "revert" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            Revert last run
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSolution("")}
            className={`rounded-full border px-3 py-1 text-xs ${!solution ? "bg-violet-600 text-white border-violet-600" : "hover:bg-accent"}`}
          >
            All solutions
          </button>
          {solutions.map((item) => (
            <button
              key={item.id}
              onClick={() => setSolution(item.id)}
              className={`rounded-full border px-3 py-1 text-xs ${solution === item.id ? "bg-violet-600 text-white border-violet-600" : "hover:bg-accent"}`}
            >
              {item.title}
            </button>
          ))}
        </div>
        {error && <div className="text-sm text-destructive">{error}</div>}
        {loading && <div className="text-sm text-muted-foreground">Loading scenarios…</div>}
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => open(item)}
              className="text-left rounded-lg border p-4 hover:bg-muted/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium">{item.title}</div>
                  <div className="text-xs text-muted-foreground mt-1">{item.solutionTitle}</div>
                </div>
                <Badge variant="outline">{item.stepCount} steps</Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-2">{item.summary}</p>
              <div className="flex flex-wrap gap-1 mt-3">
                {item.plugins.map((plugin) => (
                  <Badge key={plugin} variant="secondary" className="text-[10px]">{plugin}</Badge>
                ))}
                {item.kpis.map((kpi) => (
                  <Badge key={kpi} variant="outline" className="text-[10px]">{kpi}</Badge>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>
      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={() => setSelected(null)}>
          <div className="h-full w-full max-w-2xl bg-background border-l shadow-2xl flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between px-5 py-4 border-b">
              <div>
                <h2 className="text-lg font-semibold">{selected.title}</h2>
                <p className="text-xs text-muted-foreground mt-1">{selected.summary}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!run || busy === "revert" || run.status === "reverted"}
                  onClick={revert}
                >
                  {busy === "revert" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  Revert
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setSelected(null)}><X className="h-4 w-4" /></Button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-5 space-y-4">
              {lastRunForSelected && <RunSummaryPanel run={lastRunForSelected} />}
              {(preview.length ? preview : selected.steps).map((step, idx) => {
                const completed = Boolean(lastRunForSelected?.completedSteps?.includes(step.id));
                const planned = "planned" in step ? (step as PreviewStep).planned : {};
                const stepResult = resultByStep.get(step.id);
                return (
                  <div key={step.id} className="rounded-lg border p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium">{idx + 1}. {step.title}</div>
                      <Badge variant={completed ? "default" : "outline"}>{completed ? "done" : step.action}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {PLUGIN_LABELS[step.plugin] || step.plugin} · {step.tables.join(", ")}
                    </div>
                    {!completed && Object.keys(planned).length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        Preview: {Object.entries(planned).map(([table, count]) => `${table} +${count}`).join(", ")}
                      </div>
                    )}
                    {stepResult && <StepResult result={stepResult} />}
                    <Button size="sm" variant="outline" disabled={completed || busy !== null} onClick={() => runStep(step.id)}>
                      {busy === step.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      Run this step
                    </Button>
                  </div>
                );
              })}
              <Button disabled={busy !== null || lastRunForSelected?.status === "completed"} onClick={() => runStep()}>
                {busy === "remaining" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run remaining
              </Button>
              {lastError && <div className="text-sm text-destructive">{lastError}</div>}
              <p className="text-[11px] text-muted-foreground">
                Changes persist to Redis and MinIO. Inspect tables under <strong>Tables</strong> — overlay rows carry{" "}
                <code className="font-mono">_scenario_id</code> and <code className="font-mono">_scenario_run_id</code>.
              </p>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
