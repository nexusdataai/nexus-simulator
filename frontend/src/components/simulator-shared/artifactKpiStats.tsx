import type { SimulatorArtifactMeta } from './simulatorArtifactMeta';

export type KpiStat = { label: string; value: string | number; color: string };

export function artifactKpiStats(meta: SimulatorArtifactMeta): KpiStat[] {
  return [
    { label: 'Tables', value: meta.tableCount, color: 'text-blue-400' },
    { label: 'With Data', value: meta.tablesWithData, color: 'text-green-400' },
    { label: 'Total Rows', value: meta.totalRows.toLocaleString(), color: 'text-purple-400' },
    { label: 'Files', value: meta.fileCount, color: 'text-amber-400' },
    { label: 'APIs', value: meta.apiCount, color: 'text-cyan-400' },
    { label: 'Streams', value: meta.streamCount, color: 'text-pink-400' },
  ];
}

export function KpiStatGrid({ stats }: { stats: KpiStat[] }) {
  if (!stats.length) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="rounded-lg border bg-card p-4 flex flex-col items-center justify-center">
          <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          <p className="text-xs text-muted-foreground mt-1 text-center">{s.label}</p>
        </div>
      ))}
    </div>
  );
}
