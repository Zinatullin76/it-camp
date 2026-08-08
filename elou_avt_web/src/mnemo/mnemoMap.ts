import type { MnemoItem } from './mnemoTypes';
import dataRaw from './mnemoData.json';
import { itemBBox } from './symbols';

const data = dataRaw as { screens: Record<string, { items: MnemoItem[] }> };
const overview = data.screens.overview.items;

/**
 * Scheme node id -> index of the matching equipment item on the "overview"
 * screen of the hand-crafted mnemo scheme (Визуал.txt reference). Only the main
 * apparatus are pinned; every other node is placed by neighbour-based layout.
 */
const IDX: Record<string, number> = {
  pump_H1: 0,
  hx_T1: 1,
  furnace_P1: 2,
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
