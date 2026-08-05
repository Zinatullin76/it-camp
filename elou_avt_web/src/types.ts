// Shared types matching the FastAPI backend contracts.

export interface SchemeNodeData {
  id: string;
  type: string;
  name: string;
  x: number;
  y: number;
  params: Record<string, unknown>;
}

export interface SchemeEdgeData {
  id: string;
  source: string;
  target: string;
  source_port: string;
  target_port: string;
  kind: string;
}

export interface Scheme {
  id: string;
  name: string;
  nodes: SchemeNodeData[];
  edges: SchemeEdgeData[];
}

export interface NodeTelemetry {
  type: string;
  name: string;
  running: boolean | null;
  failed: boolean | null;
  failure_mode: string | null;
  params: Record<string, number | boolean | string | null>;
}

export interface ParamSpec {
  key: string;
  label: string;
  unit: string;
  value: number | null;
  min: number;
  max: number;
  step: number;
  int?: boolean;
}

export interface EquipmentSpec {
  node_id: string;
  node_type: string;
  editable: boolean;
  params: ParamSpec[];
}

export interface AlarmData {
  id: string;
  timestamp: number;
  parameter: string;
  actual_value: number;
  threshold: number;
  severity: string;
  description: string;
}

export interface ApiState {
  status: string;
  simulation_time: number;
  feed: {
    flow_kg_s: number;
    flow_m3_h: number;
    temperature_c: number;
    pressure_bar: number;
  };
  pressure: Record<string, number>;
  temperature: Record<string, number>;
  feed_flow: number;
  product_flow: number;
  feed_flow_kg_s: number;
  feed_flow_m3_h: number;
  heat_duty: Record<string, number>;
  level: Record<string, number>;
  pump_states: Record<string, boolean>;
  valve_positions: Record<string, number>;
  equipment_states: Record<string, { failed: boolean; failure_mode: string | null; running: boolean }>;
  equipment: Record<string, NodeTelemetry>;
  active_failures: string[];
  alarms: AlarmData[];
  errors: unknown[];
  controllers?: Record<string, ControllerSnap>;
}

export interface ControllerSnap {
  tag: string;
  desc: string;
  unit: string;
  sp: number;
  pv: number;
  lo: number;
  hi: number;
  kp: number;
  ti: number;
  rev: boolean;
  mode: string;
  out: number;
  i: number;
  man: boolean;
  cascade?: string | null;
  tracked?: boolean;
}

export interface HistoryResponse {
  times: number[];
  series: Record<string, number[]>;
}

export interface PaletteItem {
  type: string;
  label: string;
  category: 'boundary' | 'equipment';
  color: string;
}
