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

  return {
    ctrl: (tag) => state?.controllers?.[tag],
    sval,
    lvl: levelPct,
    lw: (key) => levelPct(key),
    flowColor: (fl) => data.flows[fl]?.c ?? '#888',
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

export function fmtSimTime(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}
