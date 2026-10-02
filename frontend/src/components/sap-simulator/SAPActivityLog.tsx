import { useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Loader2, CheckCircle, XCircle, ScrollText } from 'lucide-react';
import type { StepEntry } from '../../services/sapSimulatorService';

interface SAPActivityLogProps {
  title: string;
  steps: StepEntry[];
  running: boolean;
  summary?: string;
  className?: string;
}

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

export function SAPActivityLog({ title, steps, running, summary, className }: SAPActivityLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [steps.length]);
  if (steps.length === 0 && !running) return null;

  return (
    <Card className={className}>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center gap-2">
          {running ? <Loader2 className="h-4 w-4 animate-spin text-yellow-500" /> : <ScrollText className="h-4 w-4 text-muted-foreground" />}
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          {summary && !running && <span className="text-xs text-muted-foreground ml-auto">{summary}</span>}
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-3 pt-0">
        <div ref={scrollRef} className="rounded-md border bg-muted/30 p-3 font-mono text-xs max-h-48 overflow-y-auto space-y-1">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-muted-foreground shrink-0 w-[70px]">[{formatTime(step.timestamp)}]</span>
              {step.status === 'running' ? <Loader2 className="h-3 w-3 animate-spin text-yellow-500 shrink-0 mt-0.5" />
                : step.status === 'error' ? <XCircle className="h-3 w-3 text-red-500 shrink-0 mt-0.5" />
                : <CheckCircle className="h-3 w-3 text-green-500 shrink-0 mt-0.5" />}
              <span className={step.status === 'error' ? 'text-red-400' : 'text-foreground'}>{step.message}</span>
            </div>
          ))}
          {running && steps.length > 0 && steps[steps.length - 1].status !== 'running' && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="w-[70px]" /><Loader2 className="h-3 w-3 animate-spin" /><span>Working...</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default SAPActivityLog;
