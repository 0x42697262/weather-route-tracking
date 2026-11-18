import { useEffect, useState } from "react";

export function useNow(refreshMs: number): number {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), refreshMs);
    return () => clearInterval(timer);
  }, [refreshMs]);
  return nowMs;
}
