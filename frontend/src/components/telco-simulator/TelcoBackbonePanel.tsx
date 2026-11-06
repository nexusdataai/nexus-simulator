import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, Loader2, Play } from 'lucide-react';

type BackboneCatalog = {
  layer: string;
  systems: { system_key: string; deliveries: string[] }[];
};

interface Props {
  /** e.g. '/api/v1/bss-simulator' */
  apiBase: string;
}

export function TelcoBackbonePanel({ apiBase }: Props) {
  const [catalog, setCatalog] = useState<BackboneCatalog | null>(null);
  const [selectedSystems, setSelectedSystems] = useState<Set<string>>(new Set());
  const [deliveries, setDeliveries] = useState<Set<string>>(new Set(['Table', 'File', 'API', 'Stream']));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSummary, setLastSummary] = useState<Record<string, unknown> | null>(null);

  const loadCatalog = useCallback(async () => {
    const res = await fetch(`${apiBase}/backbone/catalog`);
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as BackboneCatalog;
    setCatalog(data);
    setSelectedSystems(new Set(data.systems.map((s) => s.system_key)));
  }, [apiBase]);

  useEffect(() => {
    loadCatalog().catch((e) => setError(String(e)));
  }, [loadCatalog]);

  const toggleSystem = (key: string) => {
    setSelectedSystems((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });
  };

  const toggleDelivery = (d: string) => {
    setDeliveries((prev) => {
      const n = new Set(prev);
      if (n.has(d)) n.delete(d);
      else n.add(d);
      return n;
    });
  };

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/backbone/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systems: Array.from(selectedSystems),
          deliveries: Array.from(deliveries),
          refresh_identity: false,
          include_legacy_tables: true,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setLastSummary(data as Record<string, unknown>);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!catalog) {
    return (
      <div className="p-4 text-sm text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading Telco AI Backbone catalog…
      </div>
    );
  }

  return (
    <div className="border-b bg-muted/30 px-4 py-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Telco AI Backbone ({catalog.layer})</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
            Generate Table / File / API / Stream artifacts aligned with{' '}
            <code className="text-[11px]">data/Telco-Data/samples.js</code>. Full reference:{' '}
            <a href="/telco-atlas/" target="_blank" rel="noreferrer" className="text-primary inline-flex items-center gap-1">
              Telco AI Backbone <ExternalLink className="h-3 w-3" />
            </a>
          </p>
        </div>
        <button
          type="button"
          disabled={busy || selectedSystems.size === 0}
          onClick={generate}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Generate backbone
        </button>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-[11px] font-medium text-muted-foreground uppercase">Deliveries</span>
        {(['Table', 'File', 'API', 'Stream'] as const).map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => toggleDelivery(d)}
            className={`text-xs px-2 py-0.5 rounded-full border ${
              deliveries.has(d) ? 'bg-primary/15 border-primary text-primary' : 'border-border text-muted-foreground'
            }`}
          >
            {d}
          </button>
        ))}
      </div>

      <div className="max-h-40 overflow-y-auto border rounded-md p-2 bg-background text-xs space-y-1">
        {catalog.systems.map((s) => (
          <label key={s.system_key} className="flex items-start gap-2 cursor-pointer hover:bg-muted/50 rounded px-1 py-0.5">
            <input
              type="checkbox"
              checked={selectedSystems.has(s.system_key)}
              onChange={() => toggleSystem(s.system_key)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium">{s.system_key}</span>
              <span className="text-muted-foreground ml-2">({s.deliveries.join(', ')})</span>
            </span>
          </label>
        ))}
      </div>

      {lastSummary && (
        <pre className="text-[11px] bg-muted p-2 rounded overflow-auto max-h-32">{JSON.stringify(lastSummary, null, 2)}</pre>
      )}
    </div>
  );
}
