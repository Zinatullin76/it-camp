import type { ApiState, ControllerSnap } from '../types';
import dataRaw from './mnemoData.json';
import type { MnemoData } from './mnemoTypes';

const data = dataRaw as MnemoData;

/** Nominal vessel height (m) used to scale level bars to 0..100 %. */
const NOMINAL_HEIGHT: Record<string, number> = {
  column: 4,
  separator: 4,
  tank: 4,
  elou: 5,
};

/** Mnemonic level key -> backend equipment node id. */
const LV_NODE: Record<string, string> = {
  L602: 'column_K1',
  L4K28: 'column_K1',
  L603: 'sep_E1',
  L603w: 'sep_E1',
  L604: 'column_K2',
  L615: 'sep_E15',
  L617: 'column_K10',
  L626: 'sep_E3',
  L632: 'column_K9',
  L_K31: 'column_K31',
  L_K32: 'column_K32',
  L_K33: 'column_K33',
  Lint: 'elou_1',
};

/** S:* temperature keys -> (node id, param key). */
const TEMP_SRC: Record<string, [string, string]> = {
  T_K1top: ['column_K1', 'top_temp_c'],
  T_K1bot: ['column_K1', 'bottom_temp_c'],
  T_E1: ['sep_E1', 'temperature_c'],
  T_K2top: ['column_K2', 'top_temp_c'],
  T_K2bot: ['column_K2', 'bottom_temp_c'],
  T_K4top: ['column_K4', 'top_temp_c'],
  T_K4bot: ['column_K4', 'bottom_temp_c'],
  T_K9top: ['column_K9', 'top_temp_c'],
  T_K9bot: ['column_K9', 'bottom_temp_c'],
  T_K10top: ['column_K10', 'top_temp_c'],
  T_K10bot: ['column_K10', 'bottom_temp_c'],
  Tp1: ['furnace_P1', 'outlet_temp_c'],
  Tp3: ['furnace_P3', 'outlet_temp_c'],
};

/** Mnemonic pump label -> backend pump node id (pump HMI state colouring). */
const PUMP_NODE: Record<string, string> = {
  'Н-1': 'pump_H1',
  'Н-2': 'pump_H2',
  'Н-4': 'pump_H4',
  'Н-6': 'pump_H6',
  'Н-20': 'pump_H20',
  'Н-58': 'pump_H58',
  'P-101A': 'pump_H1',
};

export type RunState = 'run' | 'off' | 'fail' | 'unknown';

export type ValveState = 'open' | 'closed' | 'mid' | 'fail';

/** Палитра УГО насосного агрегата (приказ № 251-П, приложение № 1, табл. 11–12). */
export const PUMP_COLORS = {
  green: '#00AF50',
  gray: '#BEBEBE',
  yellow: '#FFFF00',
  red: '#FF0000',
  brown: '#AA5500',
  cyan: '#00FFFF',
} as const;

/** Класс CSS-анимации мигания: пара цветов, частота 1 Гц, скачок steps(1, end). */
export type PumpBlink = 'green-gray' | 'gray-green' | 'red-green' | 'red-gray';

export interface PumpVisual {
  volute: string;
  center: string;
  blink?: PumpBlink;
}

/** Визуал насоса по эталону visual/pump: состояния 01–09. */
export const PUMP_SPEC: Record<string, PumpVisual> = {
  '01': { volute: PUMP_COLORS.green, center: PUMP_COLORS.green },
  '02': { volute: PUMP_COLORS.gray, center: PUMP_COLORS.gray },
  '03': { volute: PUMP_COLORS.gray, center: PUMP_COLORS.yellow },
  '04': { volute: PUMP_COLORS.gray, center: PUMP_COLORS.gray, blink: 'green-gray' },
  '05': { volute: PUMP_COLORS.green, center: PUMP_COLORS.green, blink: 'gray-green' },
  '06': { volute: PUMP_COLORS.red, center: PUMP_COLORS.red, blink: 'red-green' },
  '07': { volute: PUMP_COLORS.red, center: PUMP_COLORS.red, blink: 'red-gray' },
  '08': { volute: PUMP_COLORS.brown, center: PUMP_COLORS.brown },
  '09': { volute: PUMP_COLORS.cyan, center: PUMP_COLORS.cyan },
};

/**
 * Бэкенд отдаёт только running/failed, поэтому из 9 состояний доступны
 * 01 Запущен (run), 02 Остановлен (off) и 07 Авария (fail); остальные
 * зарезервированы под данные переходов/блокировок/ремонта/имитации.
 */
export function pumpVisual(st: RunState): PumpVisual {
  switch (st) {
    case 'run':
      return PUMP_SPEC['01'];
    case 'fail':
      return PUMP_SPEC['07'];
    default:
      return PUMP_SPEC['02'];
  }
}

/** S:* flow keys -> (node id, param key). */
const FLOW_SRC: Record<string, [string, string]> = {
  Fmaz: ['sink_fuel_oil', 'flow_kg_s'],
  F_ker: ['sink_kerosene', 'flow_kg_s'],
  F_dt: ['sink_diesel', 'flow_kg_s'],
  F_go: ['sink_gasoil', 'flow_kg_s'],
  Fpbf: ['sink_stabgas', 'flow_kg_s'],
  Fnaph: ['sink_benzene', 'flow_kg_s'],
  F820: ['sep_E16', 'out_flow'],
  water_out: ['sep_E16', 'out_flow'],
};

export interface MnemoLive {
  ctrl(tag: string): ControllerSnap | undefined;
  sval(key: string): number | null;
  lvl(key: string): number;
  lw(key: string): number;
  flowColor(fl: string): string;
  run(key: string): RunState;
  equip(label: string): string | undefined;
  gate(key: string): boolean;
  valve(key: string): ValveState;
  param(label: string, key: string): number | null;
  fireOn: boolean;
  edVolt: boolean;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function buildLive(state: ApiState | null): MnemoLive {
  const tele = (nid: string, key: string): number | null => {
    if (!state) return null;
    const v = state.equipment?.[nid]?.params?.[key];
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
  };

  const levelPct = (key: string): number => {
    const nid = LV_NODE[key];
    if (!nid || !state) return 0;
    const eq = state.equipment?.[nid];
    const h = NOMINAL_HEIGHT[eq?.type ?? ''] ?? 4;
    const lv = eq?.params?.level_m;
    if (typeof lv !== 'number' || !Number.isFinite(lv)) return 0;
    return clamp((lv / h) * 100, 0, 100);
  };

  const sval = (key: string): number | null => {
    if (!state) return null;
    switch (key) {
      case 'Fcrude':
        return state.feed?.flow_kg_s ?? null;
      case 'Tcrude':
        return state.feed?.temperature_c ?? null;
      case 'Tdes':
      case 'Tdes1':
      case 'Tdes2':
      case 'Tdes3': {
        const k = state.temperature?.preheat_outlet;
        return typeof k === 'number' ? k - 273.15 : null;
      }
      case 'Tp2': {
        const t = tele('furnace_P1', 'outlet_temp_c');
        return t;
      }
      case 'P204': {
        return tele('column_K1', 'pressure_bar');
      }
      case 'P213': {
        return tele('column_K2', 'pressure_bar');
      }
      case 'fuelP': {
        let m = 0;
        for (const id of ['furnace_P1', 'furnace_P3', 'furnace_P4a', 'furnace_P4b']) {
          const f = tele(id, 'fuel_flow');
          if (f != null && f > m) m = f;
        }
        return m || null;
      }
      case 'L632':
      case 'L4K28':
        return levelPct(key);
      default:
        break;
    }
    const t = TEMP_SRC[key];
    if (t) return tele(t[0], t[1]);
    const f = FLOW_SRC[key];
    if (f) return tele(f[0], f[1]);
    return null;
  };

  let fuel = 0;
  if (state) {
    for (const id of ['furnace_P1', 'furnace_P3', 'furnace_P4a', 'furnace_P4b']) {
      const f = tele(id, 'fuel_flow');
      if (f != null && f > fuel) fuel = f;
    }
  }

  const runState = (key: string): RunState => {
    const nid = PUMP_NODE[key];
    if (!nid || !state) return 'unknown';
    const es = state.equipment?.[nid] ?? state.equipment_states?.[nid];
    if (!es) return 'unknown';
    if (es.failed) return 'fail';
    return es.running ? 'run' : 'off';
  };

  const param = (label: string, key: string): number | null => {
    const nid = PUMP_NODE[label] ?? label;
    return tele(nid, key);
  };

  const valveState = (key: string): ValveState => {
    if (!state) return 'mid';
    const eq = state.equipment?.[key];
    if (!eq) return 'mid';
    if (eq.failed) return 'fail';
    if (eq.type === 'gate_valve') return eq.params?.open ? 'open' : 'closed';
    const pos = eq.params?.position;
    if (typeof pos !== 'number' || !Number.isFinite(pos)) return 'mid';
    return pos >= 99 ? 'open' : pos <= 1 ? 'closed' : 'mid';
  };

  return {
    ctrl: (tag) => state?.controllers?.[tag],
    sval,
    lvl: levelPct,
    lw: (key) => levelPct(key),
    flowColor: (fl) => data.flows[fl]?.c ?? '#888',
    run: runState,
    equip: (label) => PUMP_NODE[label],
    gate: (key) => {
      const eq = state?.equipment?.[key];
      return typeof eq?.params?.open === 'boolean' ? eq.params.open : true;
    },
    valve: valveState,
    param,
    fireOn: !!(state && fuel > 0.15),
    edVolt: !!(state && (state.equipment?.['elou_1']?.running ?? true)),
  };
}

/** Replicate the HTML digit formatting for instrument values. */
export function fmtVal(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return '--';
  const a = Math.abs(v);
  return v.toFixed(a < 10 ? 2 : a < 100 ? 1 : 0);
}
