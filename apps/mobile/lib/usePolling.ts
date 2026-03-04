import { useEffect, useRef, useCallback } from "react";

interface UsePollingOptions<T> {
  fetchFn: () => Promise<T>;
  intervalMs: number;
  shouldPoll: (data: T) => boolean;
  onComplete?: (data: T) => void;
  enabled: boolean;
}

export function usePolling<T>({
  fetchFn,
  intervalMs,
  shouldPoll,
  onComplete,
  enabled,
}: UsePollingOptions<T>) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const poll = useCallback(async () => {
    if (!mountedRef.current) return;
    try {
      const data = await fetchFn();
      if (!mountedRef.current) return;
      if (shouldPoll(data)) {
        timerRef.current = setTimeout(poll, intervalMs);
      } else {
        onComplete?.(data);
      }
    } catch {
      // Retry on error
      if (mountedRef.current) {
        timerRef.current = setTimeout(poll, intervalMs);
      }
    }
  }, [fetchFn, intervalMs, shouldPoll, onComplete]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      poll();
    }
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [enabled, poll]);
}
