import * as React from 'react';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { CodeBlock, InlineError, KeyValues, StatusPill, TableShell } from '@/components/ds/kit';
import { PageHeader, SectionHeader } from '@/components/ds/primitives';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { simByService } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { useTheme } from '@/hooks/use-theme';
import { dateTime } from '@/core/format';
import { getHealth, getReadiness, listSimulators } from '@/services/api';

const text = (v: unknown) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

export default function SettingsPage() {
  const health = useLoad(getHealth);
  const ready = useLoad(getReadiness);
  const catalog = useLoad(listSimulators);
  const { theme, setTheme } = useTheme();
  const [raw, setRaw] = React.useState(false);

  const refresh = () => { health.reload(); ready.reload(); catalog.reload(); };
  const busy = health.loading || ready.loading || catalog.loading;
  const healthStatus = String((health.data as any)?.status || '');
  const readyEntries = Object.entries(ready.data || {});

  return (
    <div className="page max-w-[1100px] space-y-8">
      <PageHeader
        title="Settings"
        description="The simulator owns its own storage. The Nexus AI platform reads these systems over HTTP only."
        actions={<Button variant="outline" size="sm" onClick={refresh} disabled={busy}><Icon name="refresh" className={cn(busy && 'animate-spin')} /> Refresh</Button>}
      />

      <section className="space-y-3">
        <SectionHeader title="Service" />
        <div className="grid gap-x-10 gap-y-2 border-y border-border py-4 md:grid-cols-2">
          <KeyValues
            items={[
              { label: 'Health', value: health.error ? <StatusPill tone="danger">Not answering</StatusPill> : health.data ? <StatusPill status={healthStatus || 'ok'}>{healthStatus === 'ok' ? 'Healthy' : healthStatus || 'Answering'}</StatusPill> : '…' },
              { label: 'Version', value: text((health.data as any)?.version), mono: true },
            ]}
          />
          <KeyValues
            items={ready.error
              ? [{ label: 'Readiness', value: <span className="text-muted-foreground">Not reported by this server</span> }]
              : readyEntries.length
                ? readyEntries.slice(0, 6).map(([k, v]) => ({ label: k.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()), value: typeof v === 'boolean' ? <StatusPill status={String(v)}>{v ? 'Yes' : 'No'}</StatusPill> : text(v) }))
                : [{ label: 'Readiness', value: '…' }]}
          />
        </div>
        {health.error && <InlineError onRetry={health.reload}>{health.error}</InlineError>}
      </section>

      <section className="space-y-3">
        <SectionHeader title="Storage by system" description="Where each system keeps its data dump and files." />
        {catalog.error && <InlineError onRetry={catalog.reload}>{catalog.error}</InlineError>}
        <TableShell>
          <table className="w-full text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">System</th>
                <th className="px-4 py-2.5 text-left font-medium">Schema</th>
                <th className="hidden px-4 py-2.5 text-left font-medium lg:table-cell">Storage bucket</th>
                <th className="hidden px-4 py-2.5 text-left font-medium md:table-cell">Data folder</th>
                <th className="px-4 py-2.5 text-left font-medium">Last loaded</th>
              </tr>
            </thead>
            <tbody>
              {(catalog.data || []).map(s => {
                const sim = simByService(s.service);
                return (
                  <tr key={s.service} className="border-b border-border last:border-b-0">
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <span className="inline-flex items-center gap-2.5 font-medium text-foreground"><SystemLogo system={sim?.logo || s.service} size="sm" />{sim?.name || s.service}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{s.schema || '—'}</td>
                    <td className="hidden break-all px-4 py-2.5 font-mono text-xs text-muted-foreground lg:table-cell">{s.bucket || <span className="font-sans text-sm text-subtle-foreground">Not configured</span>}</td>
                    <td className="hidden px-4 py-2.5 font-mono text-xs text-muted-foreground md:table-cell">{s.table_data_prefix || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">{dateTime(s.last_loaded)}</td>
                  </tr>
                );
              })}
              {catalog.loading && !catalog.data && Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-border last:border-b-0"><td colSpan={5} className="px-4 py-2.5"><div className="shimmer h-5 rounded bg-surface-2" /></td></tr>
              ))}
            </tbody>
          </table>
        </TableShell>
      </section>

      <section className="space-y-3">
        <SectionHeader title="Appearance" />
        <div role="radiogroup" aria-label="Theme" className="inline-flex gap-1 rounded-lg bg-surface-2 p-1">
          {(['dark', 'light'] as const).map(t => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={theme === t}
              onClick={() => setTheme(t)}
              className={cn('flex h-8 items-center gap-2 rounded-md px-3 text-sm transition-colors', theme === t ? 'bg-card font-medium text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground')}
            >
              <Icon name={t === 'dark' ? 'moon' : 'sun'} /> {t === 'dark' ? 'Dark' : 'Light'}
            </button>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="Raw service answers"
          description="For support: exactly what the service returned."
          actions={<Button variant="ghost" size="sm" onClick={() => setRaw(r => !r)} aria-expanded={raw}>{raw ? 'Hide' : 'Show'} <Icon name={raw ? 'chevron-up' : 'chevron-down'} /></Button>}
        />
        {raw && (
          <div className="space-y-4">
            {[['Health', health.data ?? { error: health.error }], ['Readiness', ready.data ?? { error: ready.error }], ['Catalog', catalog.data ?? { error: catalog.error }]].map(([label, value]) => (
              <div key={label as string}>
                <h3 className="mb-1.5 text-sm font-medium text-foreground">{label as string}</h3>
                <CodeBlock maxHeight={260}>{JSON.stringify(value, null, 2)}</CodeBlock>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
