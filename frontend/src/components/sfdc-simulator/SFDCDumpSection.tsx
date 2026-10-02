import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { ChevronDown, ChevronRight, Upload, Loader2 } from 'lucide-react';
import { SFDCActivityLog } from './SFDCActivityLog';
import {
  sfdcSimulatorService,
  type SFDCDumpRequest,
  type SFDCDumpStatus,
  type SFDCSimulatorError,
  type SFDCStepEntry,
} from '../../services/sfdcSimulatorService';
import { useToast } from '../../hooks/use-toast';

export function SFDCDumpSection() {
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [sourceUrl, setSourceUrl] = useState('');
  const [schema, setSchema] = useState('sfdc_itxp2dev');
  const [tables, setTables] = useState('Account,Lead,Opportunity');
  const [limit, setLimit] = useState('10000');
  const [dumpAll, setDumpAll] = useState(false);
  const [dumping, setDumping] = useState(false);
  const [dumpSteps, setDumpSteps] = useState<SFDCStepEntry[]>([]);
  const [dumpProgress, setDumpProgress] = useState<{ done: number; total: number; rows: number } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setSourceUrl(window.location.origin + '/');
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const pollDumpStatus = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s: SFDCDumpStatus = await sfdcSimulatorService.getDumpStatus();
        if (s.steps) setDumpSteps(s.steps);
        if (s.tables_total && s.tables_total > 0) {
          setDumpProgress({ done: s.tables_done || 0, total: s.tables_total, rows: s.rows_dumped || 0 });
        }
        if (!s.running) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setDumping(false);
          toast({ title: 'Dump Complete', description: s.result?.message as string || 'FDW data dump finished' });
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        setDumping(false);
      }
    }, 2000);
  };

  const handleDump = async () => {
    if (!sourceUrl.trim()) { toast({ title: 'Source URL required', variant: 'destructive' }); return; }
    setDumping(true);
    setDumpSteps([]);
    setDumpProgress(null);
    try {
      const req: SFDCDumpRequest = {
        source_url: sourceUrl.trim(),
        schema: schema || undefined,
        dump_all: dumpAll,
        limit: parseInt(limit) || 10000,
      };
      if (tables.trim() && !dumpAll) req.tables = tables.split(',').map(t => t.trim()).filter(Boolean);
      await sfdcSimulatorService.triggerDump(req);
      toast({ title: 'Dump Started', description: 'Polling for progress...' });
      pollDumpStatus();
    } catch (err) {
      setDumping(false);
      toast({ title: 'Dump Failed', description: (err as SFDCSimulatorError).message, variant: 'destructive' });
    }
  };

  const Chevron = expanded ? ChevronDown : ChevronRight;

  return (
    <Card>
      <CardHeader className="cursor-pointer select-none" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-2">
          <Chevron className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-lg">Dump from Live FDW</CardTitle>
          {dumping && <Badge className="bg-yellow-500">Running</Badge>}
          {dumpProgress && dumping && (
            <span className="text-xs text-muted-foreground ml-2">
              {dumpProgress.done}/{dumpProgress.total} tables, {(dumpProgress.rows ?? 0).toLocaleString()} rows
            </span>
          )}
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Dump data from a live FDW runtime (via its ALB URL) to S3. This creates the data files the simulator loads.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Source URL (ALB)</label>
              <Input placeholder="https://..." value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Schema</label>
              <Input placeholder="sfdc_itxp2dev" value={schema} onChange={e => setSchema(e.target.value)} className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Tables (comma-separated, or leave empty)</label>
              <Input placeholder="Account,Lead,Opportunity" value={tables} onChange={e => setTables(e.target.value)} disabled={dumpAll} className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Row Limit per Table</label>
              <Input type="number" placeholder="10000" value={limit} onChange={e => setLimit(e.target.value)} className="mt-1" />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={dumpAll} onChange={e => setDumpAll(e.target.checked)} className="rounded" />
              Dump all tables
            </label>
            <Button size="sm" onClick={handleDump} disabled={dumping}>
              {dumping ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
              {dumping ? 'Dumping...' : 'Start Dump'}
            </Button>
          </div>

          {(dumping || dumpSteps.length > 0) && (
            <SFDCActivityLog
              title={dumping ? 'Dump in Progress...' : 'Dump Complete'}
              steps={dumpSteps}
              running={dumping}
              summary={dumpProgress && !dumping ? `${dumpProgress.done} tables, ${(dumpProgress.rows ?? 0).toLocaleString()} rows` : undefined}
            />
          )}
        </CardContent>
      )}
    </Card>
  );
}

export default SFDCDumpSection;
