import type { MnemoItem } from './mnemoTypes';
import dataRaw from './mnemoData.json';
import { itemBBox } from './symbols';

const data = dataRaw as { screens: Record<string, { items: MnemoItem[] }> };
const overview = data.screens.overview.items;

/**
 * Scheme node id -> index of the matching equipment item on the "overview"
 * screen of the hand-crafted mnemo scheme. Reusing these positions makes the
 * "Схема" tab look exactly like the reference avt4.html layout.
 */
const IDX: Record<string, number> = {
  src_feed: 0,
  pump_H1: 2,
  hx_T1: 3,
  elou_1: 7,
  elou_2: 9,
  sep_E16: 10,
  sep_E15: 12,
  pump_H20: 13,
  hx_T17: 14,
  column_K1: 16,
  hx_cond1: 18,
  sep_E1: 19,
  pump_H6: 20,
  pump_H2: 21,
  furnace_P1: 22,
  furnace_P3: 24,
  src_gas: 25,
  column_K2: 26,
  hx_cond2: 28,
  sep_E2: 29,
  column_K31: 31,
  column_K32: 32,
  column_K33: 33,
  pump_H4: 40,
  sink_kerosene: 42,
  sink_diesel: 43,
  sink_gasoil: 44,
  sink_fuel_oil: 45,
  column_K4: 48,
  hx_cond4: 49,
  sep_E3: 50,
  column_K7: 53,
  column_K9: 59,
  sep_E18: 61,
  sink_62: 63,
  furnace_P4a: 65,
  column_K10: 66,
  sep_E17: 68,
  pump_H58: 71,
  sink_105: 70,
  sink_105_180: 72,
};

export interface MnemoPlacement {
  item: MnemoItem;
  bb: [number, number, number, number];
}

export function mnemoPlacement(id: string): MnemoPlacement | null {
  const i = IDX[id];
  if (i == null) return null;
  const it = overview[i];
  if (!it) return null;
  return { item: it, bb: itemBBox(it) };
}
