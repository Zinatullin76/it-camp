import type { MnemoColDetail, ColDetailSection, ColDetailNozzle } from './mnemoTypes';

/**
 * Пресеты детализированных колонн К-1..К-4 для палитры редактора схем.
 * Геометрия скопирована из эталонов visual/Колонны (УГО по приказу № 251-П):
 *   - k1  -> k-1-expl.html   (640x530, экспликация штуцеров)
 *   - k2  -> k-2(1).html     (220x900, 43 тар., формула уровня y = 852 - 1.52*L)
 *   - k3  -> k3-column.html  (75x425, отпарная, секции К-3/1..К-3/3)
 *   - k4  -> kolonna-k4-level-v5.html (340x800, уровень 750..620)
 *   - k7  -> K-7.html        (200x520, газосепаратор, перечень K-7_shtutsera.txt)
 *   - k9  -> k-9(1).html     (760x960, вторичная перегонка бензина)
 *   - k10 -> k10.html        (300x800, вторичная перегонка, 5 входов слева)
 *   - k12 -> k12-2-3.html    (131x414, К-12/2 реактор + К-12/3 стриппинг)
 *   - k12_4 -> k-12-4.html   (140x360, реактор демеркаптанизации)
 */

export interface ColPreset {
  name: string;
  label: string;
  numStages: number;
  feedStage: number;
  config: MnemoColDetail;
}

const nz = (
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  extra: Partial<ColDetailNozzle> = {},
): ColDetailNozzle => ({ from: { x: x1, y: y1 }, to: { x: x2, y: y2 }, ...extra });

// ---------------------------------------------------------------------------
// К-1 — атмосферная колонна (экспликация по k-1-expl.html, колонна +210 по X)
// ---------------------------------------------------------------------------
const k1Section: ColDetailSection = {
  shell: 'M 292 46 L 348 46 L 370 90 L 370 428 L 348 472 L 292 472 L 270 428 L 270 90 Z',
  fill: '#D7D7D7',
  leftX: 270,
  rightX: 370,
  level: { y0: 472, y100: 336, lv: 'lv', color: '#8B5E3C' },
  trays: [
    { y: 112, label: '28 тар.' },
    { y: 150, label: '26 тар.', blind: true },
    { y: 190, label: '25 тар.' },
    { y: 226, label: '22 тар.' },
    { y: 256, label: '18 тар.' },
    { y: 292, label: '17 тар.' },
    { y: 332, label: '16 тар.' },
  ],
  tag: { x: 320, y: 398, s: 'К-1', size: 26 },
  nozzles: [
    nz(270, 226, 254, 226, { flange: true, dir: 'in', port: 'in' }),
    nz(270, 292, 254, 292, { flange: true, dir: 'in', port: 'feed1' }),
    nz(270, 332, 254, 332, { flange: true, dir: 'in', port: 'feed2' }),
    nz(270, 372, 254, 372, { flange: true, dir: 'in', port: 'feed3' }),
    nz(270, 400, 254, 400, { flange: true, dir: 'in', port: 'feed4' }),
    nz(370, 96, 386, 96, { flange: true, dir: 'in', port: 'reflux' }),
    nz(370, 112, 386, 112, { flange: true, dir: 'in', port: 'circ' }),
    nz(370, 150, 386, 150, { flange: true, dir: 'out', port: 'side_draw' }),
    nz(370, 372, 386, 372, { flange: true, dir: 'in', port: 'steam' }),
    nz(305, 46, 305, 28, { flange: true, dir: 'out', port: 'distillate' }),
    nz(320, 472, 320, 492, { flange: true, dir: 'out', port: 'bottoms' }),
  ],
};

const k1: ColPreset = {
  name: 'К-1',
  label: 'К-1 · Атмосферная колонна',
  numStages: 28,
  feedStage: 18,
  config: {
    vb: { w: 640, h: 530 },
    nodeW: 380,
    sections: [k1Section],
    ppk: [{ x: 341.1, y: 47.3, scale: 0.45, kind: 'atmos' }],
  },
};

// ---------------------------------------------------------------------------
// К-2 — атмосферная колонна (k-2(1).html, 43 тарелки)
// ---------------------------------------------------------------------------
const k2Section: ColDetailSection = {
  shell: 'M 82 46 L 138 46 L 160 90 L 160 808 L 138 852 L 82 852 L 60 808 L 60 90 Z',
  fill: '#D7D7D7',
  leftX: 60,
  rightX: 160,
  level: { y0: 852, y100: 776, lv: 'lv', color: '#8B5E3C' },
  trays: [
    { y: 130, label: '43 тар.' },
    { y: 153, label: '36 тар.' },
    { y: 176, label: '35 тар.' },
    { y: 199, label: '34 тар.' },
    { y: 221, label: '33 тар.' },
    { y: 243, label: '32 тар.' },
    { y: 377, label: '26 тар.' },
    { y: 398, label: '25 тар.' },
    { y: 421, label: '24 тар.' },
    { y: 444, label: '23 тар.' },
    { y: 466, label: '22 тар.' },
    { y: 561, label: '16 тар.' },
    { y: 585, label: '15 тар.' },
    { y: 606, label: '14 тар.' },
    { y: 628, label: '13 тар.' },
    { y: 650, label: '12 тар.' },
    { y: 765, label: '6 тар.' },
  ],
  tag: { x: 110, y: 320, s: 'К-2', size: 26 },
  nozzles: [
    nz(60, 153, 44, 153, { flange: true, dir: 'in', port: 'circ1_in' }),
    nz(60, 199, 44, 199, { flange: true, dir: 'out', port: 'circ1_out' }),
    nz(60, 377, 44, 377, { flange: true, dir: 'out', port: 'circ2_out' }),
    nz(60, 421, 44, 421, { flange: true, dir: 'in', port: 'circ2_in' }),
    nz(60, 606, 44, 606, { flange: true, dir: 'in', port: 'circ3_in' }),
    nz(60, 650, 44, 650, { flange: true, dir: 'out', port: 'circ3_out' }),
    nz(60, 785, 44, 785, { flange: true, dir: 'in', port: 'in' }),
    nz(60, 805, 44, 805, { flange: true, dir: 'in', port: 'steam' }),
    nz(160, 115, 176, 115, { flange: true, dir: 'in', port: 'reflux' }),
    nz(160, 153, 176, 153, { flange: true, dir: 'in', port: 'k31_vap' }),
    nz(160, 176, 176, 176, { flange: true, dir: 'out', port: 'k31_liq' }),
    nz(160, 377, 176, 377, { flange: true, dir: 'in', port: 'k32_vap' }),
    nz(160, 398, 176, 398, { flange: true, dir: 'out', port: 'k32_liq' }),
    nz(160, 561, 176, 561, { flange: true, dir: 'in', port: 'k33_vap' }),
    nz(160, 585, 176, 585, { flange: true, dir: 'out', port: 'k33_liq' }),
    nz(95, 46, 95, 28, { flange: true, dir: 'out', port: 'distillate' }),
    nz(110, 852, 110, 872, { flange: true, dir: 'out', port: 'bottoms' }),
  ],
};

const k2: ColPreset = {
  name: 'К-2',
  label: 'К-2 · Атмосферная колонна',
  numStages: 43,
  feedStage: 36,
  config: {
    vb: { w: 220, h: 900 },
    nodeW: 130,
    sections: [k2Section],
    ppk: [{ x: 131.1, y: 47.3, scale: 0.45, kind: 'atmos' }],
  },
};

// ---------------------------------------------------------------------------
// К-3 — отпарная колонна (стриппинг, k3-column.html)
// ---------------------------------------------------------------------------
const k3Pipe = (pts: number[][], extra: Partial<ColDetailNozzle> = {}): ColDetailNozzle => ({ pts, width: 1.2, ...extra });
const k3Side = (y: number, extra: Partial<ColDetailNozzle> = {}): ColDetailNozzle => nz(11.5, y, 0, y, { width: 2, ...extra });

const k3Sections: ColDetailSection[] = [
  {
    shell: [
      'M 11.5 22 L 36 15 L 59.5 22',
      'M 11.5 105 L 36 113 L 59.5 105',
    ],
    fill: 'none',
    tag: { x: 15, y: 56, s: 'К-3/1', size: 10, anchor: 'start', line: { x2: 54, y2: 61 } },
    nozzles: [
      k3Pipe([[36, 15], [36, 4], [0, 4]], { dir: 'out', port: 'k31_vap' }),
      k3Side(31, { dir: 'in', port: 'k31_liq' }),
      k3Side(96.5, { dir: 'in', port: 'k31_steam' }),
      k3Pipe([[36, 113], [36, 122], [75, 122]], { dir: 'out', port: 'k31_out' }),
    ],
  },
  {
    shell: [
      'M 11.5 174 L 36 166 L 59.5 174',
      'M 11.5 256 L 36 264 L 59.5 256',
    ],
    fill: 'none',
    tag: { x: 15, y: 208, s: 'К-3/2', size: 10, anchor: 'start', line: { x2: 54, y2: 213 } },
    nozzles: [
      k3Pipe([[36, 166], [36, 151.5], [0, 151.5]], { dir: 'out', port: 'k32_vap' }),
      k3Side(188, { dir: 'in', port: 'k32_liq' }),
      k3Pipe([[36, 264], [36, 273], [75, 273]], { dir: 'out', port: 'k32_out' }),
    ],
  },
  {
    shell: [
      'M 11.5 317 L 36 310 L 59.5 317',
      'M 11.5 400 L 36 408 L 59.5 400',
    ],
    fill: 'none',
    tag: { x: 15, y: 358, s: 'К-3/3', size: 10, anchor: 'start', line: { x2: 54, y2: 363 } },
    nozzles: [
      k3Pipe([[36, 310], [36, 299.5], [0, 299.5]], { dir: 'out', port: 'k33_vap' }),
      k3Side(336, { dir: 'in', port: 'k33_liq' }),
      k3Pipe([[36, 408], [36, 417], [75, 417]], { dir: 'out', port: 'k33_out' }),
    ],
  },
];

const k3: ColPreset = {
  name: 'К-3',
  label: 'К-3 · Отпарная колонна',
  numStages: 10,
  feedStage: 5,
  config: {
    vb: { w: 75, h: 425 },
    nodeW: 70,
    shell: [
      'M 11.5 22 L 11.5 148  M 11.5 155 L 11.5 296  M 11.5 303 L 11.5 400',
      'M 59.5 22 L 59.5 119  M 59.5 125 L 59.5 270  M 59.5 279 L 59.5 400',
    ],
    sections: k3Sections,
  },
};

// ---------------------------------------------------------------------------
// К-4 — стабилизатор бензина (kolonna-k4-level-v5.html)
// ---------------------------------------------------------------------------
const k4Section: ColDetailSection = {
  shell: 'M 70 200 L 98 160 L 152 160 L 180 200 L 180 700 L 152 750 L 98 750 L 70 700 Z',
  fill: '#E6E6E6',
  leftX: 70,
  rightX: 180,
  level: { y0: 750, y100: 620, lv: 'lv', color: '#000000' },
  trays: [
    { y: 265, label: '34 тар.' },
    { y: 385, label: '23 тар.' },
    { y: 505, label: '15 тар.' },
  ],
  tag: { x: 125, y: 452, s: 'К-4', size: 30 },
  nozzles: [
    nz(70, 265, 34, 265, { dir: 'in', port: 'reflux' }),
    nz(70, 385, 34, 385, { dir: 'in', port: 'feed1' }),
    nz(70, 505, 34, 505, { dir: 'in', port: 'feed2' }),
    nz(180, 655, 222, 655, { dir: 'in', port: 'reboil' }),
    nz(104.3, 160, 104.3, 118, { dir: 'out', port: 'distillate' }),
    nz(111, 750, 111, 786, { dir: 'out', port: 'bottoms' }),
    nz(139, 750, 139, 786, { dir: 'out', port: 'product' }),
    nz(180, 240, 200, 240),
  ],
};

const k4: ColPreset = {
  name: 'К-4',
  label: 'К-4 · Стабилизатор',
  numStages: 34,
  feedStage: 23,
  config: {
    vb: { w: 340, h: 800 },
    nodeW: 150,
    sections: [k4Section],
    ppk: [
      { x: 200, y: 240, scale: 0.413, kind: 'flare' },
      { x: 138.1, y: 162.8, scale: 0.413, kind: 'atmos' },
    ],
  },
};

// ---------------------------------------------------------------------------
// К-7 — газосепаратор (K-7.html / K-7_shtutsera.txt)
// ---------------------------------------------------------------------------
const k7Section: ColDetailSection = {
  shell: 'M 68 74 L 114 55 L 160 74 L 160 490 L 114 509 L 68 490 Z',
  fill: '#D7D7D7',
  leftX: 68,
  rightX: 160,
  level: { y0: 508, y100: 270, lv: 'lv', color: '#000000' },
  trays: [
    { y: 175, blind: true },
    { y: 211 },
    { y: 337, label: '17 тар.' },
    { y: 387, label: '12 тар.' },
    { y: 445, label: '9 тар.' },
  ],
  tag: { x: 114, y: 152, s: 'К-7', size: 30 },
  nozzles: [
    nz(114, 55, 114, 0, { dir: 'in', port: 'in' }),
    nz(160, 88, 200, 88, { dir: 'out', port: 'distillate' }),
    nz(160, 150, 190, 150, { dir: 'in', port: 'vap_top' }),
    nz(68, 211, 50, 211, { dir: 'out', port: 'liq_top' }),
    nz(68, 321, 50, 321, { dir: 'in', port: 'liq_bot' }),
    nz(160, 287, 190, 287, { dir: 'out', port: 'vap_bot' }),
    nz(68, 428, 18, 428, { dir: 'in', port: 'gas' }),
    nz(114, 509, 114, 520, { dir: 'out', port: 'bottoms' }),
  ],
};

const k7: ColPreset = {
  name: 'К-7',
  label: 'К-7 · Газосепаратор',
  numStages: 25,
  feedStage: 12,
  config: {
    vb: { w: 200, h: 520 },
    nodeW: 100,
    sections: [k7Section],
    ppk: [
      { x: 86, y: 55, scale: 0.4, kind: 'flare' },
      { x: 142, y: 55, scale: 0.4, kind: 'atmos' },
    ],
  },
};

// ---------------------------------------------------------------------------
// К-9 — колонна вторичной перегонки бензина (k-9(1).html)
// ---------------------------------------------------------------------------
const k9Section: ColDetailSection = {
  shell: 'M 275 160 L 345 160 L 370 200 L 370 800 L 345 840 L 275 840 L 250 800 L 250 200 Z',
  fill: '#D7D7D7',
  leftX: 250,
  rightX: 370,
  level: { y0: 800, y100: 620, lv: 'lv', color: '#000000' },
  trays: [
    { y: 270, label: '60 тар.' },
    { y: 400, label: '25 тар.' },
    { y: 650, label: '11 тар.' },
    { y: 715, label: '8 тар.' },
  ],
  tag: { x: 310, y: 530, s: 'К-9', size: 42 },
  nozzles: [
    nz(308.88, 159.14, 308.88, 76.14, { dir: 'out', port: 'distillate' }),
    nz(368, 262, 470, 262, { dir: 'in', port: 'reflux' }),
    nz(252, 392, 150, 392, { dir: 'in', port: 'feed1' }),
    nz(252, 642, 150, 642, { dir: 'in', port: 'feed2' }),
    nz(252, 772, 150, 772, { dir: 'in', port: 'feed3' }),
    nz(287.89, 838.84, 287.89, 872.33, { dir: 'out', port: 'product' }),
    nz(328.51, 839.58, 328.51, 873.07, { dir: 'out', port: 'bottoms' }),
  ],
};

const k9: ColPreset = {
  name: 'К-9',
  label: 'К-9 · Вторичная перегонка бензина',
  numStages: 30,
  feedStage: 15,
  config: {
    vb: { w: 760, h: 960 },
    nodeW: 200,
    sections: [k9Section],
    ppk: [
      { x: 336.8, y: 159.6, scale: 0.4, kind: 'atmos' },
      { x: 281.6, y: 159.6, scale: 0.4, kind: 'atmos' },
    ],
  },
};

// ---------------------------------------------------------------------------
// К-10 — колонна вторичной перегонки бензина (k10.html, входы — 5 слева)
// ---------------------------------------------------------------------------
const k10Section: ColDetailSection = {
  shell: 'M 100 120 L 130 88 L 170 88 L 200 120 L 200 690 L 170 722 L 130 722 L 100 690 Z',
  fill: '#D7D7D7',
  leftX: 100,
  rightX: 200,
  level: { y0: 722, y100: 622, lv: 'lv', color: '#000000' },
  trays: [
    { y: 155 },
    { y: 250, label: '37 тар.' },
    { y: 278, label: '35 тар.' },
    { y: 306, label: '31 тар.' },
    { y: 334, label: '28 тар.' },
    { y: 362, label: '25 тар.' },
    { y: 390, label: '17 тар.' },
    { y: 580, label: '10 тар.' },
  ],
  tag: { x: 150, y: 215, s: 'К-10', size: 30 },
  nozzles: [
    nz(151.71, 88.9, 151.71, 5.9, { dir: 'out', port: 'distillate' }),
    nz(200, 164.72, 240.12, 164.72, { dir: 'in', port: 'reflux' }),
    nz(100, 267.47, 59.66, 267.47, { dir: 'in', port: 'feed1' }),
    nz(100, 296.18, 59.78, 296.18, { dir: 'in', port: 'feed2' }),
    nz(100, 352.95, 59.03, 352.95, { dir: 'in', port: 'feed3' }),
    nz(100, 384.35, 59.24, 384.35, { dir: 'in', port: 'feed4' }),
    nz(100, 570.6, 60.34, 570.6, { dir: 'in', port: 'in' }),
    nz(133.89, 721.08, 133.89, 761.66, { dir: 'out', port: 'bottoms' }),
    nz(165.68, 721.53, 165.68, 762.1, { dir: 'out', port: 'product' }),
  ],
};

const k10: ColPreset = {
  name: 'К-10',
  label: 'К-10 · Вторичная перегонка бензина',
  numStages: 30,
  feedStage: 15,
  config: {
    vb: { w: 300, h: 800 },
    nodeW: 130,
    sections: [k10Section],
    ppk: [
      { x: 168.7, y: 87.3, scale: 0.4, kind: 'flare' },
      { x: 133.3, y: 87.3, scale: 0.4, kind: 'atmos' },
    ],
  },
};

// ---------------------------------------------------------------------------
// К-12/2 (реактор) + К-12/3 (стриппинг) — общая обечайка (k12-2-3.html)
// ---------------------------------------------------------------------------
const k12Pipe = (pts: number[][], extra: Partial<ColDetailNozzle> = {}): ColDetailNozzle => ({ pts, width: 1.6, ...extra });

const k12SectionTop: ColDetailSection = {
  shell: 'M 26 47 L 59.5 37.5 L 94 47 L 94 372 L 59.5 382 L 26 372 Z',
  fill: '#D7D7D7',
  leftX: 26,
  rightX: 94,
  tag: { x: 59.5, y: 156, s: 'К-12/2', size: 12 },
  trays: [
    { y: 298.5, label: '4 тар.' },
    { y: 311.5, label: '3 тар.' },
    { y: 324.5, label: '2 тар.' },
    { y: 337.5, label: '1 тар.' },
  ],
  nozzles: [
    nz(59.5, 37.5, 59.5, 8, { dir: 'in', port: 'feed' }),
    k12Pipe([[59.5, 177], [59.5, 188.5], [13, 188.5]], { dir: 'in', port: 'in' }),
    k12Pipe([[59.5, 237], [59.5, 210.5], [129, 210.5]], { dir: 'out', port: 'distillate' }),
    nz(94, 265.5, 113.5, 265.5, { dir: 'in', port: 'reflux' }),
    nz(23, 363.5, 0, 363.5, { dir: 'in', port: 'steam' }),
    k12Pipe([[59.5, 382], [59.5, 394.5], [79, 394.5]], { dir: 'out', port: 'bottoms' }),
  ],
};

const k12SectionBot: ColDetailSection = {
  shell: ['M 26 167 L 59.5 177 L 94 167', 'M 26 246 L 59.5 237 L 94 246'],
  fill: 'none',
  leftX: 26,
  rightX: 94,
  tag: { x: 59, y: 259, s: 'К-12/3', size: 12 },
  trays: [],
  nozzles: [],
};

const k12: ColPreset = {
  name: 'К-12/2-3б',
  label: 'К-12/2-3б · Демеркаптанизация',
  numStages: 4,
  feedStage: 2,
  config: {
    vb: { w: 131, h: 414 },
    nodeW: 100,
    sections: [k12SectionTop, k12SectionBot],
  },
};

// ---------------------------------------------------------------------------
// К-12/4 — реактор демеркаптанизации (k-12-4.html)
// ---------------------------------------------------------------------------
const k12_4Section: ColDetailSection = {
  shell: 'M 25 40 A 45 16 0 0 1 115 40 L 115 320 A 45 16 0 0 1 25 320 Z',
  fill: '#D7D7D7',
  leftX: 25,
  rightX: 115,
  tag: { x: 70, y: 150, s: 'К-12/4', size: 16 },
  trays: [],
  nozzles: [
    nz(70, 40, 70, 10, { dir: 'in', port: 'in' }),
    nz(70, 320, 70, 350, { dir: 'out', port: 'out' }),
  ],
};

const k12_4: ColPreset = {
  name: 'К-12/4',
  label: 'К-12/4 · Реактор демеркаптанизации',
  numStages: 1,
  feedStage: 0,
  config: {
    vb: { w: 140, h: 360 },
    nodeW: 90,
    sections: [k12_4Section],
  },
};

export const PRESET_COLUMNS: Record<string, ColPreset> = { k1, k2, k3, k4, k7, k9, k10, k12, k12_4 };
