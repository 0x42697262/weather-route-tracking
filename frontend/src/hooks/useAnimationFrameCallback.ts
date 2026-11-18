import { useCallback, useEffect, useRef } from "react";

export function useAnimationFrameCallback<Value>(callback: (value: Value) => void): (value: Value) => void {
  const callbackRef = useRef(callback);
  const frameRef = useRef<number | null>(null);
  const pendingRef = useRef<{ value: Value } | null>(null);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(
    () => () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
      }
    },
    [],
  );

  return useCallback((value: Value) => {
    pendingRef.current = { value };
    if (frameRef.current !== null) {
      return;
    }
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null;
      const pending = pendingRef.current;
      pendingRef.current = null;
      if (pending !== null) {
        callbackRef.current(pending.value);
      }
    });
  }, []);
}
