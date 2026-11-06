import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, Play, RefreshCw } from 'lucide-react';

type CatalogSystem = {
  system_key: string;
  layer: string;
  deliveries: string[];
  phase_a?: boolean;
};

export function TelcoSourcesPanel() {
  const [catalog, setCatalog] = useState<CatalogSystem[]>([]);
  const [profilePreset, setProfilePreset] = useState('default');
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [lineage, setLineage] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    const res = await fetch('/api/v1/telco-sources/catalog');
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setCatalog(data.systems || []);
  }, []);

  const loadLineage = useCallback(async () => {
    const res = await fetch('/api/v1/telco-sources/lineage');
    if (res.ok) setLineage(await res.json());
  }, []);

  useEffect(() => {
    loadCatalog().catch((e) => setError(String(e)));
    loadLineage().catch(() => undefined);
  }, [loadCatalog, loadLineage]);

  const applyPreset = async (preset: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/telco-sources/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset, profile_id: preset }),
      });
      if (!res.ok) throw new Error(await res.text());
      setProfilePreset(preset);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/telco-sources/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSummary(data.summary as Record<string, unknown>);
      await loadLineage();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const enabledCount = catalog.filter((s) => s.phase_a).length;

  return (
    <div className="space-y-6 p-4">
      <div>
        <h2 className="text-xl font-semibold">Telco source artifacts</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Generate vendor-native BSS / OSS / NSS data (Table, File, API, Stream) from the Telco-Data atlas.
        </p>
        <a
          href="/telco-atlas/"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm text-primary mt-2 hover:underline"
        >
          Open atlas reference <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => applyPreset('default')}
          className="px-3 py-1.5 rounded-md border text-sm"
        >
          Default profile
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => applyPreset('zain')}
          className="px-3 py-1.5 rounded-md border text-sm"
        >
          Zain preset
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={generate}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm"
        >
          {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Generate sources
        </button>
      </div>

      <p className="text-sm text-muted-foreground">
        Active preset: <strong>{profilePreset}</strong> · Atlas systems: {catalog.length} · Phase-A builders:{' '}
        {enabledCount}
      </p>

      {summary && (
        <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">{JSON.stringify(summary, null, 2)}</pre>
      )}

      {lineage && (
        <div>
          <h3 className="text-sm font-medium mb-2">Trace lineage (primary subscriber)</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">{JSON.stringify(lineage, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
