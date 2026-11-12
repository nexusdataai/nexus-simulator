/** Header and facts shared by every system screen. */
import * as React from 'react';
import { cn } from '@/core/utils';
import { StatusPill, type KV } from '@/components/ds/kit';
import { AnimatedNumber } from '@/components/ds/AnimatedNumber';
import { SystemLogo } from '@/components/ds/SystemLogo';
import type { SimulatorDef } from '@/config/simulators';
import { ago, dateTime, num } from '@/core/format';
import type { SimStatus } from '@/services/api';

interface SystemHeaderProps {
  sim: SimulatorDef;
  status?: SimStatus | null;
  loading?: boolean;
  /** Extra line under the description. */
  note?: React.ReactNode;
  actions?: React.ReactNode;
}

export function SystemHeader({ sim, status, loading, note, actions }: SystemHeaderProps) {
  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div className="flex min-w-0 items-start gap-4">
        <SystemLogo system={sim.logo} tile size="lg" className="mt-0.5" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h1 className="text-xl font-medium tracking-tight text-foreground">{sim.name}</h1>
            {status ? (
              <>
                <StatusPill status={status.enabled ? 'enabled' : 'disabled'}>{status.enabled ? 'Switched on' : 'Switched off'}</StatusPill>
                <StatusPill status={status.loaded ? 'healthy' : 'pending'}>{status.loaded ? 'Data loaded' : 'No data loaded'}</StatusPill>
              </>
            ) : loading ? <span className="text-xs text-subtle-foreground">Checking…</span> : null}
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sim.description}</p>
          {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Numbers on the left, storage details on the right. Everything visible. */
export function SystemFacts({ status, extra = [] }: { status?: SimStatus | null; extra?: KV[] }) {
  const s = status;
  const stats: { label: string; value?: number | null; hint?: string }[] = [
    { label: 'Tables', value: s?.table_count, hint: s ? `${num(s.tables_with_data)} with data` : undefined },
    { label: 'Rows', value: s?.total_rows },
    { label: 'Files', value: s?.file_count },
    { label: 'APIs', value: s?.api_count },
    { label: 'Streams', value: s?.stream_count },
  ];
  const facts: KV[] = [
    { label: 'Schema', value: s?.schema || '—', mono: true },
    { label: 'Storage bucket', value: s?.bucket || 'Not configured', mono: !!s?.bucket },
    { label: 'Table data folder', value: s?.table_data_prefix || '—', mono: true },
    { label: 'File data folder', value: s?.files_data_prefix || '—', mono: true },
    { label: 'Data dump from', value: s?.dump_timestamp ? `${dateTime(s.dump_timestamp)} (${ago(s.dump_timestamp)})` : '—' },
    { label: 'Last loaded', value: s?.last_loaded ? `${dateTime(s.last_loaded)} (${ago(s.last_loaded)})` : '—' },
    ...extra,
  ];
  return (
    <div className="grid gap-x-10 gap-y-5 border-y border-border py-5 xl:grid-cols-[minmax(0,4fr)_minmax(0,7fr)]">
      <dl className="grid grid-cols-2 content-start gap-x-6 gap-y-5 sm:grid-cols-3">
        {stats.map(st => (
          <div key={st.label} className="min-w-0">
            <dt className="text-sm text-muted-foreground">{st.label}</dt>
            <dd className="mt-1 text-2xl font-medium tracking-tight text-foreground"><AnimatedNumber value={st.value} className="num" /></dd>
            {st.hint && <div className="num mt-0.5 text-xs text-muted-foreground">{st.hint}</div>}
          </div>
        ))}
      </dl>
      <dl className="grid content-start gap-x-8 gap-y-4 sm:grid-cols-2">
        {facts.map(f => (
          <div key={f.label} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{f.label}</dt>
            <dd className={cn('mt-0.5 break-all text-sm text-foreground', f.mono && 'font-mono text-xs leading-5')}>{f.value ?? '—'}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
