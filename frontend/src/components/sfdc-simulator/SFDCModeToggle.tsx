import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Loader2, ToggleLeft, ToggleRight } from 'lucide-react';
import type { SFDCModeResponse } from '../../services/sfdcSimulatorService';

export interface SFDCModeToggleProps {
  mode: SFDCModeResponse | null;
  isLoading: boolean;
  onToggle: (enabled: boolean) => Promise<void>;
}

export function SFDCModeToggle({ mode, isLoading, onToggle }: SFDCModeToggleProps) {
  const [toggling, setToggling] = useState(false);

  const handleToggle = async () => {
    if (!mode || toggling) return;
    setToggling(true);
    try {
      await onToggle(!mode.simulator_enabled);
    } finally {
      setToggling(false);
    }
  };

  const isSimulator = mode?.simulator_enabled ?? false;
  const ToggleIcon = isSimulator ? ToggleRight : ToggleLeft;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg">SFDC Mode</CardTitle>
        {mode && (
          <Badge variant={isSimulator ? 'default' : 'secondary'} className={isSimulator ? 'bg-purple-500 hover:bg-purple-600' : ''}>
            {mode.mode === 'simulator' ? 'Simulator' : 'Real FDW'}
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">
              {isSimulator ? 'Using in-memory simulator data' : 'Connected to real Salesforce FDW'}
            </p>
            {mode && (
              <p className="text-xs text-muted-foreground mt-1">
                Source: {mode.source}
              </p>
            )}
          </div>
          <Button
            variant={isSimulator ? 'default' : 'outline'}
            size="sm"
            onClick={handleToggle}
            disabled={isLoading || toggling || !mode}
          >
            {toggling ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ToggleIcon className="h-4 w-4 mr-2" />}
            {isSimulator ? 'Switch to Real' : 'Switch to Simulator'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default SFDCModeToggle;
