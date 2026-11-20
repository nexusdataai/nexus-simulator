import * as React from 'react';
import { cn } from '@/core/utils';
import { Chips, InlineError, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { PageHeader } from '@/components/ds/primitives';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { simByService } from '@/config/simulators';
import { num } from '@/core/format';
import { getBillingOverview, systemApi, type BillingFeed, type BillingOverview } from '@/services/api';

type Layer = 'all' | 'BSS' | 'OSS' | 'NSS';

const th = 'px-3 py-2.5 text-left text-xs font-medium text-muted-foreground';
const td = 'px-3 py-2.5 align-top text-sm text-foreground';

function layerBadge(layer: string) {
  const l = layer.toUpperCase();
  const cls =
    l === 'BSS' ? 'border-primary/40 bg-primary/10 text-primary'
      : l === 'NSS' ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300'
        : l === 'OSS' ? 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200'
          : 'border-border bg-surface-2 text-muted-foreground';
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {l}
    </span>
  );
}

function feedRows(feeds: BillingFeed[], layer: Layer) {
  return layer === 'all' ? feeds : feeds.filter(f => String(f.layer).toUpperCase() === layer);
}

/** Cross-layer billing: inbound feeds + simulated BSS/NSS/OSS tables. */
export default function BillingPage() {
  const [data, setData] = React.useState<BillingOverview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [layer, setLayer] = React.useState<Layer>('all');
  const [openTable, setOpenTable] = React.useState<TableListRow | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  const load = React.useCallback(() => {
    setLoading(true);
    setError(null);
    getBillingOverview()
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Could not load billing data.'))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => { load(); }, [load, attempt]);

  const feeds = React.useMemo(
    () => feedRows(data?.feeds || [], layer),
    [data?.feeds, layer],
  );

  const tables = React.useMemo(() => {
    const svcLayer: Record<string, Layer> = { bss: 'BSS', nss: 'NSS', oss: 'OSS' };
    const list = (data?.tables || []).map((t): TableListRow => ({
      service: t.service,
      schemaName: t.schemaName ?? t.schema ?? '',
      tableName: t.tableName ?? t.table ?? '',
      columnCount: t.columnCount,
      rowCount: t.rowCount ?? t.rows,
      applications: t.applications,
      billing_target: t.billing_target,
      system_key: t.system_key,
    }));
    if (layer === 'all') return list;
    return list.filter(t => svcLayer[t.service || ''] === layer);
  }, [data?.tables, layer]);

  const openSim = simByService(openTable?.service);
  const source = React.useMemo(() => (openSim ? systemApi(openSim.apiPath) : undefined), [openSim]);

  const totals = data?.totals;
  const byLayer = totals?.by_layer?.tables;

  return (
    <div className="page space-y-6">
      <PageHeader
        title="Billing"
        description="Inbound billing feeds and simulated data across BSS, OSS, and NSS — aligned with the Telco atlas and Kenan intake model."
        actions={
          <a
            href="/telco-atlas/kenan.html"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-primary underline-offset-4 hover:underline dark:text-brand-hi"
          >
            Atlas reference
          </a>
        }
      />

      {error && <InlineError onRetry={() => setAttempt(a => a + 1)}>{error}</InlineError>}

      <Toolbar className="flex-wrap gap-3">
        <Chips<Layer>
          label="Layer"
          value={layer}
          onChange={setLayer}
          options={[
            { value: 'all', label: 'All layers', count: totals?.feeds },
            { value: 'BSS', label: 'BSS', count: byLayer?.BSS },
            { value: 'OSS', label: 'OSS', count: byLayer?.OSS },
            { value: 'NSS', label: 'NSS', count: byLayer?.NSS },
          ]}
        />
        <ToolbarSpacer />
        {totals && (
          <span className="num text-xs text-muted-foreground" aria-live="polite">
            {num(totals.tables)} billing tables · {num(totals.rows)} rows
          </span>
        )}
      </Toolbar>

      <section className="space-y-3" aria-label="Inbound feeds">
        <h2 className="text-sm font-medium text-foreground">Inbound feeds</h2>
        <TableShell className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-sm">
            <thead className="border-b border-border bg-surface-2/50">
              <tr>
                <th className={th}>Feed</th>
                <th className={th}>Layer</th>
                <th className={th}>Comes from</th>
                <th className={th}>Key data</th>
                <th className={th}>Format</th>
                <th className={th}>Delivery</th>
                <th className={th}>Intake</th>
                <th className={th}>Lands in</th>
                <th className={th}>TMF / SID</th>
                <th className={cn(th, 'text-right')}>Simulated rows</th>
              </tr>
            </thead>
            <tbody>
              {loading && !feeds.length && (
                <tr><td colSpan={10} className="px-3 py-8 text-center text-muted-foreground">Loading feeds…</td></tr>
              )}
              {feeds.map(f => (
                <tr key={f.id} className="border-b border-border last:border-b-0 hover:bg-surface-2/40">
                  <td className={cn(td, 'min-w-[140px] font-medium')}>{f.name}</td>
                  <td className={td}>{layerBadge(f.layer)}</td>
                  <td className={cn(td, 'max-w-[200px] text-muted-foreground')}>{f.source_lineage}</td>
                  <td className={cn(td, 'max-w-[180px] text-muted-foreground')}>{f.key_data}</td>
                  <td className={cn(td, 'max-w-[140px] text-xs text-muted-foreground')}>{f.format}</td>
                  <td className={td}>
                    <div className="flex flex-wrap gap-1">
                      {(f.delivery || []).map(d => (
                        <span key={d} className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">{d}</span>
                      ))}
                    </div>
                  </td>
                  <td className={cn(td, 'text-xs text-muted-foreground')}>{f.intake}</td>
                  <td className={cn(td, 'text-xs text-muted-foreground')}>{f.lands_in}</td>
                  <td className={cn(td, 'text-xs text-muted-foreground')}>{f.tmf_sid}</td>
                  <td className={cn(td, 'num text-right')}>
                    {f.table_count ? (
                      <span title={`${f.table_count} linked table(s)`}>{num(f.simulated_rows || 0)}</span>
                    ) : (
                      <span className="text-subtle-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !feeds.length && (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">No feeds for this layer.</p>
          )}
        </TableShell>
      </section>

      <section className="space-y-3" aria-label="Simulated billing tables">
        <h2 className="text-sm font-medium text-foreground">Simulated billing data</h2>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          {(['bss', 'nss', 'oss'] as const).map(s => {
            const sim = simByService(s);
            const n = tables.filter(t => t.service === s).length;
            const rows = tables.filter(t => t.service === s).reduce((a, t) => a + (t.rowCount || 0), 0);
            return (
              <span key={s} className="inline-flex items-center gap-2">
                <SystemLogo system={sim?.logo || s} size="sm" />
                {sim?.short}: {num(n)} tables · {num(rows)} rows
              </span>
            );
          })}
        </div>
        <TableList
          rows={tables}
          loading={loading}
          showSystem
          onOpen={setOpenTable}
          emptyText="No billing-tagged tables yet. Seed BSS, NSS, and OSS (billing profile) or generate billing families from each backbone."
        />
      </section>

      <RowsSheet
        open={!!openTable}
        onOpenChange={o => { if (!o) setOpenTable(null); }}
        schema={openTable?.schemaName}
        table={openTable?.tableName}
        context={openSim?.name}
        source={source}
      />
    </div>
  );
}