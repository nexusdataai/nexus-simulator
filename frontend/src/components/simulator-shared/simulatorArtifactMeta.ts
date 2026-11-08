import type { SimulatorStatus } from '@/services/sapSimulatorService';
import type { SFDCSimulatorStatus } from '@/services/sfdcSimulatorService';
import type { ExternalSimulatorStatus } from '@/services/externalSimulatorService';

type StatusLike = SimulatorStatus | SFDCSimulatorStatus | ExternalSimulatorStatus;

/** Normalized artifact + S3 layout fields for Simulator Status UI. */
export type SimulatorArtifactMeta = {
  enabled: boolean;
  loaded: boolean;
  bucket: string;
  tableDataPrefix: string;
  filesDataPrefix: string;
  schema?: string;
  tableCount: number;
  tablesWithData: number;
  totalRows: number;
  fileCount: number;
  apiCount: number;
  streamCount: number;
  dumpTimestamp?: string | null;
  lastLoaded?: string | null;
  dumpAvailable?: boolean;
  dumpTables?: number;
  dumpRows?: number;
  /** Telco backbone */
  backboneRunId?: string | null;
  backboneGeneratedAt?: string | null;
  vendorLabel?: string | null;
  backboneS3Base?: string;
};

export function artifactMetaFromStatus(status: StatusLike | null): SimulatorArtifactMeta | null {
  if (!status) return null;
  const prefix = status.table_data_prefix ?? status.prefix ?? '';
  const filesPrefix =
    status.files_data_prefix ?? (prefix ? `${prefix.replace(/\/$/, '')}/files` : '');
  return {
    enabled: status.enabled,
    loaded: status.loaded,
    bucket: status.bucket || '',
    tableDataPrefix: prefix,
    filesDataPrefix: filesPrefix,
    schema: status.schema,
    tableCount: status.table_count ?? 0,
    tablesWithData: status.tables_with_data ?? 0,
    totalRows: status.total_rows ?? 0,
    fileCount: status.file_count ?? 0,
    apiCount: status.api_count ?? 0,
    streamCount: status.stream_count ?? 0,
    dumpTimestamp: status.dump_timestamp,
    lastLoaded: status.last_loaded,
    dumpAvailable: status.dump_available,
    dumpTables: status.dump_tables,
    dumpRows: status.dump_rows,
    backboneRunId: status.backbone_run_id,
    backboneGeneratedAt: status.backbone_generated_at,
    vendorLabel: status.vendor_label,
    backboneS3Base: status.backbone_s3_base,
  };
}
