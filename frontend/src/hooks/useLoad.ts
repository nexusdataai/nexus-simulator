import { useCallback, useEffect, useRef, useState } from 'react';
import { errorText } from '@/core/format';

/**
 * Load data when the screen opens (and when `deps` change).
 * `reload()` fetches again and keeps the current data on screen meanwhile.
 */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);

  const run = useCallback((keep: boolean) => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    if (!keep) setData(null);
    return fn()
      .then(d => { if (id === seq.current) setData(d); })
      .catch(e => { if (id === seq.current) setError(errorText(e)); })
      .finally(() => { if (id === seq.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(false); }, [run]);

  return { data, error, loading, reload: () => run(true), setData };
}
