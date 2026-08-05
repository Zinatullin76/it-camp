import type { PaletteItem, SchemeNodeData } from './types';

export const PALETTE: PaletteItem[] = [
  { type: 'source', label: 'Источник сырья', category: 'boundary', color: '#35d399' },
  { type: 'sink', label: 'Продукт / отбор', category: 'boundary', color: '#64748b' },
  { type: 'pump', label: 'Насос', category: 'equipment', color: '#35d399' },
  { type: 'valve', label: 'Регулирующий клапан', category: 'equipment', color: '#38bdf8' },
  { type: 'elou', label: 'ЭЛОУ (электродегидратор)', category: 'equipment', color: '#38bdf8' },
  { type: 'heat_exchanger', label: 'Теплообменник', category: 'equipment', color: '#38bdf8' },
  { type: 'heater', label: 'Печь', category: 'equipment', color: '#fb923c' },
  { type: 'column', label: 'Колонна ректификации', category: 'equipment', color: '#67e8f9' },
  { type: 'separator', label: 'Сепаратор', category: 'equipment', color: '#38bdf8' },
];

export const TYPE_COLORS: Record<string, string> = Object.fromEntries(PALETTE.map((p) => [p.type, p.color]));

// Default parameters for a freshly created node.
export const DEFAULT_PARAMS: Record<string, Record<string, unknown>> = {
  source: { flow_kg_s: 100, temperature_c: 25, pressure_bar: 1.01325 },
  sink: {},
  pump: { nominal_flow: 0.1, efficiency_nominal: 0.75 },
  valve: { cv: 0.01, response_rate: 0.2 },
  elou: { vessel_area: 30.0 },
  heat_exchanger: { u: 300.0, area: 200.0 },
  heater: { max_heat_duty: 50000000.0, response_tau: 60.0 },
  column: { num_stages: 20, feed_stage: 10 },
  separator: {},
};

// Node card size per type (width x height) — compact, matches the symbol.
export const NODE_SIZES: Record<string, { w: number; h: number }> = {
  source: { w: 132, h: 70 },
  sink: { w: 132, h: 70 },
  pump: { w: 44, h: 64 },
  valve: { w: 40, h: 56 },
  elou: { w: 120, h: 66 },
  heat_exchanger: { w: 132, h: 70 },
  heater: { w: 118, h: 88 },
  column: { w: 52, h: 128 },
  separator: { w: 48, h: 96 },
};

export function nodeSize(type: string) {
  return NODE_SIZES[type] ?? { w: 120, h: 80 };
}

export function defaultName(type: string): string {
  const p = PALETTE.find((x) => x.type === type);
  return p ? p.label : type;
}

let counter = 0;
export function nextId(type: string): string {
  counter += 1;
  const prefix = type === 'source' || type === 'sink' ? type : type.slice(0, 3);
  return `${prefix}_${counter}`;
}

export function createNode(type: string, x: number, y: number): SchemeNodeData {
  const { w, h } = nodeSize(type);
  return {
    id: nextId(type),
    type,
    name: defaultName(type),
    x: Math.round(x - w / 2),
    y: Math.round(y - h / 2),
    params: { ...(DEFAULT_PARAMS[type] ?? {}) },
  };
}

// Human-readable display of a telemetry value with units.
export function fmtValue(v: unknown, unit = ''): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}${unit}`;
}
