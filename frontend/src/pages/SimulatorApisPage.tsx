import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X, Play, Loader2 } from "lucide-react";

type HttpMethod = { method: string; path: string; kind: string };

type VendorApi = {
  id: string;
  system: "sfdc" | "oracle" | "sap";
  name: string;
  table: string;
  schema: string;
  rowCount: number;
  columnCount: number;
  pk?: string;
  docsUrl?: string;
  methods: HttpMethod[];
};

type Tab = "sfdc" | "oracle" | "sap";

const TABS: { id: Tab; label: string }[] = [
  { id: "sfdc", label: "Salesforce" },
  { id: "oracle", label: "Oracle ERP" },
  { id: "sap", label: "SAP S/4HANA" },
];

function fillPath(path: string, id: string) {
  return path.replace("{id}", encodeURIComponent(id)).replace("('{id}')", `('${id}')`);
}

export default function SimulatorApisPage() {
  const [tab, setTab] = useState<Tab>("sfdc");
  const [items, setItems] = useState<VendorApi[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [hasDataOnly, setHasDataOnly] = useState(true);
  const [selected, setSelected] = useState<VendorApi | null>(null);
  const [method, setMethod] = useState<HttpMethod | null>(null);
  const [path, setPath] = useState("");
  const [body, setBody] = useState("{}");
  const [result, setResult] = useState("");
  const [running, setRunning] = useState(false);
  const [batching, setBatching] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/vendor-apis?system=${tab}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(data.items || []);
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
    setSelected(null);
    setPicked(new Set());
  }, [load]);

  const filtered = useMemo(() => {
    const needle = q.toLowerCase();
    return items.filter((item) => {
      if (hasDataOnly && !item.rowCount) return false;
      if (methodFilter && !item.methods.some((m) => m.method === methodFilter)) return false;
      if (!needle) return true;
      return `${item.name} ${item.table} ${item.id} ${item.methods.map((m) => m.path).join(" ")}`.toLowerCase().includes(needle);
    });
  }, [items, q, hasDataOnly, methodFilter]);

  const open = async (item: VendorApi) => {
    setSelected(item);
    const update = item.methods.find((m) => m.kind === "update") || item.methods[0];
    setMethod(update);
    let recordId = "";
    let sample: Record<string, unknown> = {};
    try {
      const res = await fetch(`/api/v1/vendor-apis/${encodeURIComponent(item.id)}/sample`);
      if (res.ok) {
        const data = await res.json();
        sample = data.row || {};
        recordId = String(sample[item.pk || ""] ?? Object.values(sample)[0] ?? "");
      }
    } catch {
      /* empty */
    }
    setPath(fillPath(update.path, recordId || "ID"));
    setBody(JSON.stringify(sample, null, 2));
    setResult("");
  };

  const runOne = async () => {
    if (!method) return;
    setRunning(true);
    try {
      const res = await fetch(path, {
        method: method.method,
        headers: { "Content-Type": "application/json" },
        body: ["GET", "HEAD", "DELETE"].includes(method.method) ? undefined : body,
      });
      const text = await res.text();
      setResult(`${res.status} ${res.statusText}\n${text}`);
      load();
    } catch (err) {
      setResult(String(err));
    } finally {
      setRunning(false);
    }
  };

  const runBatch = async (mode: "operations" | "canary_writes") => {
    setBatching(true);
    setResult("");
    try {
      const payload =
        mode === "canary_writes"
          ? { system: tab, mode: "canary_writes", limit: 50 }
          : {
              system: tab,
              mode: "operations",
              operations: filtered
                .filter((i) => picked.has(i.id))
                .map((i) => {
                  const m = i.methods.find((x) => x.kind === "list") || i.methods[0];
                  return { method: m.method, path: m.path };
                }),
            };
      const res = await fetch("/api/v1/vendor-apis/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      setResult(`${res.status} ${res.statusText}\n${text}`);
      load();
    } catch (err) {
      setResult(String(err));
    } finally {
      setBatching(false);
    }
  };

  return (
    <Layout>
      <div className="p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Official vendor APIs</h2>
          <p className="text-sm text-muted-foreground">
            Salesforce sObject REST, Oracle Fusion REST, and SAP OData over the loaded simulator catalogs. Writes update Redis and S3.
          </p>
        </div>
        <div className="flex gap-1 border-b">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm border-b-2 ${tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search object or path"
            className="w-full max-w-md rounded-md border bg-background px-3 py-2 text-sm"
          />
          <select
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">All methods</option>
            {["GET", "POST", "PATCH", "DELETE"].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={hasDataOnly} onChange={(e) => setHasDataOnly(e.target.checked)} />
            Has data
          </label>
          <Button size="sm" variant="outline" disabled={batching} onClick={() => runBatch("canary_writes")}>
            {batching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Canary all populated writes
          </Button>
          <Button size="sm" variant="outline" disabled={batching || picked.size === 0} onClick={() => runBatch("operations")}>
            Run selected ({picked.size})
          </Button>
        </div>
        {error && <div className="text-sm text-destructive">{error}</div>}
        {loading && <div className="text-sm text-muted-foreground">Loading catalog…</div>}
        <div className="rounded-lg border overflow-auto max-h-[60vh]">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 sticky top-0">
              <tr>
                <th className="p-2 w-8" />
                <th className="text-left p-2">Object</th>
                <th className="text-left p-2">Table</th>
                <th className="text-left p-2">Path</th>
                <th className="text-left p-2">Rows</th>
                <th className="text-left p-2">Methods</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const list = item.methods.find((m) => m.kind === "list") || item.methods[0];
                return (
                  <tr
                    key={item.id}
                    className="border-t cursor-pointer hover:bg-muted/40"
                    onClick={() => open(item)}
                  >
                    <td className="p-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={picked.has(item.id)}
                        onChange={(e) => {
                          const next = new Set(picked);
                          if (e.target.checked) next.add(item.id);
                          else next.delete(item.id);
                          setPicked(next);
                        }}
                      />
                    </td>
                    <td className="p-2 font-medium">{item.name}</td>
                    <td className="p-2">{item.table}</td>
                    <td className="p-2 font-mono text-xs">{list.path}</td>
                    <td className="p-2">{item.rowCount}</td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-1">
                        {[...new Set(item.methods.map((m) => m.method))].map((m) => (
                          <Badge key={m} variant="outline" className="text-[10px]">{m}</Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {result && !selected && (
          <pre className="rounded-md border bg-muted/40 p-3 text-xs overflow-auto whitespace-pre-wrap max-h-64">{result}</pre>
        )}
      </div>
      {selected && method && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setSelected(null)}>
          <div className="bg-background border rounded-xl shadow-2xl w-[90vw] max-w-3xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h2 className="text-lg font-semibold">{selected.name}</h2>
                <p className="text-xs text-muted-foreground">{selected.schema}.{selected.table} · {selected.rowCount.toLocaleString()} rows</p>
              </div>
              <div className="flex items-center gap-2">
                {selected.docsUrl && (
                  <a href={selected.docsUrl} target="_blank" rel="noreferrer" className="text-xs text-primary underline">
                    Docs
                  </a>
                )}
                <Button variant="ghost" size="icon" onClick={() => setSelected(null)}><X className="h-4 w-4" /></Button>
              </div>
            </div>
            <div className="p-5 space-y-3 overflow-auto">
              <div className="flex flex-wrap gap-1">
                {selected.methods.map((m) => (
                  <button
                    key={`${m.method}-${m.kind}`}
                    className={`text-xs rounded-md border px-2 py-1 ${method === m ? "bg-violet-600 text-white" : "hover:bg-accent"}`}
                    onClick={() => {
                      setMethod(m);
                      const idMatch = path.match(/[^/]+$/);
                      setPath(fillPath(m.path, idMatch?.[0] || "ID"));
                    }}
                  >
                    {m.method} {m.kind}
                  </button>
                ))}
              </div>
              <input value={path} onChange={(e) => setPath(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono" />
              {!["GET", "HEAD", "DELETE"].includes(method.method) && (
                <textarea value={body} onChange={(e) => setBody(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm min-h-[160px] font-mono" />
              )}
              <Button onClick={runOne} disabled={running}>
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Run
              </Button>
              {result && <pre className="rounded-md border bg-muted/40 p-3 text-xs overflow-auto whitespace-pre-wrap max-h-64">{result}</pre>}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
