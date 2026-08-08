import type { MnemoColDetail, ColDetailSection, ColDetailNozzle } from './mnemoTypes';

/**
 * Пресеты детализированных колонн К-1..К-4 для палитры редактора схем.
 * Геометрия скопирована из эталонов visual/Колонны (УГО по приказу № 251-П):
 *   - k1  -> k-1-expl.html   (640x530, экспликация штуцеров)
 *   - k2  -> k-2(1).html     (220x900, 43 тар., формула уровня y = 852 - 1.52*L)
 *   - k3  -> k3-column.html  (75x425, отпарная, секции К-3/1..К-3/3)
 *   - k4  -> kolonna-k4-level-v5.html (340x800, уровень 750..620)
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
    nz(270, 226, 254, 226, { flange: true }),
    nz(270, 292, 254, 292, { flange: true }),
    nz(270, 332, 254, 332, { flange: true }),
    nz(270, 372, 254, 372, { flange: true }),
    nz(270, 400, 254, 400, { flange: true }),
    nz(370, 96, 386, 96, { flange: true }),
    nz(370, 112, 386, 112, { flange: true }),
    nz(370, 150, 386, 150, { flange: true }),
    nz(370, 372, 386, 372, { flange: true }),
    nz(305, 46, 305, 28, { flange: true }),
    nz(320, 472, 320, 492, { flange: true }),
  ],
};

const k1Expl = [
  {
    x: 248, y: 223, anchor: 'end' as const,
    lead: [252, 220, 264, 220] as [number, number, number, number],
    lines: [{ s: 'Отбор на 22 тар.' }],
  },
  {
    x: 248, y: 289, anchor: 'end' as const,
    lead: [252, 286, 264, 286] as [number, number, number, number],
    lines: [{ s: 'Отбор на 17 тар.' }],
  },
  {
    x: 248, y: 325, anchor: 'end' as const,
    lead: [252, 328, 264, 328] as [number, number, number, number],
    lines: [
      { s: 'Обессоленная нефть с Т-17, Т-19, Т-22/1' },
      { s: 'ввод на 16 тар.', sub: true },
    ],
  },
  {
    x: 248, y: 365, anchor: 'end' as const,
    lead: [252, 368, 264, 368] as [number, number, number, number],
    lines: [
      { s: 'Отбензиненная нефть из П-2' },
      { s: 'горячая струя', sub: true },
    ],
  },
  {
    x: 248, y: 393, anchor: 'end' as const,
    lead: [252, 396, 264, 396] as [number, number, number, number],
    lines: [
      { s: 'Отбензиненная нефть из П-3' },
      { s: 'горячая струя', sub: true },
    ],
  },
  {
    x: 392, y: 93, anchor: 'start' as const,
    lead: [388, 96, 376, 96] as [number, number, number, number],
    lines: [
      { s: 'Острое орошение из Е-1' },
      { s: 'TRC 2 / FRC 408', sub: true },
    ],
  },
  {
    x: 392, y: 121, anchor: 'start' as const,
    lead: [388, 124, 376, 124] as [number, number, number, number],
    lines: [
      { s: 'Циркулирующее орошение на 28 тар.' },
      { s: 'возврат через Т-1/5, FRC 3К-32', sub: true },
    ],
  },
  {
    x: 392, y: 147, anchor: 'start' as const,
    lead: [388, 150, 376, 150] as [number, number, number, number],
    lines: [
      { s: 'Отбор фр. 40-180 °С с 26 тар.' },
      { s: 'глухая тарелка, на Н-6К (Н-6К/1)', sub: true },
    ],
  },
  {
    x: 392, y: 369, anchor: 'start' as const,
    lead: [388, 372, 376, 372] as [number, number, number, number],
    lines: [
      { s: 'Перегретый пар из П-1, П-2, П-3' },
      { s: 'не более 1200 кг/ч, FR 803', sub: true },
    ],
  },
  {
    x: 305, y: 16, anchor: 'middle' as const,
    lead: [305, 22, 305, 28] as [number, number, number, number],
    lines: [{ s: 'Пары фр. НК-180 °С и воды на АВЗ-3' }],
  },
  {
    x: 440, y: 16, anchor: 'middle' as const,
    lead: [440, 22, 440, 34] as [number, number, number, number],
    lines: [{ s: 'ППК, сброс в атмосферу' }],
  },
  {
    x: 320, y: 512, anchor: 'middle' as const,
    lead: [320, 500, 320, 492] as [number, number, number, number],
    lines: [{ s: 'Отбензин. нефть с низа колонны' }],
  },
];

const k1: ColPreset = {
  name: 'К-1',
  label: 'К-1 · Атмосферная колонна',
  numStages: 28,
  feedStage: 18,
  config: {
    vb: { w: 640, h: 530 },
    nodeW: 380,
    sections: [k1Section],
    expl: k1Expl,
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
    nz(60, 153, 44, 153, { flange: true }),
    nz(60, 199, 44, 199, { flange: true }),
    nz(60, 377, 44, 377, { flange: true }),
    nz(60, 421, 44, 421, { flange: true }),
    nz(60, 606, 44, 606, { flange: true }),
    nz(60, 650, 44, 650, { flange: true }),
    nz(60, 785, 44, 785, { flange: true }),
    nz(60, 805, 44, 805, { flange: true }),
    nz(160, 115, 176, 115, { flange: true }),
    nz(160, 153, 176, 153, { flange: true }),
    nz(160, 176, 176, 176, { flange: true }),
    nz(160, 377, 176, 377, { flange: true }),
    nz(160, 398, 176, 398, { flange: true }),
    nz(160, 561, 176, 561, { flange: true }),
    nz(160, 585, 176, 585, { flange: true }),
    nz(95, 46, 95, 28, { flange: true }),
    nz(110, 852, 110, 872, { flange: true }),
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
const k3Pipe = (pts: number[][]): ColDetailNozzle => ({ pts, width: 1.2 });
const k3Side = (y: number): ColDetailNozzle => nz(11.5, y, 0, y, { width: 2 });

const k3Sections: ColDetailSection[] = [
  {
    shell: [
      'M 11.5 22 L 36 15 L 59.5 22',
      'M 11.5 105 L 36 113 L 59.5 105',
    ],
    fill: 'none',
    tag: { x: 15, y: 56, s: 'К-3/1', size: 10, anchor: 'start', line: { x2: 54, y2: 61 } },
    nozzles: [
      k3Pipe([[36, 15], [36, 4], [0, 4]]),
      k3Side(31),
      k3Pipe([[36, 113], [36, 122], [75, 122]]),
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
      k3Pipe([[36, 166], [36, 151.5], [0, 151.5]]),
      k3Side(188),
      k3Pipe([[36, 264], [36, 273], [75, 273]]),
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
      k3Pipe([[36, 310], [36, 299.5], [0, 299.5]]),
      k3Side(336),
      k3Pipe([[36, 408], [36, 417], [75, 417]]),
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
    nz(70, 265, 34, 265),
    nz(70, 385, 34, 385),
    nz(70, 505, 34, 505),
    nz(180, 655, 222, 655),
    nz(104.3, 160, 104.3, 118),
    nz(111, 750, 111, 786),
    nz(139, 750, 139, 786),
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

export const PRESET_COLUMNS: Record<string, ColPreset> = { k1, k2, k3, k4 };
