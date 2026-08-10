import { useCallback, useEffect, useState } from 'react';
import { api, connectWs } from '../api';
import type { ApiState, HistoryResponse } from '../types';

export interface Sim {
  live: ApiState | null;
  connected: boolean;
  history: HistoryResponse | null;
  refresh: () => Promise<void>;
  reset: () => void;
}

export function useSimulation(): Sim {
  const [live, setLive] = useState<ApiState | null>(null);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState<HistoryResponse | null>(null);

  const applyTelemetry = useCallback((s: ApiState) => {
    setLive(s);
    setConnected(true);
  }, []);

  useEffect(() => {
    const close = connectWs(applyTelemetry);
    return close;
  }, [applyTelemetry]);

  useEffect(() => {
    api.getHistory().then(setHistory).catch(() => undefined);
  }, []);

  const refresh = useCallback(async () => {
    try {
      applyTelemetry(await api.getState());
    } catch {
      setConnected(false);
    }
  }, [applyTelemetry]);

  const reset = useCallback(() => {
    setLive(null);
    setConnected(false);
    setHistory(null);
  }, []);

  return { live, connected, history, refresh, reset };
}
