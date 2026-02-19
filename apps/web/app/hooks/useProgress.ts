import { useCallback, useEffect, useRef, useState } from "react";

export function useProgress() {
  const [progress, setProgress] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => stop, [stop]);

  const start = useCallback(() => {
    setProgress(0);
    stop();
    timerRef.current = setInterval(() => {
      setProgress((prev) => {
        if (prev === null) return null;
        if (prev >= 90) return prev;
        return Math.min(90, prev + Math.max(0.5, (90 - prev) / 15));
      });
    }, 200);
  }, [stop]);

  const complete = useCallback(() => {
    stop();
    setProgress(100);
    setTimeout(() => setProgress(null), 400);
  }, [stop]);

  const isActive = progress !== null;
  const pct = progress !== null ? Math.round(progress) : 0;

  return { progress, isActive, pct, start, complete };
}
