import type { ApiState, ControllerSnap, EquipmentSpec, HistoryResponse, Scheme, SchemeNodeData, SchemeEdgeData } from './types';

const API = '';
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/simulation`;

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  getState: () => json<ApiState>('/state'),
  getHistory: (limit = 600) => json<HistoryResponse>(`/history?limit=${limit}`),
  getScheme: () => json<Scheme>('/scheme'),
  getTemplates: () => json<{ types: { type: string; label: string; category: string }[] }>('/scheme/templates'),

  listSchemes: () => json<{ current: string; schemes: string[] }>('/schemes'),

  loadScheme: (name: string) =>
    json<ApiState>('/scheme/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  saveScheme: (nodes: SchemeNodeData[], edges: SchemeEdgeData[]) =>
    json<ApiState>('/scheme', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes, edges }),
    }),

  action: (equipmentId: string, actionType: string, value?: number | null) =>
    json<ApiState>('/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: equipmentId, action_type: actionType, value: value ?? null }),
    }),

  setInput: (partial: { flow_kg_s?: number; temperature_c?: number; pressure_bar?: number }) =>
    json<ApiState>('/input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(partial),
    }),

  injectFailure: (equipmentId: string) => json<ApiState>(`/failure/${equipmentId}`, { method: 'POST' }),

  getEquipmentSpec: (nodeId: string) => json<EquipmentSpec>(`/equipment/spec/${nodeId}`),

  updateEquipmentParams: (equipmentId: string, params: Record<string, number>) =>
    json<ApiState>('/equipment/params', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: equipmentId, params }),
    }),

  startScenario: (scenarioId: string) =>
    json<ApiState>('/scenario/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),

  resetScenario: () => json<ApiState>('/scenario/reset', { method: 'POST' }),

  step: () => json<ApiState>('/scenario/step', { method: 'POST' }),

  command: (tag: string, action: string, value?: number | string | null) =>
    json<{ ok: boolean; controller: ControllerSnap }>('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag, action, value: value ?? null, operator_id: 'hmi' }),
    }),
};

export function connectWs(onState: (s: ApiState) => void): () => void {
  let ws: WebSocket | null = null;
  let retry = 0;

  const open = () => {
    ws = new WebSocket(WS_URL);
    ws.onmessage = (e) => {
      try {
        onState(JSON.parse(e.data as string) as ApiState);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      retry += 1;
      if (retry < 5) setTimeout(open, 2000 * retry);
    };
    ws.onopen = () => (retry = 0);
  };

  open();
  return () => ws?.close();
}
