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
  gate?: string;
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
  /** Состояние параметра для рамки шкалы: normal | warning | alarm | fault. */
  state?: string;
  /** Событие не квитировано — рамка мигает до квитирования. */
  unacked?: boolean;
  /** Обозначение уровня в сепараторе: 'reflux' | 'water'. */
  lmode?: string;
  /** Детализированный конфиг колонны (пресеты К-1..К-4). */
  detail?: MnemoColDetail;
}

/**
 * Детализированная колонна (К-1..К-4) — УГО как в visual/Колонны.
 * Все координаты — в системе полотна символа (viewBox ``vb``).
 */
export interface MnemoColDetail {
  /** Габариты полотна символа. */
  vb: { w: number; h: number };
  /** Целевая ширина узла на схеме (px). */
  nodeW?: number;
  /** Общие контуры аппарата (образующие корпуса К-3). */
  shell?: string[];
  /** Секции колонны (для стриппера К-3 — три, для остальных — одна). */
  sections: ColDetailSection[];
  /** Экспликация штуцеров (подписи с выносками). */
  expl?: ColExpl[];
  /** Предохранительные клапаны. */
  ppk?: ColPpk[];
}

export interface ColDetailSection {
  /** Контур корпуса секции (одна или несколько под-команд). */
  shell?: string | string[];
  /** Заливка корпуса; 'none' — только контур (К-3). */
  fill?: string;
  /** Левая / правая образующая цилиндрической части (для тарелок и уровня). */
  leftX?: number;
  rightX?: number;
  /** Уровень в кубе: y0 = 0 %, y100 = 100 %, lv — ключ уровня. */
  level?: { y0: number; y100: number; lv: string; color?: string };
  /** Тарелки. */
  trays?: ColDetailTray[];
  /** Позиционное обозначение секции. */
  tag?: { x: number; y: number; s: string; size?: number; anchor?: 'start' | 'middle' | 'end'; line?: { x2: number; y2: number } };
  /** Штуцеры секции. */
  nozzles?: ColDetailNozzle[];
}

export interface ColDetailTray {
  /** Y-координата линии тарелки. */
  y: number;
  /** Подпись «N тар.». */
  label?: string;
  /** Глухая тарелка — толще. */
  blind?: boolean;
  /** Уровень за глухой тарелкой (К-1, 26 тар.). */
  lv?: string;
}

export interface ColDetailNozzle {
  /** Прямой штуцер от (врезка в корпус) до (наружу). */
  from?: { x: number; y: number };
  to?: { x: number; y: number };
  /** Ломаный патрубок с отводом (К-3). */
  pts?: number[][];
  /** Фланец на конце штуцера. */
  flange?: boolean;
  /** Толщина линии (К-3: патрубки 1.2, боковые врезки 2). */
  width?: number;
}

export interface ColExpl {
  x: number;
  y: number;
  anchor?: 'start' | 'end' | 'middle';
  lines: { s: string; sub?: boolean }[];
  /** Выноска: линия [x1,y1,x2,y2] от текста к штуцеру. */
  lead?: [number, number, number, number];
}

export interface ColPpk {
  /** Точка врезки клапана (в корпус). */
  x: number;
  y: number;
  scale?: number;
  /** Сброс в атмосферу (петля вверх) либо на факел (отвод вбок). */
  kind?: 'atmos' | 'flare';
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
