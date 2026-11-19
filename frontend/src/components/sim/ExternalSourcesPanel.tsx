/**
 * External sources: Google Drive documents, social listening feed and uploads.
 * Mapped ontology tables are produced downstream — not listed here.
 */
import * as React from 'react';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { InlineError, SearchInput, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { Icon, type IconName } from '@/components/ds/Icon';
import { AnimatedNumber } from '@/components/ds/AnimatedNumber';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { confirmDialog } from '@/components/ds/confirm';
import { PreviewModal, type PreviewTarget } from '@/components/sim/PreviewModal';
import { SystemHeader } from '@/components/sim/SystemHeader';
import { Chips } from '@/components/ds/kit';
import type { SimAction, SimulatorDef } from '@/config/simulators';
import { useLoad } from '@/hooks/useLoad';
import { dateTime, errorText, num } from '@/core/format';
import type { ExternalArtifactFile, ExternalSourceDef, SimStatus, SocialFeedItem, SystemApi } from '@/services/api';

const ACTIONS: Record<SimAction, { label: string; icon: IconName; title: (n: string) => string; description: string; confirm: string; done: string; destructive?: boolean }> = {
  load: {
    label: 'Load data', icon: 'download',
    title: n => `Load ${n} data?`,
    description: 'This loads the saved data dump into the simulator on the server.',
    confirm: 'Load data', done: 'Data loaded.',
  },
  seed: {
    label: 'Seed data', icon: 'sparkles',
    title: n => `Seed ${n} with fresh data?`,
    description: 'This generates Google Drive files, social feed items and upload scans.',
    confirm: 'Seed data', done: 'Fresh data seeded.',
  },
  reset: {
    label: 'Reset', icon: 'trash',
    title: n => `Reset ${n}?`,
    description: 'This clears external source artifacts in memory. Seed or load again to repopulate.',
    confirm: 'Reset system', done: 'System reset.', destructive: true,
  },
};

type SourceTab = 'google_drive' | 'social_listening' | 'file_uploads';

const TAB_LOGO: Record<SourceTab, string> = {
  google_drive: 'google_drive',
  social_listening: 'social',
  file_uploads: 'files',
};

const KIND_LABEL: Record<string, string> = {
  contract: 'Contract',
  report: 'Sustainability report',
  document: 'Drive document',
  invoice: 'Invoice scan',
  lab_report: 'Lab report',
};

function ExternalFacts({ status }: { status?: SimStatus | null }) {
  const counts = status?.source_counts;
  const stats = [
    { label: 'Drive files', value: counts?.google_drive ?? status?.file_count },
    { label: 'Social feed', value: counts?.social_listening ?? status?.social_item_count },
    { label: 'Uploads', value: counts?.file_uploads ?? 0 },
  ];
  const facts = [
    { label: 'Schema (mapping)', value: status?.schema || '—', mono: true },
    { label: 'Storage bucket', value: status?.bucket || 'Not configured', mono: !!status?.bucket },
    { label: 'File data folder', value: status?.files_data_prefix || '—', mono: true },
    { label: 'Last loaded', value: status?.last_loaded ? dateTime(status.last_loaded) : '—' },
  ];
  return (
    <div className="grid gap-x-10 gap-y-5 border-y border-border py-5 xl:grid-cols-[minmax(0,4fr)_minmax(0,7fr)]">
      <dl className="grid grid-cols-3 content-start gap-x-6 gap-y-5">
        {stats.map(st => (
          <div key={st.label} className="min-w-0">
            <dt className="text-sm text-muted-foreground">{st.label}</dt>
            <dd className="mt-1 text-2xl font-medium tracking-tight text-foreground">
              <AnimatedNumber value={st.value} className="num" />
            </dd>
          </div>
        ))}
      </dl>
      <dl className="grid content-start gap-x-8 gap-y-4 sm:grid-cols-2">
        {facts.map(f => (
          <div key={f.label} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{f.label}</dt>
            <dd className={cn('mt-0.5 break-all text-sm text-foreground', f.mono && 'font-mono text-xs leading-5')}>{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ExternalSourcesPanel({ sim, api }: { sim: SimulatorDef; api: SystemApi }) {
  const status = useLoad(api.status, [api]);
  const sources = useLoad(api.sources!, [api, status.data?.loaded]);
  const [tab, setTab] = React.useState<SourceTab>('google_drive');
  const [q, setQ] = React.useState('');
  const files = useLoad(() => api.files!(tab === 'social_listening' ? undefined : tab), [api, tab, status.data?.loaded]);
  const social = useLoad(() => api.social!(200), [api, status.data?.loaded]);
  const [busy, setBusy] = React.useState<SimAction | null>(null);
  const [preview, setPreview] = React.useState<PreviewTarget | null>(null);
  const [socialPreview, setSocialPreview] = React.useState<SocialFeedItem | null>(null);

  const refresh = () => {
    status.reload();
    sources.reload();
    files.reload();
    social.reload();
  };

  const act = async (kind: SimAction) => {
    const a = ACTIONS[kind];
    const ok = await confirmDialog({ title: a.title(sim.name), description: a.description, confirmLabel: a.confirm, destructive: a.destructive });
    if (!ok) return;
    setBusy(kind);
    try {
      const r = await api[kind]();
      toast.success(typeof r?.message === 'string' ? r.message : `${sim.name}: ${a.done}`);
      refresh();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  const sourceMeta = React.useMemo(() => new Map((sources.data || []).map(s => [s.id, s])), [sources.data]);

  const fileRows = (files.data || []).filter(f => {
    if (tab !== 'social_listening' && f.source_id !== tab) return false;
    const hay = `${f.name} ${f.path} ${f.kind}`.toLowerCase();
    return !q.trim() || hay.includes(q.trim().toLowerCase());
  });

  const socialRows = (social.data || []).filter(item => {
    const hay = `${item.title} ${item.summary} ${item.kind}`.toLowerCase();
    return !q.trim() || hay.includes(q.trim().toLowerCase());
  });

  const tabCounts: Record<SourceTab, number> = {
    google_drive: sourceMeta.get('google_drive')?.file_count ?? 0,
    social_listening: sourceMeta.get('social_listening')?.feed_count ?? social.data?.length ?? 0,
    file_uploads: sourceMeta.get('file_uploads')?.file_count ?? 0,
  };

  const th = 'px-3 py-2 text-left text-xs font-medium text-muted-foreground';
  const td = 'px-3 py-2 align-top text-sm';

  return (
    <div className="space-y-6">
      <SystemHeader
        sim={sim}
        status={status.data}
        loading={status.loading}
        note="Files and feeds are simulated here; ontology mapping builds the final warehouse tables."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={refresh} disabled={status.loading || files.loading}>
              <Icon name="refresh" className={cn((status.loading || files.loading) && 'animate-spin')} /> Refresh
            </Button>
            {sim.actions.map(kind => {
              const a = ACTIONS[kind];
              const working = busy === kind;
              return (
                <Button
                  key={kind}
                  size="sm"
                  variant={kind === 'reset' ? 'outline' : 'default'}
                  disabled={busy !== null}
                  onClick={() => act(kind)}
                  className={cn(kind === 'reset' && 'text-destructive hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive')}
                >
                  <Icon name={working ? 'spinner' : a.icon} className={cn(working && 'animate-spin')} /> {a.label}
                </Button>
              );
            })}
          </>
        }
      />

      {status.error && <InlineError onRetry={status.reload}>Could not load the status. {status.error}</InlineError>}
      <ExternalFacts status={status.data} />

      <section aria-label="External sources" className="space-y-3">
        <Toolbar>
          <Chips<SourceTab>
            label="Source"
            value={tab}
            onChange={v => { setTab(v); setQ(''); }}
            options={([
              { id: 'google_drive', label: 'Google Drive' },
              { id: 'social_listening', label: 'Social listening' },
              { id: 'file_uploads', label: 'File uploads' },
            ] as const).map(o => ({
              value: o.id,
              label: o.label,
              count: tabCounts[o.id],
            }))}
          />
          <ToolbarSpacer />
          <SearchInput value={q} onChange={setQ} placeholder={tab === 'social_listening' ? 'Search feed' : 'Search files'} />
        </Toolbar>

        {tab !== 'social_listening' && files.error && <InlineError onRetry={files.reload}>{files.error}</InlineError>}
        {tab === 'social_listening' && social.error && <InlineError onRetry={social.reload}>{social.error}</InlineError>}

        {tab !== 'social_listening' && (
          <TableShell>
            <table className="w-full text-sm">
              <thead className="border-b border-border">
                <tr>
                  <th className={th}>File</th>
                  <th className={cn(th, 'hidden sm:table-cell')}>Kind</th>
                  <th className={cn(th, 'hidden md:table-cell')}>Path</th>
                  <th className={th}>Size</th>
                </tr>
              </thead>
              <tbody>
                {fileRows.map(f => (
                  <tr key={f.path} className="border-b border-border last:border-b-0 hover:bg-surface-2/70">
                    <td className={td}>
                      <div className="flex items-center gap-2">
                        <SystemLogo system={TAB_LOGO[tab]} size="sm" />
                        <button
                          type="button"
                          onClick={() =>
                            setPreview({
                              title: f.name,
                              subtitle: f.path,
                              name: f.name,
                              load: () => api.filePreview!(f.path),
                            })
                          }
                          className="break-all text-left font-medium text-foreground hover:text-primary dark:hover:text-brand-hi"
                        >
                          {f.name}
                        </button>
                      </div>
                    </td>
                    <td className={cn(td, 'hidden text-muted-foreground sm:table-cell')}>{KIND_LABEL[f.kind || ''] || f.kind || '—'}</td>
                    <td className={cn(td, 'hidden break-all font-mono text-xs text-muted-foreground md:table-cell')}>{f.path}</td>
                    <td className={cn(td, 'num whitespace-nowrap text-muted-foreground')}>
                      {f.size_kb != null ? `${num(f.size_kb)} KB` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!files.loading && !fileRows.length && (
              <p className="px-4 py-10 text-center text-sm text-muted-foreground">
                No files for {sourceMeta.get(tab)?.name || tab}. Seed data or load the supply-chain dump.
              </p>
            )}
          </TableShell>
        )}

        {tab === 'social_listening' && (
          <div className="divide-y divide-border rounded-lg border border-border bg-card">
            {!social.loading && !socialRows.length && (
              <p className="px-4 py-10 text-center text-sm text-muted-foreground">No social feed items yet. Seed data to generate signals and sentiment.</p>
            )}
            {socialRows.map(item => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSocialPreview(item)}
                className="flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2/70"
              >
                <SystemLogo system="social" size="sm" className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-medium text-foreground">{item.title}</span>
                    {item.timestamp && <span className="text-xs text-muted-foreground">{item.timestamp}</span>}
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">{item.summary}</p>
                </div>
                <Icon name="chevron-right" className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </div>
        )}
      </section>

      <PreviewModal target={preview} onClose={() => setPreview(null)} />

      {socialPreview && (
        <PreviewModal
          target={{
            title: socialPreview.title,
            subtitle: socialPreview.kind,
            load: async () => JSON.stringify(socialPreview.metadata || socialPreview, null, 2),
          }}
          onClose={() => setSocialPreview(null)}
        />
      )}
    </div>
  );
}