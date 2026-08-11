import type { PaletteItem, SchemeNodeData } from './types';
import type { MnemoItem, MnemoColDetail, MnemoFurDetail } from './mnemo/mnemoTypes';
import { PRESET_COLUMNS } from './mnemo/colPresets';
import { PRESET_FURNACES } from './mnemo/furPresets';

export const PALETTE: PaletteItem[] = [
  { type: 'source', label: 'Источник сырья', category: 'boundary', color: '#35d399' },
  { type: 'sink', label: 'Продукт / отбор', category: 'boundary', color: '#64748b' },
  { type: 'pump', label: 'Насос', category: 'equipment', color: '#35d399' },
  { type: 'valve', label: 'Регулирующий клапан', category: 'equipment', color: '#38bdf8' },
  { type: 'angle_valve', label: 'Угловой клапан', category: 'equipment', color: '#38bdf8' },
  { type: 'gate_valve', label: 'Задвижка', category: 'equipment', color: '#38bdf8' },
  { type: 'mixer', label: 'Смеситель', category: 'equipment', color: '#38bdf8' },
  { type: 'splitter', label: 'Разъединитель потока', category: 'equipment', color: '#38bdf8' },
  { type: 'elou', label: 'ЭЛОУ (электродегидратор)', category: 'equipment', color: '#38bdf8' },
  { type: 'heat_exchanger', label: 'Теплообменник', category: 'equipment', color: '#38bdf8' },
  { type: 'heater', label: 'Печь', category: 'equipment', color: '#fb923c' },
  { type: 'heater', label: 'П-1 · Нагрев отбензиненной нефти', category: 'equipment', color: '#fb923c', preset: 'p1' },
  { type: 'heater', label: 'П-2 · Нефть в К-2 + подогрев низа К-1', category: 'equipment', color: '#fb923c', preset: 'p2' },
  { type: 'heater', label: 'П-3 · Подогрев низа К-1 (рибойлер К-4)', category: 'equipment', color: '#fb923c', preset: 'p3' },
  { type: 'heater', label: 'П-4 · Вторичная перегонка бензина', category: 'equipment', color: '#fb923c', preset: 'p4' },
  { type: 'heater', label: 'П-5 · Перегрев пара для регенерации', category: 'equipment', color: '#fb923c', preset: 'p5' },
  { type: 'column', label: 'Колонна ректификации', category: 'equipment', color: '#67e8f9' },
  { type: 'column', label: 'К-1 · Атмосферная колонна', category: 'equipment', color: '#67e8f9', preset: 'k1' },
  { type: 'column', label: 'К-2 · Атмосферная колонна', category: 'equipment', color: '#67e8f9', preset: 'k2' },
  { type: 'column', label: 'К-3 · Отпарная колонна', category: 'equipment', color: '#67e8f9', preset: 'k3' },
  { type: 'column', label: 'К-4 · Стабилизатор', category: 'equipment', color: '#67e8f9', preset: 'k4' },
  { type: 'column', label: 'К-7 · Газосепаратор', category: 'equipment', color: '#67e8f9', preset: 'k7' },
  { type: 'column', label: 'К-9 · Вторичная перегонка бензина', category: 'equipment', color: '#67e8f9', preset: 'k9' },
  { type: 'column', label: 'К-10 · Вторичная перегонка бензина', category: 'equipment', color: '#67e8f9', preset: 'k10' },
  { type: 'column', label: 'К-12/2-3б · Демеркаптанизация', category: 'equipment', color: '#67e8f9', preset: 'k12' },
  { type: 'column', label: 'К-12/4 · Реактор демеркаптанизации', category: 'equipment', color: '#67e8f9', preset: 'k12_4' },
  { type: 'separator', label: 'Сепаратор', category: 'equipment', color: '#38bdf8' },
  { type: 'separator_s1k', label: 'Сепаратор С-1К', category: 'equipment', color: '#38bdf8' },
];

export const TYPE_COLORS: Record<string, string> = Object.fromEntries(PALETTE.map((p) => [p.type, p.color]));

// Human-readable labels/units for telemetry params (used in Inspector + on-scheme tags).
export const PARAM_LABELS: Record<string, { label: string; unit: string }> = {
  flow_kg_s: { label: 'Расход', unit: 'кг/с' },
  feed_flow: { label: 'Расход сырья', unit: 'кг/с' },
  column_pressure: { label: 'Давление в колонне', unit: 'атм' },
  column_temperature: { label: 'Температура в колонне', unit: 'K' },
  furnace_temperature: { label: 'Температура печи', unit: 'K' },
  in_flow: { label: 'Расход вход', unit: 'кг/с' },
  out_flow: { label: 'Расход выход', unit: 'кг/с' },
  power_w: { label: 'Мощность', unit: 'кВт' },
  pressure_bar: { label: 'Давление', unit: 'бар' },
  pressure_in_bar: { label: 'Давление вход', unit: 'бар' },
  pressure_out_bar: { label: 'Давление выход', unit: 'бар' },
  temperature_c: { label: 'Температура', unit: '°C' },
  outlet_temp_c: { label: 'Температура выхода', unit: '°C' },
  top_temp_c: { label: 'Температура верха', unit: '°C' },
  bottom_temp_c: { label: 'Температура низа', unit: '°C' },
  t_cold_in_c: { label: 'Холодный вход', unit: '°C' },
  t_cold_out_c: { label: 'Холодный выход', unit: '°C' },
  t_hot_in_c: { label: 'Горячий вход', unit: '°C' },
  t_hot_out_c: { label: 'Горячий выход', unit: '°C' },
  position: { label: 'Открытие', unit: '%' },
  open: { label: 'Состояние', unit: '' },
  blocked: { label: 'Линия изолирована', unit: '' },
  duty_w: { label: 'Тепловая нагрузка', unit: 'МВт' },
  fuel_flow: { label: 'Расход топлива', unit: 'кг/с' },
  distillate_flow: { label: 'Дистиллят', unit: 'кг/с' },
  side_draw_flow: { label: 'Боковой отбор', unit: 'кг/с' },
  bottoms_flow: { label: 'Кубовый остаток', unit: 'кг/с' },
  level_m: { label: 'Уровень', unit: 'м' },
  level_setpoint_m: { label: 'Уставка уровня', unit: 'м' },
  volume_m3: { label: 'Объём аппарата', unit: 'м³' },
  efficiency: { label: 'КПД', unit: '%' },
  speed_rpm: { label: 'Частота вращения', unit: 'об/мин' },
  converged: { label: 'Сходимость', unit: '' },
};

// Параметры потока (линии), которые можно показывать квадратиком на схеме.
// Значения берутся из телеметрии узла-источника; `phase` — среда в линии.
export const STREAM_PARAMS: Record<string, { label: string; unit: string }> = {
  phase: { label: 'Среда', unit: '' },
  flow_kg_s: { label: 'Расход', unit: 'кг/с' },
  temperature_c: { label: 'Температура', unit: '°C' },
  pressure_bar: { label: 'Давление', unit: 'бар' },
};

// Default parameters for a freshly created node.
export const DEFAULT_PARAMS: Record<string, Record<string, unknown>> = {
  source: { flow_kg_s: 100, temperature_c: 25, pressure_bar: 1.01325 },
  sink: {},
  pump: { nominal_flow: 100.0, efficiency_nominal: 0.75 },
  valve: { cv: 0.01, response_rate: 0.2 },
  angle_valve: { cv: 0.01, response_rate: 0.2 },
  gate_valve: { initial_open: 1 },
  elou: { vessel_area: 30.0 },
  heat_exchanger: { u: 300.0, area: 200.0 },
  heater: { max_heat_duty: 50000000.0, response_tau: 60.0 },
  column: { num_stages: 20, feed_stage: 10 },
  separator: { level_mode: 'reflux' },
  separator_s1k: { level_mode: 'reflux' },
  mixer: { num_inputs: 2 },
  splitter: { num_outputs: 2 },
};

// Node card size per type (width x height) — compact, matches the symbol.
export const NODE_SIZES: Record<string, { w: number; h: number }> = {
  source: { w: 72, h: 40 },
  sink: { w: 72, h: 40 },
  pump: { w: 104, h: 64 },
  valve: { w: 40, h: 56 },
  angle_valve: { w: 84, h: 76 },
  gate_valve: { w: 40, h: 56 },
  mixer: { w: 144, h: 114 },
  splitter: { w: 144, h: 114 },
  elou: { w: 120, h: 66 },
  heat_exchanger: { w: 132, h: 70 },
  heater: { w: 118, h: 88 },
  column: { w: 52, h: 128 },
  separator: { w: 140, h: 70 },
  separator_s1k: { w: 140, h: 70 },
};

export function nodeSize(type: string) {
  return NODE_SIZES[type] ?? { w: 120, h: 80 };
}

/** Габарит карточки узла с учётом пресета детальной колонны/печи. */
export function nodeSizeFor(n: { type: string; params?: Record<string, unknown> }): { w: number; h: number } {
  const d = n.params?.mnemo as MnemoColDetail | MnemoFurDetail | undefined;
  if (d?.vb?.w && d?.nodeW) {
    const nw = d.nodeW;
    return { w: nw + 8, h: Math.round((nw * d.vb.h) / d.vb.w) + 26 };
  }
  const preset = n.params?.preset as string | undefined;
  const pc = preset ? PRESET_COLUMNS[preset] : undefined;
  const pf = preset ? PRESET_FURNACES[preset] : undefined;
  const cfg = pc?.config ?? pf?.config;
  if (cfg?.vb?.w && cfg.nodeW) {
    const nw = cfg.nodeW;
    return { w: nw + 8, h: Math.round((nw * cfg.vb.h) / cfg.vb.w) + 26 };
  }
  return nodeSize(n.type);
}

/** Символ мнемосхемы для узла (пресет детальной колонны или печи). */
export function mnemoForNode(params: Record<string, unknown>): Partial<MnemoItem> | undefined {
  const d = params.mnemo as MnemoColDetail | MnemoFurDetail | undefined;
  if (d?.vb?.w && d?.nodeW) {
    const preset = params.preset as string | undefined;
    const isFur = !!preset && !!PRESET_FURNACES[preset];
    return { t: isFur ? 'fur' : 'col', w: d.nodeW, detail: d };
  }
  const preset = params.preset as string | undefined;
  const pc = preset ? PRESET_COLUMNS[preset] : undefined;
  if (pc?.config?.vb?.w && pc.config.nodeW) return { t: 'col', w: pc.config.nodeW, detail: pc.config };
  const pf = preset ? PRESET_FURNACES[preset] : undefined;
  if (pf?.config?.vb?.w && pf.config.nodeW) return { t: 'fur', w: pf.config.nodeW, detail: pf.config };
  return undefined;
}

export function defaultName(type: string): string {
  const p = PALETTE.find((x) => x.type === type);
  return p ? p.label : type;
}

let counter = 0;
/** Сгенерировать уникальный id объекта (prefix_n), не пересекающийся с уже
 *  существующими. Схемы, загруженные с бэкенда, имеют свои id (source_5,
 *  col_32, ...), поэтому простой счётчик-инкремент может выдать дубликат:
 *  новый узел затирает существующий с тем же id, и его связи «сами собой»
 *  переезжают на новый элемент. */
export function nextId(type: string, taken?: Iterable<string>): string {
  counter += 1;
  const prefix = type === 'source' || type === 'sink' ? type : type.slice(0, 3);
  const used = new Set(taken ?? []);
  let max = counter;
  for (const id of used) {
    if (!id.startsWith(`${prefix}_`)) continue;
    const n = Number(id.slice(prefix.length + 1));
    if (Number.isFinite(n)) max = Math.max(max, n + 1);
  }
  let id = `${prefix}_${max}`;
  while (used.has(id)) {
    max += 1;
    id = `${prefix}_${max}`;
  }
  return id;
}

/** Создать узел. Для детальных колонн передаётся ключ пресета (k1..k4):
 *  в params кладётся конфиг мнемосимвола (detail), число тарелок и стадия питания. */
export function createNode(
  type: string,
  x: number,
  y: number,
  preset?: string,
  existingIds?: Iterable<string>,
): SchemeNodeData {
  const node: SchemeNodeData = {
    id: nextId(type, existingIds),
    type,
    name: defaultName(type),
    x: 0,
    y: 0,
    params: { ...(DEFAULT_PARAMS[type] ?? {}) },
  };
  if (preset) {
    const pc = PRESET_COLUMNS[preset];
    const pf = PRESET_FURNACES[preset];
    const p = pc ?? pf;
    if (p) {
      node.name = p.label;
      node.params = {
        ...node.params,
        preset,
        mnemo: p.config,
      };
      if (pc) {
        node.params.num_stages = pc.numStages;
        node.params.feed_stage = pc.feedStage;
      }
    }
  }
  const { w, h } = nodeSizeFor(node);
  node.x = Math.round(x - w / 2);
  node.y = Math.round(y - h / 2);
  return node;
}

// Human-readable display of a telemetry value with units.
export function fmtValue(v: unknown, unit = ''): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}${unit}`;
}

// ---------------------------------------------------------------------------
// Потоки / фазы технологических линий. Палитра — «Тип продукта» (HEX из
// легенды мнемосхемы). Выбирается в редакторе схемы и определяет цвет линии.
// ---------------------------------------------------------------------------

export interface PhaseMeta {
  id: string;
  label: string;
  color: string;
}

export const PHASE_TYPES: PhaseMeta[] = [
  { id: 'gas_haz', label: 'Опасные газы', color: '#FFD965' },
  { id: 'liq', label: 'Неопасные жидкости', color: '#0070C0' },
  { id: 'oil', label: 'Нефть и нефтепродукты', color: '#000000' },
  { id: 'gas', label: 'Неопасные газы', color: '#00B0F0' },
  { id: 'reag', label: 'Реагенты', color: '#9966FF' },
  { id: 'drain', label: 'Дренажные жидкости', color: '#7F6000' },
  { id: 'other', label: 'Прочие продукты', color: '#54426A' },
];

export const DEFAULT_PHASE = 'oil';

// Устаревшие id/kind старых схем -> тип продукта.
const PHASE_ALIASES: Record<string, string> = {
  process: 'oil',
  hot: 'gas',
  cooling: 'liq',
  crude: 'oil',
  des: 'oil',
  atb: 'oil',
  naph: 'oil',
  ker: 'oil',
  dt: 'oil',
  go: 'oil',
  maz: 'oil',
  gaz: 'gas_haz',
  fuel: 'gas_haz',
  steam: 'gas',
  water: 'liq',
  reag: 'reag',
  sig: 'other',
};

function resolvePhase(id: string): string {
  return PHASE_ALIASES[id] ?? id;
}

export function phaseMeta(id: string): PhaseMeta {
  const resolved = resolvePhase(id);
  return PHASE_TYPES.find((p) => p.id === resolved) ?? PHASE_TYPES[2];
}

export function normalizePhase(kind: string): string {
  const resolved = resolvePhase(kind);
  return PHASE_TYPES.some((p) => p.id === resolved) ? resolved : DEFAULT_PHASE;
}

// Контрастный цвет текста поверх заданного фона.
export function contrastText(hex: string): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const lum = 0.299 * r + 0.587 * g + 0.114 * b;
  return lum > 150 ? '#111' : '#fff';
}
