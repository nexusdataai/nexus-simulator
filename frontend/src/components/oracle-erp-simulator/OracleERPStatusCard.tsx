import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { RefreshCw, CheckCircle, XCircle, AlertTriangle, FolderOpen, Database, TableProperties, Rows3, Clock, Archive } from 'lucide-react';
import type { SimulatorStatus } from '../../services/oracleErpSimulatorService';

export interface OracleERPStatusCardProps {
  status: SimulatorStatus | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}

function StatusBadge({ ok, label }: { ok: boolean; label: [string, string] }) {
  return ok ? (
    <Badge variant="default" className="bg-green-500 hover:bg-green-600"><CheckCircle className="h-3 w-3 mr-1" />{label[0]}</Badge>
  ) : (
    <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />{label[1]}</Badge>
  );
}

function Item({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
      <Icon className="h-5 w-5 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium truncate">{String(value)}</p>
      </div>
    </div>
  );
}

export function OracleERPStatusCard({ status, isLoading, error, onRefresh }: OracleERPStatusCardProps) {
  if (isLoading && !status) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-lg">Simulator Status</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between"><Skeleton className="h-6 w-24" /><Skeleton className="h-8 w-8 rounded-full" /></div>
            <div className="grid grid-cols-2 gap-3">{[1,2,3,4].map(i => <Skeleton key={i} className="h-16 rounded-lg" />)}</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !status) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-lg">Simulator Status</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <AlertTriangle className="h-12 w-12 text-yellow-500 mb-4" />
            <h3 className="text-lg font-semibold mb-2">Unable to Load Status</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-sm">{error}</p>
            <Button variant="outline" onClick={onRefresh}><RefreshCw className="h-4 w-4 mr-2" />Retry</Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg">Simulator Status</CardTitle>
        <div className="flex items-center gap-2">
          {status && <StatusBadge ok={status.enabled} label={['Enabled', 'Disabled']} />}
          {status && <StatusBadge ok={status.loaded} label={['Loaded', 'Not Loaded']} />}
          <Button variant="ghost" size="icon" onClick={onRefresh} disabled={isLoading} className="h-8 w-8">
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {status && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Item icon={FolderOpen} label="S3 Bucket" value={status.bucket || 'Not configured'} />
              <Item icon={Database} label="S3 Prefix" value={status.prefix || '—'} />
              <Item icon={TableProperties} label="Tables" value={`${status.tables_with_data} / ${status.table_count}`} />
              <Item icon={Rows3} label="Total Rows" value={status.total_rows.toLocaleString()} />
            </div>
            {(status.dump_timestamp || status.dump_available) && (
              <div className="mt-3 pt-3 border-t grid grid-cols-2 gap-3">
                {status.dump_timestamp && <Item icon={Clock} label="Dump Timestamp" value={new Date(status.dump_timestamp).toLocaleString()} />}
                {status.dump_available && status.dump_tables != null && (
                  <Item icon={Archive} label="Dump Available" value={`${status.dump_tables} tables, ${status.dump_rows?.toLocaleString() ?? '?'} rows`} />
                )}
              </div>
            )}
            {status.last_loaded && (
              <p className="text-xs text-muted-foreground mt-3 text-right">Last loaded: {new Date(status.last_loaded).toLocaleString()}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default OracleERPStatusCard;
