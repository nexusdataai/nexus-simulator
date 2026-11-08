import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  formatJsonForDisplay,
  previewBackboneFileContent,
  recordsToTable,
  type ContentPreview,
} from './backboneContentPreview';

function PreviewBody({ preview }: { preview: ContentPreview }) {
  if (preview.kind === 'csv' || (preview.kind === 'json' && preview.asTable)) {
    const { headers, rows } = preview.kind === 'csv' ? preview : preview.asTable!;
    return (
      <div className="rounded-md border overflow-auto max-h-[min(60vh,480px)]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50 text-left border-b">
              {headers.map((h) => (
                <th key={h} className="px-2 py-1.5 font-medium whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className="border-t border-border/60 hover:bg-muted/20">
                {row.map((cell, ci) => (
                  <td key={ci} className="px-2 py-1.5 align-top break-all max-w-[16rem]">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (preview.kind === 'json') {
    return (
      <pre className="text-[11px] bg-muted/40 rounded-md p-3 overflow-auto max-h-[min(60vh,480px)] font-mono whitespace-pre-wrap break-all">
        {formatJsonForDisplay(preview.value)}
      </pre>
    );
  }

  return (
    <pre className="text-[11px] bg-muted/40 rounded-md p-3 overflow-auto max-h-[min(60vh,480px)] font-mono whitespace-pre-wrap break-all">
      {preview.content}
    </pre>
  );
}

export type FilePreviewTarget = {
  type: 'file';
  path: string;
  name: string;
  productFamily?: string;
};

export type ApiPreviewTarget = {
  type: 'api';
  method: string;
  href: string;
  routePath: string;
  productFamily?: string;
};

export type StreamPreviewTarget = {
  type: 'stream';
  topic: string;
  productFamily?: string;
  sseHref: string;
};

export type PreviewTarget = FilePreviewTarget | ApiPreviewTarget | StreamPreviewTarget | null;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  target: PreviewTarget;
  apiBase: string;
};

export function TelcoBackboneArtifactPreviewDialog({ open, onOpenChange, target, apiBase }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ContentPreview | null>(null);

  const load = useCallback(async () => {
    if (!target || !open) return;
    setLoading(true);
    setError(null);
    setPreview(null);
    try {
      if (target.type === 'file') {
        const q = encodeURIComponent(target.path);
        const res = await fetch(`${apiBase}/backbone/file?path=${q}`);
        if (!res.ok) throw new Error(await res.text());
        const text = await res.text();
        setPreview(previewBackboneFileContent(text, target.name));
      } else if (target.type === 'stream') {
        const q = encodeURIComponent(target.topic);
        const res = await fetch(`${apiBase}/backbone/stream-events?topic=${q}`);
        if (!res.ok) throw new Error(await res.text());
        const payload = (await res.json()) as { events?: unknown[] };
        const events = payload.events ?? [];
        setPreview({ kind: 'json', value: events, asTable: recordsToTable(events) });
      } else {
        const res = await fetch(target.href, {
          method: target.method,
          headers: { Accept: 'application/json' },
        });
        if (!res.ok) throw new Error(await res.text());
        const data = (await res.json()) as unknown;
        setPreview({ kind: 'json', value: data, asTable: recordsToTable(data) });
      }
    } catch (e) {
      setError((e as Error).message || 'Failed to load content');
    } finally {
      setLoading(false);
    }
  }, [target, open, apiBase]);

  useEffect(() => {
    if (open && target) load();
    if (!open) {
      setPreview(null);
      setError(null);
    }
  }, [open, target, load]);

  const title =
    target?.type === 'file'
      ? target.name
      : target?.type === 'api'
        ? `${target.method} ${target.routePath}`
        : target?.type === 'stream'
          ? target.topic
          : 'Preview';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[min(100vw-2rem,52rem)] max-h-[min(90vh,640px)] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-base pr-6 break-all">{title}</DialogTitle>
          <DialogDescription className="text-xs space-y-0.5">
            {target?.productFamily ? (
              <span className="block">
                Product family: <strong className="font-medium text-foreground">{target.productFamily}</strong>
              </span>
            ) : null}
            {target?.type === 'file' ? (
              <span className="block font-mono break-all text-muted-foreground">{target.path}</span>
            ) : target?.type === 'api' ? (
              <span className="block font-mono break-all text-muted-foreground">{target.href}</span>
            ) : target?.type === 'stream' ? (
              <span className="block font-mono break-all text-muted-foreground">SSE: {target.sseHref}</span>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 min-h-0 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          {!loading && !error && preview && <PreviewBody preview={preview} />}
        </div>
        {target?.type === 'api' && <ApiFooter href={target.href} method={target.method} />}
        {target?.type === 'stream' && (
          <ApiFooter href={target.sseHref} method="SSE" label="Open SSE replay in new tab" />
        )}
      </DialogContent>
    </Dialog>
  );
}

function ApiFooter({ href, method, label }: { href: string; method: string; label?: string }) {
  const text = label ?? `Open ${method} in new tab`;
  return (
    <div className="flex justify-end pt-2 border-t">
      <Button variant="outline" size="sm" asChild>
        <a href={href} target="_blank" rel="noreferrer">
          {text}
        </a>
      </Button>
    </div>
  );
}
