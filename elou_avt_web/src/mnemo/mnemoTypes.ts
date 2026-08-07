export interface MnemoItem {
  t: string;
  x: number;
  y: number;
  w?: number;
  h?: number;
  n?: string;
  s?: string;
  vt?: string;
  st?: string;
  r?: number;
  ctrl?: string;
  tag?: string;
  src?: string;
  u?: string;
  sc?: number;
  fs?: number;
  fc?: string;
  hi?: number;
  fl?: string;
  lv?: string;
  lvw?: string;
  lvb?: string;
  tr?: number;
  sump?: number;
  blind?: number;
  marks?: number[];
}

export interface MnemoPipe {
  f: string;
  pts: number[][];
}

export interface MnemoScreenData {
  name: string;
  vb: number[];
  items: MnemoItem[];
  pipes: MnemoPipe[];
}

export interface MnemoData {
  flows: Record<string, { c: string; n: string }>;
  order: string[];
  screens: Record<string, MnemoScreenData>;
}

export type MnemoItemKey = string | number;
