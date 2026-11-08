import type { ElementType } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FolderOpen,
  Database,
  TableProperties,
  Rows3,
  FileStack,
  Plug,
  Radio,
  Clock,
  Archive,
} from 'lucide-react';
import type { SimulatorArtifactMeta } from './simulatorArtifactMeta';

export interface SimulatorArtifactStatusCardProps {
  meta: SimulatorArtifactMeta | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  title?: string;
}

function StatusBadge({ ok, label }: { ok: boolean; label: [string, string] }) {
  return ok ? (
    <Badge variant="default" className="bg-green-500 hover:bg-green-600">
      <CheckCircle className="h-3 w-3 mr-1" />
      {label[0]}
    </Badge>
  ) : (
    <Badge variant="destructive">
      <XCircle className="h-3 w-3 mr-1" />
      {label[1]}
    </Badge>
  );
}

function Item({ icon: Icon, label, value }: { icon: ElementType; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg min-w-0">
      <Icon className="h-5 w-5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium truncate" title={String(value)}>
          {String(value)}
        </p>
      </div>
    </div>
  );
}

export function SimulatorArtifactStatusCard({
  meta,
  isLoading,
  error,
  onRefresh,
  title = 'Simulator Status',
}: SimulatorArtifactStatusCardProps) {
  if (isLoading && !meta) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-6 w-24" />
            <div className="grid grid-cols-2 gap-3">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !meta) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <AlertTriangle className="h-12 w-12 text-yellow-500 mb-4" />
            <h3 className="text-lg font-semibold mb-2">Unable to Load Status</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-sm">{error}</p>
            <Button variant="outline" onClick={onRefresh}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
        <div className="flex items-center gap-2">
          {meta && <StatusBadge ok={meta.enabled} label={['Enabled', 'Disabled']} />}
          {meta && <StatusBadge ok={meta.loaded} label={['Loaded', 'Not Loaded']} />}
          <Button variant="ghost" size="icon" onClick={onRefresh} disabled={isLoading} className="h-8 w-8">
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {meta && (
          <>
            {meta.vendorLabel && (
              <p className="text-xs text-muted-foreground mb-3">
                Backbone vendor: <span className="text-foreground font-medium">{meta.vendorLabel}</span>
                {meta.backboneRunId ? (
                  <>
                    {' '}
                    · run <code className="text-[10px]">{meta.backboneRunId}</code>
                  </>
                ) : null}
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Item icon={FolderOpen} label="S3 bucket" value={meta.bucket || 'Not configured'} />
              <Item icon={Database} label="Table data prefix" value={meta.tableDataPrefix || '—'} />
              <Item icon={FileStack} label="File data prefix" value={meta.filesDataPrefix || '—'} />
              <Item
                icon={TableProperties}
                label="Tables"
                value={`${meta.tablesWithData} / ${meta.tableCount}`}
              />
              <Item icon={Plug} label="Total APIs" value={meta.apiCount} />
              <Item icon={Radio} label="Total streams" value={meta.streamCount} />
              <Item icon={Rows3} label="Total rows" value={meta.totalRows.toLocaleString()} />
              <Item icon={FileStack} label="Total files" value={meta.fileCount} />
            </div>
            {(meta.dumpTimestamp || meta.dumpAvailable) && (
              <div className="mt-3 pt-3 border-t grid grid-cols-1 sm:grid-cols-2 gap-3">
                {meta.dumpTimestamp && (
                  <Item icon={Clock} label="Dump timestamp" value={new Date(meta.dumpTimestamp).toLocaleString()} />
                )}
                {meta.dumpAvailable && meta.dumpTables != null && (
                  <Item
                    icon={Archive}
                    label="Dump available"
                    value={`${meta.dumpTables} tables, ${meta.dumpRows?.toLocaleString() ?? '?'} rows`}
                  />
                )}
              </div>
            )}
            {meta.lastLoaded && (
              <p className="text-xs text-muted-foreground mt-3 text-right">
                Last loaded: {new Date(meta.lastLoaded).toLocaleString()}
              </p>
            )}
            {meta.backboneGeneratedAt && (
              <p className="text-xs text-muted-foreground mt-1 text-right">
                Backbone generated: {new Date(meta.backboneGeneratedAt).toLocaleString()}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
