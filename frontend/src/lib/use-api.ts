"use client";

import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

interface InternalState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

/** Küçük, bağımlılıksız bir data-fetch hook'u — bu kişisel araç için React Query gibi bir
 * kütüphaneye gerek yok (YAGNI), sadece loading/error/data üçlüsü. `loading` sıfırlaması
 * effect gövdesinde SENKRON değil, promise zincirinin ilk adımında yapılıyor — React'ın
 * "effect içinde senkron setState" uyarısını (cascading render riski) tetiklemesin diye. */
export function useApi<T>(fetcher: () => Promise<T>, deps: React.DependencyList): AsyncState<T> {
  const [state, setState] = useState<InternalState<T>>({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    Promise.resolve()
      .then(() => {
        if (active) setState((prev) => ({ ...prev, loading: true, error: null }));
        return fetcher();
      })
      .then((result) => {
        if (active) setState({ data: result, error: null, loading: false });
      })
      .catch((err) => {
        if (active) setState({ data: null, error: toError(err), loading: false });
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload };
}
