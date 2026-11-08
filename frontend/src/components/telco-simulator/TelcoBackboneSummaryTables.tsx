import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { BackboneCatalog } from './telcoBackboneTypes';
import {
  destinationFolderFromPath,
  resolveProductFamily,
  vendorLabel,
} from './telcoBackboneUtils';
import type { ApiPreviewTarget, FilePreviewTarget, StreamPreviewTarget } from './TelcoBackboneArtifactPreviewDialog';

type SummaryRow = {
  method?: string;
  route_path?: string;
  system_key?: string;
  vendor_code?: string | null;
  name?: string;
  path?: string;
  topic?: string;
  event_count?: number;
};

type Props = {
  catalog: BackboneCatalog;
  files: SummaryRow[];
  apis: SummaryRow[];
  apiBase: string;
  onPreviewFile: (target: FilePreviewTarget) => void;
  onPreviewApi: (target: ApiPreviewTarget) => void;
};

function useFilter<T>(rows: T[], predicate: (row: T, q: string) => boolean) {
  const [search, setSearch] = useState('');
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => predicate(r, q));
  }, [rows, search, predicate]);
  return { search, setSearch, filtered };
}

export function TelcoBackboneFilesTable({ catalog, files, onPreviewFile }: Omit<Props, 'apis' | 'apiBase' | 'onPreviewApi'>) {
  const { search, setSearch, filtered } = useFilter(files, (f, q) => {
    const fam = resolveProductFamily(catalog, f.system_key, f.path);
    const name = (f.name || f.path?.split('/').pop() || '').toLowerCase();
    const folder = destinationFolderFromPath(f.path).toLowerCase();
    const key = (fam?.key || '').toLowerCase();
    return name.includes(q) || folder.includes(q) || key.includes(q) || (f.path || '').toLowerCase().includes(q);
  });

  if (!files.length) {
    return <p className="text-muted-foreground text-[11px] px-1">Enable File delivery for a family, then Generate.</p>;
  }

  return (
    <div className="space-y-2">
      <div className="relative w-full max-w-xs">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Filter files…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8 h-8 text-xs"
        />
      </div>
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50 text-left border-b">
              <th className="px-2 py-2 font-medium min-w-[9rem]">Product family</th>
              <th className="px-2 py-2 font-medium min-w-[8rem]">File</th>
              <th className="px-2 py-2 font-medium min-w-[10rem]">Destination</th>
              <th className="px-2 py-2 font-medium w-[4.5rem]">Vendor</th>
              <th className="px-2 py-2 font-medium w-[4.5rem] text-right" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((f, i) => {
              const fam = resolveProductFamily(catalog, f.system_key, f.path);
              const fileName = f.name || f.path?.split('/').pop() || '—';
              const folder = destinationFolderFromPath(f.path) || '—';
              const path = f.path || '';
              return (
                <tr key={`${path}-${i}`} className="border-t border-border/80 hover:bg-muted/30">
                  <td className="px-2 py-2 align-top">
                    <div className="font-medium leading-tight">{fam?.key || '—'}</div>
                    {fam?.slug ? <div className="text-[10px] text-muted-foreground mt-0.5">{fam.slug}</div> : null}
                  </td>
                  <td className="px-2 py-2 align-top">
                    <button
                      type="button"
                      className="text-left text-primary hover:underline font-medium break-all"
                      onClick={() =>
                        path &&
                        onPreviewFile({
                          type: 'file',
                          path,
                          name: fileName,
                          productFamily: fam?.key,
                        })
                      }
                      disabled={!path}
                    >
                      {fileName}
                    </button>
                  </td>
                  <td className="px-2 py-2 align-top font-mono text-[10px] text-muted-foreground break-all">{folder}</td>
                  <td className="px-2 py-2 align-top text-[10px] text-muted-foreground">
                    {f.vendor_code ? vendorLabel(catalog, f.vendor_code) : '—'}
                  </td>
                  <td className="px-2 py-2 align-top text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-[10px] px-2"
                      disabled={!path}
                      onClick={() =>
                        onPreviewFile({
                          type: 'file',
                          path,
                          name: fileName,
                          productFamily: fam?.key,
                        })
                      }
                    >
                      View
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-muted-foreground text-[11px] py-4">No files match the filter.</p>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground">
        {filtered.length} of {files.length} file{files.length === 1 ? '' : 's'}
      </p>
    </div>
  );
}

export function TelcoBackboneApisTable({
  catalog,
  apis,
  apiBase,
  onPreviewApi,
}: Omit<Props, 'files' | 'onPreviewFile'>) {
  const { search, setSearch, filtered } = useFilter(apis, (a, q) => {
    const fam = resolveProductFamily(catalog, a.system_key);
    const route = (a.route_path || '').toLowerCase();
    const method = (a.method || '').toLowerCase();
    const key = (fam?.key || '').toLowerCase();
    return route.includes(q) || method.includes(q) || key.includes(q);
  });

  if (!apis.length) {
    return <p className="text-muted-foreground text-[11px] px-1">Enable API delivery for a family, then Generate.</p>;
  }

  return (
    <div className="space-y-2">
      <div className="relative w-full max-w-xs">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Filter APIs…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8 h-8 text-xs"
        />
      </div>
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50 text-left border-b">
              <th className="px-2 py-2 font-medium min-w-[9rem]">Product family</th>
              <th className="px-2 py-2 font-medium w-[4rem]">Method</th>
              <th className="px-2 py-2 font-medium min-w-[12rem]">Route</th>
              <th className="px-2 py-2 font-medium w-[4.5rem]">Vendor</th>
              <th className="px-2 py-2 font-medium w-[5.5rem] text-right" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((a, i) => {
              const fam = resolveProductFamily(catalog, a.system_key);
              const rp = (a.route_path || '').replace(/^\//, '');
              const href = `${apiBase}/vendor-api/${rp}`;
              const method = (a.method || 'GET').toUpperCase();
              return (
                <tr key={`${method}-${a.route_path}-${i}`} className="border-t border-border/80 hover:bg-muted/30">
                  <td className="px-2 py-2 align-top">
                    <div className="font-medium leading-tight">{fam?.key || '—'}</div>
                    {fam?.slug ? <div className="text-[10px] text-muted-foreground mt-0.5">{fam.slug}</div> : null}
                  </td>
                  <td className="px-2 py-2 align-top">
                    <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0">
                      {method}
                    </Badge>
                  </td>
                  <td className="px-2 py-2 align-top font-mono text-[10px] break-all">
                    <a href={href} className="text-primary hover:underline" target="_blank" rel="noreferrer">
                      /{rp}
                    </a>
                  </td>
                  <td className="px-2 py-2 align-top text-[10px] text-muted-foreground">
                    {a.vendor_code ? vendorLabel(catalog, a.vendor_code) : '—'}
                  </td>
                  <td className="px-2 py-2 align-top text-right whitespace-nowrap">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-[10px] px-2"
                      onClick={() =>
                        onPreviewApi({
                          type: 'api',
                          method,
                          href,
                          routePath: `/${rp}`,
                          productFamily: fam?.key,
                        })
                      }
                    >
                      View
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-muted-foreground text-[11px] py-4">No APIs match the filter.</p>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground">
        {filtered.length} of {apis.length} endpoint{apis.length === 1 ? '' : 's'}
      </p>
    </div>
  );
}

export function TelcoBackboneStreamsTable({
  catalog,
  streams,
  apiBase,
  onPreviewStream,
}: {
  catalog: BackboneCatalog;
  streams: SummaryRow[];
  apiBase: string;
  onPreviewStream: (target: StreamPreviewTarget) => void;
}) {
  const { search, setSearch, filtered } = useFilter(streams, (s, q) => {
    const fam = resolveProductFamily(catalog, s.system_key);
    const topic = (s.topic || '').toLowerCase();
    const key = (fam?.key || '').toLowerCase();
    return topic.includes(q) || key.includes(q);
  });

  if (!streams.length) {
    return <p className="text-muted-foreground text-[11px] px-1">Enable Stream delivery for a family, then Generate.</p>;
  }

  return (
    <div className="space-y-2">
      <div className="relative w-full max-w-xs">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Filter streams…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8 h-8 text-xs"
        />
      </div>
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50 text-left border-b">
              <th className="px-2 py-2 font-medium min-w-[9rem]">Product family</th>
              <th className="px-2 py-2 font-medium min-w-[10rem]">Topic</th>
              <th className="px-2 py-2 font-medium w-[4.5rem] text-right">Events</th>
              <th className="px-2 py-2 font-medium w-[4.5rem]">Vendor</th>
              <th className="px-2 py-2 font-medium min-w-[8rem]">SSE replay</th>
              <th className="px-2 py-2 font-medium w-[4.5rem] text-right" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((srow, i) => {
              const fam = resolveProductFamily(catalog, srow.system_key);
              const topic = srow.topic || '—';
              const enc = encodeURIComponent(srow.topic || '');
              const sseHref = `${apiBase}/backbone/stream/${enc}`;
              return (
                <tr key={`${topic}-${i}`} className="border-t border-border/80 hover:bg-muted/30">
                  <td className="px-2 py-2 align-top">
                    <div className="font-medium leading-tight">{fam?.key || '—'}</div>
                    {fam?.slug ? <div className="text-[10px] text-muted-foreground mt-0.5">{fam.slug}</div> : null}
                  </td>
                  <td className="px-2 py-2 align-top">
                    <button
                      type="button"
                      className="text-left text-primary hover:underline font-mono text-[10px] break-all"
                      disabled={!srow.topic}
                      onClick={() =>
                        srow.topic &&
                        onPreviewStream({
                          type: 'stream',
                          topic: srow.topic,
                          productFamily: fam?.key,
                          sseHref,
                        })
                      }
                    >
                      {topic}
                    </button>
                  </td>
                  <td className="px-2 py-2 align-top text-right tabular-nums">{srow.event_count ?? 0}</td>
                  <td className="px-2 py-2 align-top text-[10px] text-muted-foreground">
                    {srow.vendor_code ? vendorLabel(catalog, srow.vendor_code) : '—'}
                  </td>
                  <td className="px-2 py-2 align-top font-mono text-[10px]">
                    <a href={sseHref} className="text-primary hover:underline break-all" target="_blank" rel="noreferrer" title={sseHref}>
                      replay
                    </a>
                  </td>
                  <td className="px-2 py-2 align-top text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-[10px] px-2"
                      disabled={!srow.topic}
                      onClick={() =>
                        onPreviewStream({
                          type: 'stream',
                          topic: srow.topic || '',
                          productFamily: fam?.key,
                          sseHref,
                        })
                      }
                    >
                      View
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-muted-foreground text-[11px] py-4">No streams match the filter.</p>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground">
        {filtered.length} of {streams.length} topic{streams.length === 1 ? '' : 's'}
      </p>
    </div>
  );
}
