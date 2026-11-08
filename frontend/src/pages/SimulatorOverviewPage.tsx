import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import { Loader2, Sparkles } from "lucide-react";
import { seedAllTelco } from "@/services/cpqSimulatorService";
import { SIMULATOR_DOMAINS, pathForSimulator, type SimulatorEntry } from "@/config/simulatorDomains";

type SimItem = {
  service: string;
  enabled?: boolean;
  loaded?: boolean;
  table_count?: number;
  total_rows?: number;
  dump_timestamp?: string | null;
  bucket?: string;
};

export default function SimulatorOverviewPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<SimItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);

  const refresh = () => {
    fetch("/api/v1/simulators")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body) => setItems(body.items || []))
      .catch((err) => setError(String(err.message || err)));
  };

  useEffect(() => {
    refresh();
  }, []);

  const onSeedAllTelco = async () => {
    setSeeding(true);
    setSeedMsg(null);
    try {
      const res = await seedAllTelco();
      setSeedMsg(res.message);
      refresh();
    } catch (err) {
      setSeedMsg(String((err as Error).message || err));
    } finally {
      setSeeding(false);
    }
  };

  const SimulatorCard = ({ sim }: { sim: SimulatorEntry }) => {
    const item = items.find((i) => i.service === sim.serviceKey);
    const Icon = sim.icon;
    return (
      <button
        type="button"
        onClick={() => nav(pathForSimulator(sim.tabId))}
        className="text-left rounded-xl border bg-card p-4 hover:border-violet-500 transition-colors w-full"
      >
        <div className="flex items-center gap-2 mb-3">
          <Icon className="h-4 w-4 text-violet-600" />
          <span className="font-medium">{sim.label}</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <div>Enabled: {item?.enabled ? "yes" : item ? "no" : "—"}</div>
          <div>Loaded: {item?.loaded ? "yes" : item ? "no" : "—"}</div>
          <div>Tables: {item?.table_count ?? "—"}</div>
          <div>Rows: {item?.total_rows ?? "—"}</div>
        </div>
        {item?.dump_timestamp && (
          <div className="mt-2 text-[11px] text-muted-foreground">Dump: {item.dump_timestamp}</div>
        )}
      </button>
    );
  };

  return (
    <Layout>
      <div className="p-6 space-y-8">
        <div>
          <h2 className="text-xl font-semibold">Enterprise Data Simulators</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Enterprise table replicas hosted by nexus-simulator. Grouped by domain: supply chain vs telecom.
          </p>
        </div>
        {error && <div className="text-sm text-destructive">Failed to load catalog: {error}</div>}
        {seedMsg && <div className="text-sm text-muted-foreground">{seedMsg}</div>}

        {SIMULATOR_DOMAINS.map((domain) => {
          const isTelecom = domain.id === "telecom";
          const sectionClass =
            domain.id === "supply-chain"
              ? "rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-900/40 p-5"
              : "rounded-xl border border-emerald-200/80 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20 p-5";

          return (
            <section key={domain.id} className={sectionClass} aria-labelledby={`domain-title-${domain.id}`}>
              <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
                <div>
                  <h3 id={`domain-title-${domain.id}`} className="text-lg font-semibold">
                    {domain.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-0.5">{domain.description}</p>
                </div>
                {isTelecom && (
                  <button
                    type="button"
                    onClick={onSeedAllTelco}
                    disabled={seeding}
                    className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-60 shrink-0"
                  >
                    {seeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    Seed all telco
                  </button>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {domain.simulators.map((sim) => (
                  <SimulatorCard key={sim.tabId} sim={sim} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </Layout>
  );
}
