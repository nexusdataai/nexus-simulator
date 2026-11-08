import { useState } from 'react';
import { cn } from '@/lib/utils';

const MODES = ['Table', 'File', 'API', 'Stream'] as const;
export type DeliveryTab = (typeof MODES)[number];

const MODE_LABELS: Record<DeliveryTab, string> = {
  Table: 'Table Data',
  File: 'File',
  API: 'API',
  Stream: 'Stream',
};

type Counts = Partial<Record<Lowercase<DeliveryTab>, number>>;

type Props = {
  counts?: Counts;
  tables: React.ReactNode;
  files: React.ReactNode;
  apis: React.ReactNode;
  streams: React.ReactNode;
  defaultTab?: DeliveryTab;
  className?: string;
};

function tabCount(counts: Counts | undefined, tab: DeliveryTab): number | undefined {
  const key = tab.toLowerCase() as keyof Counts;
  const n = counts?.[key];
  return typeof n === 'number' ? n : undefined;
}

export function SimulatorDeliveryTabs({
  counts,
  tables,
  files,
  apis,
  streams,
  defaultTab = 'Table',
  className,
}: Props) {
  const [active, setActive] = useState<DeliveryTab>(defaultTab);
  const panes: Record<DeliveryTab, React.ReactNode> = { Table: tables, File: files, API: apis, Stream: streams };

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap gap-1 border-b pb-1" role="tablist" aria-label="Delivery type">
        {MODES.map((mode) => {
          const n = tabCount(counts, mode);
          const selected = active === mode;
          return (
            <button
              key={mode}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setActive(mode)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors border',
                selected
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-transparent bg-muted/50 text-muted-foreground hover:text-foreground',
              )}
            >
              {MODE_LABELS[mode]}
              {n !== undefined ? <span className="ml-1.5 text-[10px] opacity-80">({n})</span> : null}
            </button>
          );
        })}
      </div>
      <div role="tabpanel">{panes[active]}</div>
    </div>
  );
}

export function ArtifactModalityEmpty({
  modality,
  hint,
}: {
  modality: DeliveryTab;
  hint?: string;
}) {
  return (
    <p className="text-sm text-muted-foreground text-center py-8 px-4 border rounded-md bg-muted/20">
      No <strong className="font-medium text-foreground">{modality}</strong> artifacts yet.
      {hint ? <span className="block mt-2 text-xs">{hint}</span> : null}
    </p>
  );
}
