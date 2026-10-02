import { useEffect, useMemo, useState } from "react";
import Layout from "@/components/Layout";
import { SAPDataBrowserModal } from "@/components/sap-simulator/SAPDataBrowserModal";

type TableRow = {
  service: string;
  schema?: string;
  table?: string;
  columns?: number;
  rows?: number;
};

const ADMIN_PATH: Record<string, string> = {
  sfdc: "/api/v1/sfdc-simulator",
  oracle: "/api/v1/oracle-erp-simulator",
  sap: "/api/v1/sap-simulator",
  external: "/api/v1/external-simulator",
  tpm: "/api/v1/tpm-simulator",
  sourcing: "/api/v1/sourcing-simulator",
};

function makeBrowserClient(service: string) {
  const base = ADMIN_PATH[service];
  if (!base) {
    throw new Error(`Unknown simulator service: ${service}`);
  }
  return {
    getObjectRecords: async (schema: string, table: string, limit = 50, offset = 0) => {
      const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      const res = await fetch(
        `${base}/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}?${qs}`,
      );
      if (!res.ok) throw new Error(`Failed to load rows (${res.status})`);
      return res.json();
    },
    getObjectColumns: async (schema: string, table: string) => {
      const res = await fetch(
        `${base}/objects/${encodeURIComponent(schema)}/${encodeURIComponent(table)}/columns`,
      );
      if (!res.ok) throw new Error(`Failed to load columns (${res.status})`);
      return res.json();
    },
  };
}

export default function SimulatorTablesPage() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<TableRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TableRow | null>(null);

  useEffect(() => {
    fetch("/api/v1/simulators")
      .then((r) => r.json())
      .then(async (body) => {
        const services = (body.items || []).map((i: { service: string }) => i.service);
        const all: TableRow[] = [];
        for (const service of services) {
          const res = await fetch(`/api/v1/simulators/${service}`);
          if (!res.ok) continue;
          const detail = await res.json();
          for (const table of detail.tables || []) {
            all.push({
              service,
              schema: table.schema || table.schemaName,
              table: table.table || table.tableName,
              columns: table.columns || table.columnCount,
              rows: table.rows || table.rowCount,
            });
          }
        }
        setRows(all);
      })
      .catch((err) => setError(String(err.message || err)));
  }, []);

  const filtered = useMemo(() => {
    const needle = q.toLowerCase();
    return rows
      .filter((r) => `${r.service} ${r.schema} ${r.table}`.toLowerCase().includes(needle))
      .sort((a, b) => (b.rows || 0) - (a.rows || 0) || (a.table || "").localeCompare(b.table || ""));
  }, [rows, q]);

  const browserClient = useMemo(
    () => (selected ? makeBrowserClient(selected.service) : undefined),
    [selected?.service],
  );

  return (
    <Layout>
      <div className="p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Cross-system catalog</h2>
          <p className="text-sm text-muted-foreground">Click a table to browse its rows.</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search schema or table"
          className="w-full max-w-md rounded-md border bg-background px-3 py-2 text-sm"
        />
        {error && <div className="text-sm text-destructive">{error}</div>}
        <div className="rounded-lg border overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-2">Service</th>
                <th className="text-left p-2">Schema</th>
                <th className="text-left p-2">Table</th>
                <th className="text-left p-2">Columns</th>
                <th className="text-left p-2">Rows</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr
                  key={`${r.service}-${r.schema}-${r.table}-${i}`}
                  className="border-t cursor-pointer hover:bg-muted/40"
                  onClick={() => setSelected(r)}
                >
                  <td className="p-2">{r.service}</td>
                  <td className="p-2">{r.schema}</td>
                  <td className="p-2 font-medium">{r.table}</td>
                  <td className="p-2">{r.columns ?? "—"}</td>
                  <td className="p-2">{r.rows ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {selected?.schema && selected.table && browserClient && (
        <SAPDataBrowserModal
          isOpen
          schema={selected.schema}
          table={selected.table}
          service={browserClient}
          catalogRowCount={selected.rows}
          onClose={() => setSelected(null)}
        />
      )}
    </Layout>
  );
}
