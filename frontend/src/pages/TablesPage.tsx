import * as React from 'react';
import { Chips, InlineError } from '@/components/ds/kit';
import { PageHeader } from '@/components/ds/primitives';
import { TableList, type TableListRow } from '@/components/sim/TableList';
import { RowsSheet } from '@/components/sim/RowsSheet';
import { SIMULATORS, simByService } from '@/config/simulators';
import { num } from '@/core/format';
import { getSimulatorTables, systemApi, type CatalogTable } from '@/services/api';

/** Every table of every system in one searchable list. */
export default function TablesPage() {
  const [tables, setTables] = React.useState<CatalogTable[]>([]);
  const [pending, setPending] = React.useState(SIMULATORS.length);
  const [failed, setFailed] = React.useState<string[]>([]);
  const [system, setSystem] = React.useState('all');
  const [module, setModule] = React.useState<'all' | 'billing'>('all');
  const [openTable, setOpenTable] = React.useState<TableListRow | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  // Systems answer at different speeds, so the list fills as each one arrives.
  React.useEffect(() => {
    let alive = true;
    setTables([]); setFailed([]); setPending(SIMULATORS.length);
    SIMULATORS.forEach(sim => {
      getSimulatorTables(sim.service)
        .then(t => { if (alive) setTables(prev => [...prev, ...t]); })
        .catch(() => { if (alive) setFailed(prev => [...prev, sim.name]); })
        .finally(() => { if (alive) setPending(p => p - 1); });
    });
    return () => { alive = false; };
  }, [attempt]);

  const counts = React.useMemo(() => {
    const m = new Map<string, number>();
    tables.forEach(t => { if (t.rowCount) m.set(t.service, (m.get(t.service) || 0) + 1); });
    return m;
  }, [tables]);

  const telecomServices = React.useMemo(() => new Set(['bss', 'nss', 'oss']), []);
  const billingCount = React.useMemo(
    () => tables.filter(t => telecomServices.has(t.service) && t.applications?.includes('billing')).length,
    [tables, telecomServices],
  );
  const rows = React.useMemo(() => {
    let list = system === 'all' ? tables : tables.filter(t => t.service === system);
    if (module === 'billing') {
      list = list.filter(t => t.applications?.includes('billing'));
    }
    return list;
  }, [tables, system, module]);
  const withData = tables.filter(t => t.rowCount).length;
  const openSim = simByService(openTable?.service);
  const source = React.useMemo(() => (openSim ? systemApi(openSim.apiPath) : undefined), [openSim]);

  return (
    <div className="page space-y-5">
      <PageHeader
        title="Tables"
        description={pending > 0
          ? `Reading the catalogs… ${SIMULATORS.length - pending} of ${SIMULATORS.length} systems`
          : `${num(tables.length)} tables across ${SIMULATORS.length} systems, ${num(withData)} of them with rows. Select a table to see its data.`}
      />

      {failed.length > 0 && (
        <InlineError onRetry={() => setAttempt(a => a + 1)}>Could not read the tables of {failed.join(', ')}.</InlineError>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start">
        <Chips
          label="System"
          value={system}
          onChange={setSystem}
          options={[
            { value: 'all', label: 'All systems', count: withData },
            ...SIMULATORS.map(s => ({ value: s.service, label: s.short, count: counts.get(s.service) || 0 })),
          ]}
        />
        {billingCount > 0 && (
          <Chips<'all' | 'billing'>
            label="Application"
            value={module}
            onChange={setModule}
            options={[
              { value: 'all', label: 'All data', count: tables.length },
              { value: 'billing', label: 'Billing', count: billingCount },
            ]}
          />
        )}
      </div>

      <TableList rows={rows} loading={pending > 0} showSystem={system === 'all'} onOpen={setOpenTable} />

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
