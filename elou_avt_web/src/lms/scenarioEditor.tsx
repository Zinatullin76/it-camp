import { useMemo, useState } from 'react';
import { api } from '../api';
import type {
  Criterion,
  EquipmentItem,
  ExpectedAction,
  LmsCompetency,
  RestrictionRule,
  ScenarioDefinition,
  TaskCondition,
} from '../types';
import { notifyToast } from './ui';

export const CRITERION_KEYS: { key: string; title: string }[] = [
  { key: 'sequence', title: 'Правильная последовательность' },
  { key: 'parameters', title: 'Контроль параметров' },
  { key: 'time', title: 'Время' },
  { key: 'errors', title: 'Ошибочные действия' },
  { key: 'safety', title: 'Безопасность' },
];

export const ACTION_TYPES = ['TURN_ON', 'TURN_OFF', 'SET_PARAM', 'OPEN_VALVE', 'CLOSE_VALVE', 'INCREASE_PARAM', 'DECREASE_PARAM', 'INJECT_FAILURE', 'RESET_FAILURE'];

export const EVENT_TYPES = ['fault', 'param', 'state', 'alarm', 'mode'];

export const EVENT_TYPE_LABEL: Record<string, string> = {
  fault: 'Отказ',
  param: 'Параметр',
  state: 'Состояние',
  alarm: 'Авария',
  mode: 'Режим',
};

export const EVENT_TYPE_HINT: Record<string, string> = {
  fault: 'Оборудование выходит из строя в этот момент',
  param: 'Значение параметра объекта меняется',
  state: 'Объект переводится в заданное состояние',
  alarm: 'Срабатывает аварийная сигнализация',
  mode: 'Установка переходит в другой режим работы',
};

export const EVENT_TYPE_COLOR: Record<string, string> = {
  fault: '#f87171',
  alarm: '#fbbf24',
  param: '#38bdf8',
  state: '#a78bfa',
  mode: '#34d399',
};

export const ACTION_TYPE_LABEL: Record<string, string> = {
  TURN_ON: 'Включить',
  TURN_OFF: 'Выключить',
  SET_PARAM: 'Задать параметр',
  OPEN_VALVE: 'Открыть клапан',
  CLOSE_VALVE: 'Закрыть клапан',
  INCREASE_PARAM: 'Увеличить параметр',
  DECREASE_PARAM: 'Уменьшить параметр',
  INJECT_FAILURE: 'Внести отказ',
  RESET_FAILURE: 'Сбросить отказ',
};

export const DIRECTIONAL_ACTIONS = ['INCREASE_PARAM', 'DECREASE_PARAM'];

export function isDirectionalAction(v: string): boolean {
  return DIRECTIONAL_ACTIONS.includes(v);
}

export function typeLabel(v: string): string {
  return EVENT_TYPE_LABEL[v] ?? v;
}

export function actionLabel(v: string): string {
  return ACTION_TYPE_LABEL[v] ?? (v === '' ? '— действие —' : v);
}

export function numOr(v: string): number | string {
  const t = v.trim();
  if (t === '') return '';
  const n = Number(t);
  return Number.isFinite(n) ? n : t;
}

export function deadlineNum(v: unknown): number | null {
  if (v == null) return null;
  const t = String(v).trim();
  if (t === '') return null;
  const n = Number(t);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function asStringArray(v: unknown): string[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.map(String);
  return [String(v)];
}

export function asString(v: unknown): string {
  return v == null ? '' : String(v);
}

// ---------------------------------------------------------------------------
// Shared pickers (выпадающие списки вместо свободного ввода)
// ---------------------------------------------------------------------------

export const EQUIP_TYPE_LABEL: Record<string, string> = {
  pump: 'Насосы',
  valve: 'Клапаны',
  heater: 'Печи',
  source: 'Источники',
  sink: 'Стоки',
  column: 'Колонны',
  separator: 'Ёмкости/сепараторы',
  heat_exchanger: 'Теплообменники',
  elou: 'ЭЛОУ',
};

export const TARGET_ATTRS = ['running', 'position', 'fuel_flow', 'failed', 'failure_mode', 'flow_kg_s', 'temperature_c', 'pressure_bar', 'level_m'];

export const ATTR_LABEL: Record<string, string> = {
  running: 'Состояние (вкл/выкл)',
  position: 'Положение клапана',
  fuel_flow: 'Расход топлива',
  failed: 'Отказ',
  failure_mode: 'Режим отказа',
  flow_kg_s: 'Расход, кг/с',
  temperature_c: 'Температура, °C',
  pressure_bar: 'Давление, бар',
  level_m: 'Уровень, м',
  level_percent: 'Уровень, %',
  setpoint_level: 'Уставка уровня',
  reflux_ratio: 'Флегмовое число',
  u: 'Коэф. теплопередачи',
  cv: 'Коэф. пропуска (Cv)',
  area: 'Площадь сечения',
  vessel_area: 'Площадь ёмкости',
  nominal_flow: 'Номинальный расход',
  nominal_volumetric_flow_m3_s: 'Номин. объёмный расход, м³/с',
  num_stages: 'Число тарелок',
  num_inputs: 'Число входов',
  num_outputs: 'Число выходов',
  feed_stage: 'Тарелка питания',
  design_delta_p: 'Расчётный перепад давления',
  efficiency_nominal: 'КПД номинальный',
  flow_coefficient_si: 'Коэф. расхода (СИ)',
  max_heat_duty: 'Макс. тепловая нагрузка',
  response_rate: 'Скорость отклика',
  response_tau: 'Постоянная времени',
  initial_running: 'Нач. состояние',
  initial_position: 'Нач. положение',
  initial_open: 'Нач. открытие',
  initial_fuel_flow: 'Нач. расход топлива',
  initial_reflux_ratio: 'Нач. флегмовое число',
  level_mode: 'Режим уровня',
  preset: 'Пресет',
  mnemo: 'Мнемосхема',
};

export function attrLabel(v: string): string {
  return ATTR_LABEL[v] ?? v;
}

export const RELATION_LABEL: Record<string, string> = {
  '==': 'равно',
  '!=': 'не равно',
  '>': 'больше',
  '<': 'меньше',
  '>=': 'больше или равно',
  '<=': 'меньше или равно',
  between: 'между',
};

export function relationLabel(v: string): string {
  return RELATION_LABEL[v] ?? v;
}

export function equipmentOpts(equipment: EquipmentItem[]): { value: string; label: string }[] {
  return equipment.map((e) => ({ value: e.id, label: `${e.name} · ${e.id}` }));
}

export function competencyOpts(competencies: LmsCompetency[]): { value: string; label: string }[] {
  return competencies.map((c) => ({ value: c.code, label: c.title ? `${c.title} (${c.code})` : c.code }));
}

export function attrOptions(equipment: EquipmentItem[]): string[] {
  const s = new Set<string>(TARGET_ATTRS);
  equipment.forEach((e) => Object.keys(e.params ?? {}).forEach((p) => s.add(p)));
  return Array.from(s);
}

export function TagPicker({ options, value, onChange, placeholder, empty }: {
  options: { value: string; label: string }[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  empty?: string;
}) {
  const selected = new Set(value);
  const remaining = options.filter((o) => !selected.has(o.value));
  const stale = value.filter((v) => !options.some((o) => o.value === v));
  return (
    <div className="tag-picker">
      {value.length === 0 && empty && <span className="tag-picker-empty">{empty}</span>}
      {value.map((v) => {
        const opt = options.find((o) => o.value === v);
        return (
          <span className="tag" key={v}>
            <span title={opt ? opt.label : v}>{opt ? opt.label : v}</span>
            <button type="button" className="tag-x" title="Убрать" onClick={() => onChange(value.filter((x) => x !== v))}>✕</button>
          </span>
        );
      })}
      {remaining.length > 0 && (
        <select
          className="scenario-select tag-picker-select"
          value=""
          onChange={(e) => { if (e.target.value) onChange([...value, e.target.value]); }}
        >
          <option value="">{placeholder ?? '+ добавить'}</option>
          {remaining.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
      {stale.length > 0 && (
        <span className="sc-hint" title="Эти значения не найдены в текущем списке, но будут сохранены">⚠ {stale.join(', ')}</span>
      )}
    </div>
  );
}

export function ObjectSelect({ equipment, value, onChange, width, placeholder }: {
  equipment: EquipmentItem[];
  value: string;
  onChange: (v: string) => void;
  width?: number;
  placeholder?: string;
}) {
  const known = value !== '' && !equipment.some((e) => e.id === value);
  const grouped: Record<string, EquipmentItem[]> = {};
  equipment.forEach((e) => {
    (grouped[e.type] = grouped[e.type] ?? []).push(e);
  });
  return (
    <select className="scenario-select" style={width ? { width } : undefined} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder ?? '— объект —'}</option>
      {known && <option value={value}>{value} (вне схемы)</option>}
      {Object.keys(grouped).sort().map((type) => (
        <optgroup key={type} label={EQUIP_TYPE_LABEL[type] ?? type}>
          {grouped[type].map((e) => <option key={e.id} value={e.id}>{e.name} · {e.id}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

export function AttrSelect({ equipment, value, onChange, width }: {
  equipment: EquipmentItem[];
  value: string;
  onChange: (v: string) => void;
  width?: number;
}) {
  const opts = attrOptions(equipment);
  const known = value !== '' && !opts.includes(value);
  return (
    <select className="scenario-select" style={width ? { width } : undefined} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">— атрибут —</option>
      {known && <option value={value}>{attrLabel(value)}</option>}
      {opts.map((a) => <option key={a} value={a}>{attrLabel(a)}</option>)}
    </select>
  );
}

// ---------------------------------------------------------------------------
// Scenario editor
// ---------------------------------------------------------------------------

export type EventRow = ScenarioDefinition['events'][number] & { rowKey: number };
export type CritRow = Criterion & { rowKey: number };
export type RestrRow = RestrictionRule & { rowKey: number };
export type ExpRow = ExpectedAction & { rowKey: number };
export type CondRow = TaskCondition & { rowKey: number };

export const RELATIONS = ['==', '!=', '>', '<', '>=', '<=', 'between'];

export function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="sc-section">
      <div className="card-title">{title}</div>
      <div className="sc-hint">{hint}</div>
    </div>
  );
}

export function tryJson(s: string): { ok: boolean; error: string } {
  if (!s.trim()) return { ok: true, error: '' };
  try {
    const v = JSON.parse(s);
    if (!v || typeof v !== 'object' || Array.isArray(v)) return { ok: false, error: 'Ожидается объект {...}' };
    return { ok: true, error: '' };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Некорректный JSON' };
  }
}

const STATE_TYPE_LABEL: Record<string, string> = { pump: 'Насос', valve: 'Клапан', heater: 'Печь' };

export function StateEditor({ label, hint, equipment, value, onChange }: {
  label: string;
  hint: string;
  equipment: EquipmentItem[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const parsed = useMemo<Record<string, unknown>>(() => {
    try {
      const v = JSON.parse(value);
      return v && typeof v === 'object' && !Array.isArray(v) ? v : {};
    } catch {
      return {};
    }
  }, [value]);
  const json = tryJson(value);

  const setKey = (key: string, v: unknown) => {
    const next = { ...parsed, [key]: v };
    onChange(JSON.stringify(next, null, 2));
  };
  const removeKey = (key: string) => {
    const next = { ...parsed };
    delete next[key];
    onChange(JSON.stringify(next, null, 2));
  };

  const rows = equipment.filter((e) => e.type === 'pump' || e.type === 'valve' || e.type === 'heater');

  const sliderRow = (e: EquipmentItem, keyName: string, def: number, min: number, max: number, step: number, fmt: (n: number) => string) => {
    const raw = parsed[keyName];
    const val = typeof raw === 'number' ? raw : def;
    return (
      <div className="sc-state-card" key={e.id}>
        <div className="sc-state-head">
          <span className="sc-state-name">{e.name}</span>
          <span className="sc-state-badge">{e.id}</span>
        </div>
        <div className="sc-state-slider-row">
          <input className="sc-state-slider" type="range" min={min} max={max} step={step} value={val} onChange={(ev) => setKey(keyName, Number(ev.target.value))} />
          <span className="sc-state-val">{fmt(val)}</span>
          {typeof raw === 'number' && (
            <button type="button" className="btn btn-ghost" style={{ padding: '1px 6px', fontSize: 11 }} onClick={() => removeKey(keyName)} title="Убрать из состояния">✕</button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="form-field">
      <label className="form-label sc-state-label">
        {label}
        <span className="sc-state-tabs">
          <button type="button" className={`sc-state-tab${mode === 'visual' ? ' on' : ''}`} onClick={() => setMode('visual')}>Визуально</button>
          <button type="button" className={`sc-state-tab${mode === 'json' ? ' on' : ''}`} onClick={() => setMode('json')}>JSON</button>
        </span>
      </label>

      {mode === 'visual' ? (
        rows.length === 0 ? (
          <div className="sc-hint">В текущей схеме нет настраиваемого оборудования (насосы, клапаны, печи). Переключитесь на режим «JSON».</div>
        ) : (
          <div className="sc-state-grid">
            {rows.map((e) => {
              if (e.type === 'pump') {
                const on = parsed[`${e.id}_running`];
                return (
                  <div className="sc-state-card" key={e.id}>
                    <div className="sc-state-head">
                      <span className="sc-state-name">{e.name}</span>
                      <span className="sc-state-badge">{e.id}</span>
                    </div>
                    <button
                      type="button"
                      className={`sc-state-toggle ${on === true ? 'on' : on === false ? 'off' : ''}`}
                      onClick={() => setKey(`${e.id}_running`, on === true ? false : on === false ? undefined : true)}
                      title="Нажмите: включить / остановить / убрать из состояния"
                    >
                      <span className="sc-state-dot" />
                      {on === true ? 'Включён' : on === false ? 'Остановлен' : 'Не задано'}
                    </button>
                  </div>
                );
              }
              if (e.type === 'valve') {
                return sliderRow(e, `${e.id}_position`, e.params?.initial_position ?? 0.5, 0, 1, 0.05, (n) => `${Math.round(n * 100)}%`);
              }
              return sliderRow(e, `${e.id}_fuel_flow`, e.params?.initial_fuel_flow ?? 0, 0, 1.2, 0.02, (n) => n.toFixed(2));
            })}
          </div>
        )
      ) : (
        <>
          <textarea className="form-input sc-json" rows={3} spellCheck={false} value={value} onChange={(e) => onChange(e.target.value)} />
          <div className={`sc-json-status${json.ok ? ' ok' : ' err'}`}>
            {json.ok ? '✓ Синтаксис JSON в порядке' : `✗ ${json.error}`}
            <span className="sc-json-hint">{hint}</span>
          </div>
        </>
      )}
    </div>
  );
}

export function EventTimeline({ events }: { events: EventRow[] }) {
  const sorted = events.filter((e) => Number(e.time) >= 0).sort((a, b) => Number(a.time) - Number(b.time));
  if (sorted.length === 0) return null;
  const max = Math.max(10, ...sorted.map((e) => Number(e.time)));
  return (
    <div className="ev-timeline">
      <div className="ev-timeline-track">
        {sorted.map((e, i) => (
          <div
            key={`${e.rowKey}-${i}`}
            className="ev-timeline-mark"
            style={{ left: `${Math.min(100, (Number(e.time) / max) * 100)}%`, background: EVENT_TYPE_COLOR[e.event_type] ?? '#94a3b8' }}
            title={`t=${e.time}с · ${typeLabel(e.event_type)}${e.object_id ? ` · ${e.object_id}` : ''}`}
          >
            <span className="ev-timeline-time">{e.time}с</span>
          </div>
        ))}
      </div>
      <div className="ev-timeline-axis"><span>0с</span><span>{max}с</span></div>
    </div>
  );
}

export function ScenarioModal({ scenario, equipment, competencies, onSave, onClose }: {
  scenario: ScenarioDefinition | null;
  equipment: EquipmentItem[];
  competencies: LmsCompetency[];
  onSave: (w: Parameters<typeof api.lmsSaveScenario>[1]) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(scenario?.title ?? '');
  const [description, setDescription] = useState(scenario?.description ?? '');
  const [goal, setGoal] = useState(scenario?.goal ?? '');
  const [durationMin, setDurationMin] = useState(scenario?.duration_min ?? 10);
  const [isExam, setIsExam] = useState(scenario?.is_exam ?? false);
  const [competencyCodes, setCompetencyCodes] = useState<string[]>(scenario?.competency_codes ?? []);
  const [equipmentIds, setEquipmentIds] = useState<string[]>(scenario?.equipment_ids ?? []);
  const [initialState, setInitialState] = useState(scenario?.initial_state ? JSON.stringify(scenario.initial_state, null, 2) : '{}');
  const [finalState, setFinalState] = useState(scenario?.final_state ? JSON.stringify(scenario.final_state, null, 2) : '{}');
  const [finalStateEnabled, setFinalStateEnabled] = useState(
    !!(scenario?.final_state && Object.keys(scenario.final_state).length > 0),
  );
  const [events, setEvents] = useState<EventRow[]>(
    (scenario?.events ?? []).map((e, i) => ({ ...e, rowKey: i })),
  );
  const [expectedActions, setExpectedActions] = useState<ExpRow[]>(
    (scenario?.expected_actions ?? []).map((a, i) => ({ ...a, seq: i + 1, rowKey: i })),
  );
  const [successCriteria, setSuccessCriteria] = useState<CritRow[]>(
    (scenario?.success_criteria ?? []).length
      ? (scenario?.success_criteria ?? []).map((c, i) => ({ ...c, rowKey: i }))
      : CRITERION_KEYS.map((c, i) => ({ ...c, weight: 1, rowKey: i })),
  );
  const [criticalErrors, setCriticalErrors] = useState<RestrRow[]>(
    (scenario?.critical_errors ?? []).map((r, i) => ({ ...r, rowKey: i })),
  );
  const [targetState, setTargetState] = useState<CondRow[]>(
    (scenario?.target_state ?? []).map((c, i) => ({ ...c, rowKey: i })),
  );

  const nextEvent = events.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextExp = expectedActions.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCrit = successCriteria.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCritErr = criticalErrors.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCond = targetState.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите название сценария');
    const init = tryJson(initialState);
    const fin = finalStateEnabled ? tryJson(finalState) : { ok: true, error: '' };
    if (!init.ok) return notifyToast(`Начальное состояние: ${init.error}`);
    if (!fin.ok) return notifyToast(`Финальное состояние: ${fin.error}`);
    onSave({
      title: title.trim(),
      description: description.trim(),
      goal: goal.trim(),
      duration_min: durationMin,
      is_exam: isExam,
      competency_codes: competencyCodes,
      equipment_ids: equipmentIds,
      initial_state: JSON.parse(initialState || '{}'),
      final_state: finalStateEnabled ? JSON.parse(finalState || '{}') : {},
      events: events.map(({ rowKey: _k, ...e }) => ({ ...e, time: Number(e.time) || 0, value: numOr(asString(e.value)) })),
      expected_actions: expectedActions.map(({ rowKey: _k, ...a }) => ({ ...a, value: numOr(asString(a.value)), deadline_t: deadlineNum(a.deadline_t) })),
      success_criteria: successCriteria.map(({ rowKey: _k, ...c }) => ({ ...c, weight: Number(c.weight) || 1 })),
      critical_errors: criticalErrors.map(({ rowKey: _k, ...r }) => ({ ...r, value: numOr(asString(r.value)) })),
      target_state: targetState.map(({ rowKey: _k, ...c }) => ({
        ...c,
        value: numOr(asString(c.value)),
        value2: numOr(asString(c.value2)),
      })),
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 880 }} onClick={(e) => e.stopPropagation()}>
        <div className="row-between">
          <div className="page-title" style={{ fontSize: 16 }}>
            {scenario ? `Сценарий #${scenario.id}` : 'Новый сценарий'}
          </div>
          <div className="sc-summary">
            Событий: <b>{events.length}</b> · Действий: <b>{expectedActions.length}</b> · Критериев: <b>{successCriteria.length}</b>
          </div>
        </div>

        <div className="card-title">ОБЩАЯ ИНФОРМАЦИЯ</div>
        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Название сценария *</label>
            <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Напр.: Авария на насосе Н-1" />
          </div>
          <div className="form-field">
            <label className="form-label">Длительность, мин</label>
            <input className="form-input" type="number" min={1} value={durationMin} onChange={(e) => setDurationMin(Number(e.target.value) || 10)} />
          </div>
        </div>
        <div className="form-field">
          <label className="form-label">Описание</label>
          <textarea className="form-input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">Цель для оператора</label>
          <textarea className="form-input" rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Напр.: вывести установку в нормальный режим, не допустив аварии" />
        </div>
        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Компетенции</label>
            <TagPicker options={competencyOpts(competencies)} value={competencyCodes} onChange={setCompetencyCodes} empty="Не выбрано" placeholder="+ компетенция" />
          </div>
          <div className="form-field">
            <label className="form-label">Оборудование</label>
            <TagPicker options={equipmentOpts(equipment)} value={equipmentIds} onChange={setEquipmentIds} empty="Не выбрано" placeholder="+ оборудование" />
          </div>
        </div>
        <label className="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6, textTransform: 'none' }}>
          <input type="checkbox" checked={isExam} onChange={(e) => setIsExam(e.target.checked)} /> Экзаменационный сценарий
        </label>

        <div className="sc-sep" />

        <div className="card-title">НАЧАЛЬНОЕ И ФИНАЛЬНОЕ СОСТОЯНИЕ</div>
        <div className="sc-hint" style={{ marginBottom: 4 }}>Задайте настройку оборудования на старте и к моменту завершения практики. Поля, которые не трогали, в состояние не попадают.</div>
        <StateEditor label="Начальное состояние" hint="Параметры установки на момент старта практики" equipment={equipment} value={initialState} onChange={setInitialState} />
        <label className="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6, textTransform: 'none', marginTop: 6 }}>
          <input type="checkbox" checked={finalStateEnabled} onChange={(e) => setFinalStateEnabled(e.target.checked)} />
          Финальное состояние (можно не задавать)
        </label>
        {finalStateEnabled && (
          <StateEditor label="Финальное состояние" hint="Требуемые параметры для успешного завершения" equipment={equipment} value={finalState} onChange={setFinalState} />
        )}

        <div className="sc-sep" />

        <SectionTitle title="ЦЕЛЬ — ДОСТИЖЕНИЕ РЕЗУЛЬТАТА" hint="Конкретный результат, который должен быть достигнут (проверяется физической моделью в момент завершения практики). Напр.: уровень колонны К-4 ≥ 2.5 м." />
        <div className="sc-col-head">
          <span style={{ width: 170 }}>Объект</span>
          <span style={{ width: 120 }}>Параметр</span>
          <span style={{ width: 90 }}>Операция</span>
          <span style={{ width: 90 }}>Значение</span>
          <span style={{ width: 90 }}>До (для «между»)</span>
          <span style={{ flex: 1 }}></span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {targetState.map((c) => (
            <div className="row sc-row" key={c.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <ObjectSelect equipment={equipment} width={170} value={c.object_id} onChange={(v) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, object_id: v } : x))} />
              <AttrSelect equipment={equipment} width={120} value={c.attribute} onChange={(v) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, attribute: v } : x))} />
              <select className="scenario-select" style={{ width: 90 }} value={c.relation} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, relation: e.target.value } : x))}>
                {RELATIONS.map((r) => <option key={r} value={r}>{relationLabel(r)}</option>)}
              </select>
              <input className="form-input" style={{ width: 90 }} placeholder="значение" value={asString(c.value)} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, value: e.target.value } : x))} />
              {c.relation === 'between' && (
                <input className="form-input" style={{ width: 90 }} placeholder="до" value={asString(c.value2)} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, value2: e.target.value } : x))} />
              )}
              <button className="btn btn-danger" onClick={() => setTargetState((rs) => rs.filter((x) => x.rowKey !== c.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setTargetState((rs) => [...rs, { object_id: '', attribute: 'level_m', relation: '>=', value: '', value2: '', rowKey: nextCond }])}>+ Цель (результат)</button>
        </div>

        <div className="sc-sep" />

        <SectionTitle title="СОБЫТИЯ ПО ВРЕМЕНИ" hint="Что и в какой момент происходит на установке. Цветные метки на шкале — хронология сценария." />
        <EventTimeline events={events} />
        <div className="sc-col-head">
          <span style={{ width: 60 }}>Время, с</span>
          <span style={{ width: 120 }}>Тип события</span>
          <span style={{ width: 130 }}>Объект</span>
          <span style={{ width: 100 }}>Параметр</span>
          <span style={{ width: 80 }}>Значение</span>
          <span style={{ flex: 1 }}>Сообщение оператору</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {events.map((ev) => (
            <div className="row sc-row" key={ev.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <input className="form-input" style={{ width: 60 }} type="number" min={0} placeholder="t" value={ev.time} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, time: Number(e.target.value) || 0 } : x))} />
              <select className="scenario-select" style={{ width: 120 }} title={EVENT_TYPE_HINT[ev.event_type]} value={ev.event_type} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, event_type: e.target.value } : x))}>
                {EVENT_TYPES.map((t) => <option key={t} value={t} title={EVENT_TYPE_HINT[t]}>{typeLabel(t)}</option>)}
              </select>
              <ObjectSelect equipment={equipment} width={170} value={ev.object_id} onChange={(v) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, object_id: v } : x))} />
              <AttrSelect equipment={equipment} width={100} value={ev.param} onChange={(v) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, param: v } : x))} />
              <input className="form-input" style={{ width: 80 }} placeholder="значение" value={asString(ev.value)} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, value: e.target.value } : x))} />
              <input className="form-input" style={{ flex: 1, minWidth: 140 }} placeholder="напр.: Отказ насоса Н-1" value={ev.message} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, message: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setEvents((rs) => rs.filter((x) => x.rowKey !== ev.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setEvents((rs) => [...rs, { time: 30, event_type: 'fault', object_id: '', param: '', value: '', severity: 'warning', message: '', rowKey: nextEvent }])}>+ Событие</button>
        </div>

        <div className="sc-sep" />

        <SectionTitle title="ОЖИДАЕМЫЕ ДЕЙСТВИЯ ОПЕРАТОРА" hint="Что оператор должен сделать в ходе практики. Порядок нумеруется автоматически. «Срок, с» — время на выполнение действия с начала практики; если не указано, контроль по сроку не применяется." />
        <div className="sc-col-head">
          <span style={{ width: 26 }}>№</span>
          <span style={{ width: 130 }}>Объект</span>
          <span style={{ width: 150 }}>Действие</span>
          <span style={{ width: 110 }}>Параметр</span>
          <span style={{ width: 80 }}>Значение</span>
          <span style={{ width: 70 }}>Срок, с</span>
          <span style={{ flex: 1 }}>Пояснение</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {expectedActions.map((a, idx) => (
            <div className="row sc-row" key={a.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <span className="sc-seq">{idx + 1}</span>
              <ObjectSelect equipment={equipment} width={190} value={a.object_id} onChange={(v) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, object_id: v } : x))} />
              <select className="scenario-select" style={{ width: 150 }} value={a.action_type} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, action_type: e.target.value } : x))}>
                <option value="">— действие —</option>
                {ACTION_TYPES.map((t) => <option key={t} value={t}>{actionLabel(t)}</option>)}
              </select>
              <AttrSelect equipment={equipment} width={110} value={a.attribute ?? ''} onChange={(v) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, attribute: v } : x))} />
              {isDirectionalAction(a.action_type) ? (
                <span className="sc-hint" style={{ width: 80 }}>↑/↓</span>
              ) : (
                <input className="form-input" style={{ width: 80 }} placeholder="значение" value={asString(a.value)} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, value: e.target.value } : x))} />
              )}
              <input className="form-input" style={{ width: 70 }} type="number" min={0} placeholder="не ограничено" title="Время на выполнение действия, с" value={a.deadline_t == null ? '' : String(a.deadline_t)} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, deadline_t: e.target.value === '' ? null : Number(e.target.value) } : x))} />
              <input className="form-input" style={{ flex: 1, minWidth: 140 }} placeholder="пояснение" value={a.description} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, description: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setExpectedActions((rs) => rs.filter((x) => x.rowKey !== a.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setExpectedActions((rs) => [...rs, { seq: rs.length + 1, object_id: '', action_type: 'TURN_ON', attribute: '', value: '', description: '', deadline_t: null, weight: 1, rowKey: nextExp }])}>+ Действие</button>
        </div>

        <div className="sc-sep" />

        <SectionTitle title="КРИТЕРИИ УСПЕХА" hint="По каким признакам оценивается результат оператора. Вес — вклад критерия в итоговую оценку." />
        <div className="sc-col-head">
          <span style={{ flex: 1 }}>Тип критерия</span>
          <span style={{ width: 200 }}>Название</span>
          <span style={{ width: 70 }}>Вес</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {successCriteria.map((c) => (
            <div className="row" key={c.rowKey} style={{ gap: 8 }}>
              <select className="scenario-select" style={{ flex: 1 }} value={c.key} onChange={(e) => setSuccessCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, key: e.target.value } : x))}>
                {CRITERION_KEYS.map((k) => <option key={k.key} value={k.key}>{k.title}</option>)}
              </select>
              <input className="form-input" style={{ width: 200 }} placeholder="название" value={c.title} onChange={(e) => setSuccessCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, title: e.target.value } : x))} />
              <input className="form-input" style={{ width: 70 }} placeholder="вес" value={c.weight} onChange={(e) => setSuccessCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, weight: Number(e.target.value) || 0 } : x))} />
              <button className="btn btn-danger" onClick={() => setSuccessCriteria((rs) => rs.filter((x) => x.rowKey !== c.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setSuccessCriteria((rs) => [...rs, { key: '', title: '', weight: 1, rowKey: nextCrit }])}>+ Критерий</button>
        </div>

        <div className="sc-sep" />

        <SectionTitle title="КРИТИЧЕСКИЕ ОШИБКИ" hint="Действия оператора, которые сразу приводят к провалу практики." />
        <div className="sc-col-head">
          <span style={{ width: 150 }}>Действие</span>
          <span style={{ width: 130 }}>Объект</span>
          <span style={{ flex: 1 }}>Сообщение</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {criticalErrors.map((r) => (
            <div className="row sc-row" key={r.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <select className="scenario-select" style={{ width: 150 }} value={r.action_type} onChange={(e) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, action_type: e.target.value } : x))}>
                <option value="">— действие —</option>
                {ACTION_TYPES.map((t) => <option key={t} value={t}>{actionLabel(t)}</option>)}
              </select>
              <ObjectSelect equipment={equipment} width={170} value={r.object_id} onChange={(v) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, object_id: v } : x))} />
              <input className="form-input" style={{ flex: 1, minWidth: 140 }} placeholder="напр.: Включение при открытой аварийной задвижке" value={r.message} onChange={(e) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, message: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setCriticalErrors((rs) => rs.filter((x) => x.rowKey !== r.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setCriticalErrors((rs) => [...rs, { action_type: '', object_id: '', relation: '', value: '', severity: 'critical', message: '', rowKey: nextCritErr }])}>+ Ошибка</button>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Отмена</button>
          <button className="btn btn-start" onClick={save}>Сохранить сценарий</button>
        </div>
      </div>
    </div>
  );
}
