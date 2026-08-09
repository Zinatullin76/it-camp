import type { MnemoFurDetail, ColDetailNozzle } from './mnemoTypes';

/**
 * Пресеты детализированных печей П-1..П-5 для палитры редактора схем.
 * Геометрия скопирована из эталонов visual/Печи (УГО по приказу № 251-П):
 *   - p1 -> pech-p1.html   (4 потока нефти + пароперегреватель)
 *   - p2 -> pech-p2(1).html (4 потока: 1,3 в К-2; 2,4 низ К-1 + ПП-1/ПП-2)
 *   - p3 -> pech-p3.html   (4 потока + потолочный экран ПЭ + пароперегреватель)
 *   - p4 -> pech-p4.html   (2 потока: правый — циркуляция низа К-9, левый — К-10)
 *   - p5 -> pech-p5.html   (2 потока перегрева пара/азота)
 */

export interface FurPreset {
  name: string;
  label: string;
  config: MnemoFurDetail;
}

const fl = (
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  extra: Partial<ColDetailNozzle> = {},
): ColDetailNozzle => ({ from: { x: x1, y: y1 }, to: { x: x2, y: y2 }, ...extra });

// Общий корпус печи (одинаков для всех УГО).
const SHELL: Pick<MnemoFurDetail, 'vb' | 'nodeW' | 'stack' | 'conv' | 'arch' | 'rad' | 'base' | 'caps'> = {
  vb: { w: 400, h: 340 },
  nodeW: 200,
  stack: [
    { x: 162, y: 2, w: 36, h: 9 },
    { x: 168, y: 10, w: 24, h: 30 },
  ],
  conv: { x: 122, y: 40, w: 116, h: 78 },
  arch: 'M 60,168 L 122,118 L 238,118 L 300,168 Z',
  rad: { x: 60, y: 168, w: 240, h: 112 },
  base: {
    floor: { x: 52, y: 280, w: 256, h: 12 },
    legs: [
      { x: 70, y: 292, w: 14, h: 18 },
      { x: 276, y: 292, w: 14, h: 18 },
    ],
  },
  caps: [{ x: 234, y: 113, s: 'КОНВ.', anchor: 'end', size: 10 }],
};

// Четыре технологических потока отбензиненной нефти (входы слева, выходы справа).
function fourFlows(): ColDetailNozzle[] {
  const ys = [206, 226, 246, 266];
  const flows: ColDetailNozzle[] = [];
  ys.forEach((y, i) => {
    const n = String(i + 1);
    flows.push(fl(60, y, 4, y, { dir: 'in', label: n, port: i === 0 ? 'in' : `in${i + 1}` }));
    flows.push(fl(300, y, 346, y, { dir: 'out', label: n, port: i === 0 ? 'out' : `out${i + 1}` }));
  });
  return flows;
}

// Пароперегреватель (вход слева в конвекцию, выход справа).
function ppFlows(y: number, inPort: string, outPort: string): ColDetailNozzle[] {
  return [
    fl(122, y, 76, y, { dir: 'in', label: 'ПП', port: inPort }),
    fl(238, y, 346, y, { dir: 'out', label: 'ПП', port: outPort }),
  ];
}

// ---------------------------------------------------------------------------
// П-1 — печь нагрева отбензиненной нефти (4 потока) перед К-2
// ---------------------------------------------------------------------------
const p1: FurPreset = {
  name: 'П-1',
  label: 'П-1 · Нагрев отбензиненной нефти',
  config: {
    ...SHELL,
    tag: { x: 180, y: 238, s: 'П-1', size: 26 },
    pp: [{ x: 128, y: 46, w: 104, h: 16, s: 'ПП' }],
    inst: [{ lead: [192, 20, 222, 20], cx: 240, cy: 20, lines: ['QR', '5001'] }],
    flows: [...fourFlows(), ...ppFlows(54, 'pp_in', 'pp_out')],
  },
};

// ---------------------------------------------------------------------------
// П-2 — потоки 1,3 в К-2; потоки 2,4 подогрев низа К-1; два пароперегревателя
// ---------------------------------------------------------------------------
const p2: FurPreset = {
  name: 'П-2',
  label: 'П-2 · Нефть в К-2 + подогрев низа К-1',
  config: {
    ...SHELL,
    tag: { x: 180, y: 238, s: 'П-2', size: 26 },
    pp: [
      { x: 128, y: 46, w: 104, h: 13, s: 'ПП-1' },
      { x: 128, y: 62, w: 104, h: 13, s: 'ПП-2' },
    ],
    flows: [
      ...fourFlows(),
      ...ppFlows(52.5, 'pp1_in', 'pp1_out'),
      ...ppFlows(68.5, 'pp2_in', 'pp2_out'),
    ],
  },
};

// ---------------------------------------------------------------------------
// П-3 — подогрев низа К-1; левый потолочный экран ПЭ (рибойлер К-4)
// ---------------------------------------------------------------------------
const p3: FurPreset = {
  name: 'П-3',
  label: 'П-3 · Подогрев низа К-1 (рибойлер К-4)',
  config: {
    ...SHELL,
    tag: { x: 180, y: 238, s: 'П-3', size: 26 },
    pp: [{ x: 128, y: 46, w: 104, h: 16, s: 'ПП' }],
    ceil: {
      xs: [96, 109, 122, 135, 148, 161, 174],
      y: 180,
      label: { x: 186, y: 184, s: 'ПЭ (лев.)' },
    },
    flows: [...fourFlows(), ...ppFlows(54, 'pp_in', 'pp_out')],
  },
};

// ---------------------------------------------------------------------------
// П-4 — бензин вторичной перегонки: 1 (правый) — низ К-9, 2 (левый) — низ К-10
// ---------------------------------------------------------------------------
function twoFlows(): ColDetailNozzle[] {
  return [
    fl(60, 222, 4, 222, { dir: 'in', label: '1', port: 'in' }),
    fl(300, 222, 346, 222, { dir: 'out', label: '1', port: 'out' }),
    fl(60, 258, 4, 258, { dir: 'in', label: '2', port: 'in2' }),
    fl(300, 258, 346, 258, { dir: 'out', label: '2', port: 'out2' }),
  ];
}

const p4: FurPreset = {
  name: 'П-4',
  label: 'П-4 · Вторичная перегонка бензина',
  config: {
    ...SHELL,
    tag: { x: 180, y: 238, s: 'П-4', size: 26 },
    flows: twoFlows(),
  },
};

// ---------------------------------------------------------------------------
// П-5 — перегрев пара (азота) для регенерации катализатора, 2 потока
// ---------------------------------------------------------------------------
const p5: FurPreset = {
  name: 'П-5',
  label: 'П-5 · Перегрев пара для регенерации',
  config: {
    ...SHELL,
    tag: { x: 180, y: 238, s: 'П-5', size: 26 },
    flows: twoFlows(),
  },
};

export const PRESET_FURNACES: Record<string, FurPreset> = { p1, p2, p3, p4, p5 };
