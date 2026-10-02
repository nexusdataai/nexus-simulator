import { useState, useEffect, useCallback } from 'react';
import { externalSimulatorService, type ExternalRecordsResponse } from '@/services/externalSimulatorService';

const SCHEMA = 'external_sources';

export function useExternalData(tableName: string, limit = 200) {
  const [data, setData] = useState<ExternalRecordsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await externalSimulatorService.getRecords(SCHEMA, tableName, limit);
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load data');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [tableName, limit]);

  useEffect(() => { refresh(); }, [refresh]);

  return { data, loading, error, refresh, rows: data?.rows || [], total: data?.total || 0 };
}
