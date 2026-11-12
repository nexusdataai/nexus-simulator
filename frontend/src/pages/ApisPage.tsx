import * as React from 'react';
import { toast } from 'sonner';
import { cn } from '@/core/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CodeBlock, DetailSheet, Field, InlineError, SearchInput, StatusPill, TableShell, Toolbar, ToolbarSpacer } from '@/components/ds/kit';
import { PageHeader } from '@/components/ds/primitives';
import { Icon } from '@/components/ds/Icon';
import { SystemLogo } from '@/components/ds/SystemLogo';
import { confirmDialog } from '@/components/ds/confirm';
import { MethodTag } from '@/components/sim/BackbonePanel';
import { useLoad } from '@/hooks/useLoad';
import { errorText, num } from '@/core/format';
import { listVendorApis, sendRaw, vendorApiSample, vendorBatch, type VendorApi, type VendorMethod } from '@/services/api';

const SYSTEMS = [
  { id: 'sfdc', label: 'Salesforce', logo: 'salesforce', style: 'sObject REST' },
  { id: 'oracle', label: 'Oracle ERP', logo: 'oracle', style: 'Fusion REST' },
  { id: 'sap', label: 'SAP S/4HANA', logo: 'sap', style: 'OData' },
];
const METHODS = ['GET', 'POST', 'PATCH', 'DELETE'];
const STEP = 150;
const selectCls = 'h-8 rounded-md border border-border-strong bg-card px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const checkCls = 'h-4 w-4 rounded border-border-strong accent-[hsl(var(--primary))]';

const fillId = (path: string, id: string) => path.replace("('{id}')", `('${id}')`).replace('{id}', encodeURIComponent(id));
const pretty = (text: string) => { try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; } };

interface Outcome { status: number; statusText: string; ok: boolean; text: string; ms: number }

function OutcomeView({ outcome }: { outcome: Outcome }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-sm">
        <StatusPill tone={outcome.ok ? 'success' : 'danger'}>{outcome.status} {outcome.statusText}</StatusPill>
        <span className="num text-xs text-muted-foreground">{num(outcome.ms)} ms</span>
      </div>
      <CodeBlock maxHeight={360} wrap>{pretty(outcome.text) || '(empty answer)'}</CodeBlock>
    </div>
  );
}

/* ------------------------------------------------------------ test bench */

function TestBench({ api, onClose, onChanged }: { api: VendorApi; onClose: () => void; onChanged: () => void }) {
  const [method, setMethod] = React.useState<VendorMethod>(() => api.methods.find(m => m.kind === 'list') || api.methods[0]);
  const [sampleId, setSampleId] = React.useState('ID');
  const [path, setPath] = React.useState(() => fillId((api.methods.find(m => m.kind === 'list') || api.methods[0]).path, 'ID'));
  const [body, setBody] = React.useState('{}');
  const [sending, setSending] = React.useState(false);
  const [outcome, setOutcome] = React.useState<Outcome | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  // Fill the address and the body with a real row so a request works first time.
  React.useEffect(() => {
    let alive = true;
    vendorApiSample(api.id).then(row => {
      if (!alive) return;
      const id = String(row[api.pk || ''] ?? Object.values(row)[0] ?? '') || 'ID';
      setSampleId(id);
      setBody(JSON.stringify(row, null, 2));
      setPath(p => p.replace(/\bID\b/, encodeURIComponent(id)));
    }).catch(() => { /* an empty body is fine */ });
    return () => { alive = false; };
  }, [api]);

  const pick = (m: VendorMethod) => { setMethod(m); setPath(fillId(m.path, sampleId)); setOutcome(null); setError(null); };
  const writes = !['GET', 'HEAD'].includes(method.method);
  const hasBody = !['GET', 'HEAD', 'DELETE'].includes(method.method);

  const send = async () => {
    if (method.method === 'DELETE') {
      const ok = await confirmDialog({ title: 'Send this DELETE request?', description: `It removes the record at ${path} from the simulator data.`, confirmLabel: 'Send DELETE', destructive: true });
      if (!ok) return;
    }
    setSending(true); setError(null);
    try {
      setOutcome(await sendRaw(path, method.method, body));
      if (writes) onChanged();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <DetailSheet
      open
      wide
      onOpenChange={o => { if (!o) onClose(); }}
      title={api.name}
      description={<><span className="font-mono text-xs">{api.schema}.{api.table}</span> · {num(api.rowCount)} rows{api.pk ? <> · key <span className="font-mono text-xs">{api.pk}</span></> : null}</>}
      meta={api.docsUrl ? (
        <a href={api.docsUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline dark:text-brand-hi">
          Vendor documentation <Icon name="external-link" className="h-3 w-3" />
        </a>
      ) : undefined}
      footer={
        <>
          {writes && <span className="mr-auto text-xs text-muted-foreground">This request changes simulator data.</span>}
          <Button size="sm" onClick={send} disabled={sending || !path.trim()}>
            <Icon name={sending ? 'spinner' : 'send'} className={cn(sending && 'animate-spin')} /> Send request
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div>
          <div className="mb-1.5 text-xs font-medium text-muted-foreground">Operation</div>
          <ul className="border-y border-border">
            {api.methods.map(m => {
              const on = m === method;
              return (
                <li key={`${m.method}-${m.kind}`} className="border-b border-border last:border-b-0">
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => pick(m)}
                    className={cn('relative flex w-full items-baseline gap-3 px-3 py-2 text-left text-sm transition-colors', on ? 'bg-accent/70' : 'hover:bg-surface-2/70')}
                  >
                    {on && <span className="absolute inset-y-0 left-0 w-0.5 bg-primary" aria-hidden="true" />}
                    <span className="w-14 shrink-0"><MethodTag method={m.method} /></span>
                    <span className="w-20 shrink-0 capitalize text-foreground">{m.kind}</span>
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">{m.path}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <Field label="Address" htmlFor="api-path">
          <Input id="api-path" value={path} onChange={e => setPath(e.target.value)} spellCheck={false} className="font-mono text-xs" />
        </Field>

        {hasBody && (
          <Field label="Body (JSON)" htmlFor="api-body" hint="Filled with a real row from this table. Edit before sending.">
            <textarea
              id="api-body"
              value={body}
              onChange={e => setBody(e.target.value)}
              spellCheck={false}
              className="scroll-thin min-h-[180px] w-full rounded-md border border-border-strong bg-card px-3 py-2 font-mono text-xs leading-5 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>
        )}

        {error && <InlineError>{error}</InlineError>}
        {outcome && (
          <div>
            <div className="mb-1.5 text-xs font-medium text-muted-foreground">Answer</div>
            <OutcomeView outcome={outcome} />
          </div>
        )}
      </div>
    </DetailSheet>
  );
}

/* ------------------------------------------------------------------ page */

export default function ApisPage() {
  const [system, setSystem] = React.useState('sfdc');
  const { data, error, loading, reload } = useLoad(() => listVendorApis(system), [system]);
  const [q, setQ] = React.useState('');
  const [method, setMethod] = React.useState('');
  const [onlyData, setOnlyData] = React.useState(true);
  const [picked, setPicked] = React.useState<Set<string>>(new Set());
  const [open, setOpen] = React.useState<VendorApi | null>(null);
  const [batching, setBatching] = React.useState<string | null>(null);
  const [batch, setBatch] = React.useState<{ title: string; outcome: Outcome } | null>(null);
  const [limit, setLimit] = React.useState(STEP);

  React.useEffect(() => { setPicked(new Set()); setBatch(null); }, [system]);
  React.useEffect(() => { setLimit(STEP); }, [system, q, method, onlyData]);

  const items = data || [];
  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter(a => {
      if (onlyData && !a.rowCount) return false;
      if (method && !a.methods.some(m => m.method === method)) return false;
      return !needle || `${a.name} ${a.table} ${a.id} ${a.methods.map(m => m.path).join(' ')}`.toLowerCase().includes(needle);
    });
  }, [items, q, method, onlyData]);
  const shown = filtered.slice(0, limit);
  const sys = SYSTEMS.find(s => s.id === system)!;

  const toggle = (id: string, on: boolean) => setPicked(prev => {
    const next = new Set(prev);
    if (on) next.add(id); else next.delete(id);
    return next;
  });
  const allShownPicked = shown.length > 0 && shown.every(a => picked.has(a.id));

  const runBatch = async (mode: 'operations' | 'canary_writes') => {
    if (mode === 'canary_writes') {
      const ok = await confirmDialog({
        title: `Test the write operations of ${sys.label}?`,
        description: 'This sends a small test write to up to 50 objects that have data. The writes are saved in the simulator data on the server.',
        confirmLabel: 'Run write test',
      });
      if (!ok) return;
    }
    const body = mode === 'canary_writes'
      ? { system, mode, limit: 50 }
      : {
          system, mode,
          operations: items.filter(a => picked.has(a.id)).map(a => {
            const m = a.methods.find(x => x.kind === 'list') || a.methods[0];
            return { method: m.method, path: m.path };
          }),
        };
    setBatching(mode);
    try {
      const outcome = await vendorBatch(body);
      setBatch({ title: mode === 'canary_writes' ? 'Write test result' : `Result of ${picked.size} selected ${picked.size === 1 ? 'call' : 'calls'}`, outcome });
      if (!outcome.ok) toast.error(`The batch answered ${outcome.status}.`);
      reload();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBatching(null);
    }
  };

  return (
    <div className="page space-y-5">
      <PageHeader
        title="Vendor APIs"
        description="The simulator answers in each vendor's own API style, so connectors can be tested exactly as they would call the real system. Write calls change the simulator data."
      />

      {/* System switch */}
      <div role="tablist" aria-label="Vendor" className="flex gap-6 border-b border-border">
        {SYSTEMS.map(s => {
          const on = s.id === system;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setSystem(s.id)}
              className={cn('relative -mb-px flex h-11 items-center gap-2.5 text-sm transition-colors', on ? 'font-medium text-foreground' : 'text-muted-foreground hover:text-foreground')}
            >
              <SystemLogo system={s.logo} size="sm" />
              {s.label}
              <span className="hidden text-xs text-subtle-foreground sm:inline">{s.style}</span>
              <span className={cn('absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-primary transition-transform duration-300 ease-brand-out', on ? 'scale-x-100' : 'scale-x-0')} />
            </button>
          );
        })}
      </div>

      <Toolbar>
        <SearchInput value={q} onChange={setQ} placeholder="Search object or path" className="sm:w-72" />
        <select value={method} onChange={e => setMethod(e.target.value)} aria-label="Method" className={selectCls}>
          <option value="">All methods</option>
          {METHODS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <label className="flex h-8 cursor-pointer select-none items-center gap-2 rounded-md px-2 text-sm text-muted-foreground hover:text-foreground">
          <input type="checkbox" className={checkCls} checked={onlyData} onChange={e => setOnlyData(e.target.checked)} /> Only objects with rows
        </label>
        <ToolbarSpacer />
        <span className="num text-xs text-muted-foreground">{loading && !data ? 'Loading…' : `${num(filtered.length)} of ${num(items.length)} objects`}</span>
        <Button variant="outline" size="sm" disabled={batching !== null || picked.size === 0} onClick={() => runBatch('operations')}>
          <Icon name={batching === 'operations' ? 'spinner' : 'play'} className={cn(batching === 'operations' && 'animate-spin')} /> Run selected{picked.size ? ` (${picked.size})` : ''}
        </Button>
        <Button variant="outline" size="sm" disabled={batching !== null} onClick={() => runBatch('canary_writes')}>
          <Icon name={batching === 'canary_writes' ? 'spinner' : 'shield-check'} className={cn(batching === 'canary_writes' && 'animate-spin')} /> Test all writes
        </Button>
      </Toolbar>

      {error && <InlineError onRetry={reload}>Could not load the API catalog. {error}</InlineError>}

      {batch && (
        <section aria-label={batch.title} className="rounded-xl border border-border bg-card p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h2 className="text-md font-medium text-foreground">{batch.title}</h2>
            <Button variant="ghost" size="icon-sm" onClick={() => setBatch(null)} aria-label="Hide result"><Icon name="close" /></Button>
          </div>
          <OutcomeView outcome={batch.outcome} />
        </section>
      )}

      <TableShell>
        <table className="w-full text-sm">
          <thead className="border-b border-border text-xs text-muted-foreground">
            <tr>
              <th className="w-10 px-4 py-2.5">
                <input
                  type="checkbox"
                  className={checkCls}
                  aria-label="Select all shown"
                  checked={allShownPicked}
                  onChange={e => setPicked(prev => {
                    const next = new Set(prev);
                    shown.forEach(a => { if (e.target.checked) next.add(a.id); else next.delete(a.id); });
                    return next;
                  })}
                />
              </th>
              <th className="px-4 py-2.5 text-left font-medium">Object</th>
              <th className="hidden px-4 py-2.5 text-left font-medium lg:table-cell">Path</th>
              <th className="px-4 py-2.5 text-left font-medium">Methods</th>
              <th className="px-4 py-2.5 text-right font-medium">Rows</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className="border-b border-border last:border-b-0"><td colSpan={5} className="px-4 py-2.5"><div className="shimmer h-5 rounded bg-surface-2" /></td></tr>
            ))}
            {shown.map(a => {
              const list = a.methods.find(m => m.kind === 'list') || a.methods[0];
              return (
                <tr
                  key={a.id}
                  tabIndex={0}
                  onClick={() => setOpen(a)}
                  onKeyDown={e => { if (e.key === 'Enter') setOpen(a); }}
                  className="group cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-surface-2/70 focus-visible:bg-surface-2/70 focus-visible:outline-none"
                >
                  <td className="px-4 py-2.5" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" className={checkCls} aria-label={`Select ${a.name}`} checked={picked.has(a.id)} onChange={e => toggle(a.id, e.target.checked)} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-foreground group-hover:text-primary dark:group-hover:text-brand-hi">{a.name}</div>
                    {a.table !== a.name && <div className="font-mono text-xs text-muted-foreground">{a.table}</div>}
                  </td>
                  <td className="hidden max-w-[420px] truncate px-4 py-2.5 font-mono text-xs text-muted-foreground lg:table-cell">{list?.path}</td>
                  <td className="px-4 py-2.5">
                    <span className="flex gap-x-2.5 whitespace-nowrap">{[...new Set(a.methods.map(m => m.method))].map(m => <MethodTag key={m} method={m} />)}</span>
                  </td>
                  <td className={cn('num px-4 py-2.5 text-right', a.rowCount ? 'text-foreground' : 'text-subtle-foreground')}>{num(a.rowCount)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && data && filtered.length === 0 && <p className="px-4 py-10 text-center text-sm text-muted-foreground">No object matches these filters.</p>}
      </TableShell>

      {filtered.length > limit && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setLimit(limit + STEP)}>Show {Math.min(STEP, filtered.length - limit)} more</Button>
          <Button variant="ghost" size="sm" onClick={() => setLimit(filtered.length)}>Show all {num(filtered.length)}</Button>
        </div>
      )}

      {open && <TestBench key={open.id} api={open} onClose={() => setOpen(null)} onChanged={reload} />}
    </div>
  );
}
