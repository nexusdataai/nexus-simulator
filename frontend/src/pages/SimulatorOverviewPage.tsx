import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import {
  Database,
  Building2,
  Factory,
  Globe,
  Receipt,
  ClipboardList,
  Smartphone,
  Signal,
  Server,
  Sparkles,
  Loader2,
} from "lucide-react";
import { seedAllTelco } from "@/services/cpqSimulatorService";

type SimItem = {
  service: string;
  enabled?: boolean;
  loaded?: boolean;
  table_count?: number;
  total_rows?: number;
  dump_timestamp?: string | null;
  bucket?: string;
};

const META: Record<string, { label: string; path: string; icon: React.ElementType }> = {
  sfdc: { label: "Salesforce", path: "/simulators/sfdc", icon: Database },
  oracle: { label: "Oracle ERP", path: "/simulators/oracle-erp", icon: Building2 },
  sap: { label: "SAP S/4HANA", path: "/simulators/sap", icon: Factory },
  external: { label: "External Sources", path: "/simulators/external", icon: Globe },
  tpm: { label: "TPM Trade CPQ", path: "/simulators/tpm", icon: Receipt },
  sourcing: { label: "Sourcing Buy CPQ", path: "/simulators/sourcing", icon: ClipboardList },
  bss: { label: "BSS Telecom", path: "/simulators/bss", icon: Smartphone },
  nss: { label: "NSS Telecom", path: "/simulators/nss", icon: Signal },
  oss: { label: "OSS Telecom", path: "/simulators/oss", icon: Server },
  telco_golden: { label: "Telco Golden", path: "/simulators/telco-golden", icon: Sparkles },
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

  return (
    <Layout>
      <div className="p-6 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-xl font-semibold">Enterprise Data Simulators</h2>
            <p className="text-sm text-muted-foreground">
              FDW-compatible replicas hosted by nexus-simulator. Ontology and ReAct call this service over HTTP.
            </p>
          </div>
          <button
            type="button"
            onClick={onSeedAllTelco}
            disabled={seeding}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-60"
          >
            {seeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Seed all telco
          </button>
        </div>
        {seedMsg && <div className="text-sm text-muted-foreground">{seedMsg}</div>}
        {error && <div className="text-sm text-destructive">Failed to load catalog: {error}</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Object.entries(META).map(([key, meta]) => {
            const item = items.find((i) => i.service === key);
            const Icon = meta.icon;
            return (
              <button
                key={key}
                onClick={() => nav(meta.path)}
                className="text-left rounded-xl border bg-card p-4 hover:border-violet-500 transition-colors"
              >
                <div className="flex items-center gap-2 mb-3">
                  <Icon className="h-4 w-4 text-violet-600" />
                  <span className="font-medium">{meta.label}</span>
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
          })}
        </div>
      </div>
    </Layout>
  );
}
