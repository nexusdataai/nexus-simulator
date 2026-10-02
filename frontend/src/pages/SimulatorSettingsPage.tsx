import { useEffect, useState } from "react";
import Layout from "@/components/Layout";

export default function SimulatorSettingsPage() {
  const [health, setHealth] = useState<unknown>(null);
  const [ready, setReady] = useState<unknown>(null);
  const [catalog, setCatalog] = useState<unknown>(null);

  useEffect(() => {
    fetch("/health").then((r) => r.json()).then(setHealth).catch((e) => setHealth({ error: String(e) }));
    fetch("/readiness").then((r) => r.json()).then(setReady).catch((e) => setReady({ error: String(e) }));
    fetch("/api/v1/simulators").then((r) => r.json()).then(setCatalog).catch((e) => setCatalog({ error: String(e) }));
  }, []);

  return (
    <Layout>
      <div className="p-6 space-y-4 max-w-3xl">
        <h2 className="text-xl font-semibold">Simulator settings</h2>
        <p className="text-sm text-muted-foreground">
          Redis and S3 are owned by this service. Ontology talks to these catalogs over HTTP only.
        </p>
        <section>
          <h3 className="font-medium mb-1">Health</h3>
          <pre className="rounded-md border bg-muted/40 p-3 text-xs overflow-auto">{JSON.stringify(health, null, 2)}</pre>
        </section>
        <section>
          <h3 className="font-medium mb-1">Readiness</h3>
          <pre className="rounded-md border bg-muted/40 p-3 text-xs overflow-auto">{JSON.stringify(ready, null, 2)}</pre>
        </section>
        <section>
          <h3 className="font-medium mb-1">Catalog</h3>
          <pre className="rounded-md border bg-muted/40 p-3 text-xs overflow-auto">{JSON.stringify(catalog, null, 2)}</pre>
        </section>
      </div>
    </Layout>
  );
}
