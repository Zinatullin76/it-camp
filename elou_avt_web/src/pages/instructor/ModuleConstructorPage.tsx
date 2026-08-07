import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../api';
import type {
  Criterion,
  EquipmentItem,
  ExpectedAction,
  Lesson,
  LessonBlock,
  LmsCompetency,
  ModuleAuthoringView,
  Question,
  QuestionKind,
  RestrictionRule,
  ScenarioDefinition,
  ScenarioStatus,
  TaskCondition,
  TestConfig,
  TrainingTask,
} from '../../types';
import { Card, Chip, Empty, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';

const QUESTION_KIND_LABEL: Record<QuestionKind, string> = {
  single: 'Один вариант',
  multi: 'Несколько вариантов',
  match: 'Соответствие',
  sequence: 'Последовательность',
  object: 'Оборудование',
};

const SCENARIO_STATUS_LABEL: Record<ScenarioStatus, string> = {
  DRAFT: 'Черновик',
  REVIEW: 'На проверке',
  PUBLISHED: 'Опубликован',
  ARCHIVED: 'Архив',
};

const STATUS_FLOW: ScenarioStatus[] = ['DRAFT', 'REVIEW', 'PUBLISHED', 'ARCHIVED'];

const BLOCK_KINDS: LessonBlock['kind'][] = [
  'text',
  'image',
  'video',
  'scheme',
  'scheme_highlight',
  'equipment_card',
  'interactive_scheme',
];

const CRITERION_KEYS: { key: string; title: string }[] = [
  { key: 'sequence', title: 'Правильная последовательность' },
  { key: 'parameters', title: 'Контроль параметров' },
  { key: 'time', title: 'Время' },
  { key: 'errors', title: 'Ошибочные действия' },
  { key: 'safety', title: 'Безопасность' },
];

const ACTION_TYPES = ['TURN_ON', 'TURN_OFF', 'SET_PARAM', 'OPEN_VALVE', 'CLOSE_VALVE', 'INJECT_FAILURE', 'RESET_FAILURE'];

const EVENT_TYPES = ['fault', 'param', 'state', 'alarm', 'mode'];

const EVENT_TYPE_LABEL: Record<string, string> = {
  fault: 'Отказ',
  param: 'Параметр',
  state: 'Состояние',
  alarm: 'Авария',
  mode: 'Режим',
};

const EVENT_TYPE_HINT: Record<string, string> = {
  fault: 'Оборудование выходит из строя в этот момент',
  param: 'Значение параметра объекта меняется',
  state: 'Объект переводится в заданное состояние',
  alarm: 'Срабатывает аварийная сигнализация',
  mode: 'Установка переходит в другой режим работы',
};

const EVENT_TYPE_COLOR: Record<string, string> = {
  fault: '#f87171',
  alarm: '#fbbf24',
  param: '#38bdf8',
  state: '#a78bfa',
  mode: '#34d399',
};

const ACTION_TYPE_LABEL: Record<string, string> = {
  TURN_ON: 'Включить',
  TURN_OFF: 'Выключить',
  SET_PARAM: 'Задать параметр',
  OPEN_VALVE: 'Открыть клапан',
  CLOSE_VALVE: 'Закрыть клапан',
  INJECT_FAILURE: 'Внести отказ',
  RESET_FAILURE: 'Сбросить отказ',
};

function typeLabel(v: string): string {
  return EVENT_TYPE_LABEL[v] ?? v;
}

function actionLabel(v: string): string {
  return ACTION_TYPE_LABEL[v] ?? (v === '' ? '— действие —' : v);
}

function numOr(v: string): number | string {
  const t = v.trim();
  if (t === '') return '';
  const n = Number(t);
  return Number.isFinite(n) ? n : t;
}

function asStringArray(v: unknown): string[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.map(String);
  return [String(v)];
}

function asString(v: unknown): string {
  return v == null ? '' : String(v);
}

// ---------------------------------------------------------------------------
// Shared pickers (выпадающие списки вместо свободного ввода)
// ---------------------------------------------------------------------------

const EQUIP_TYPE_LABEL: Record<string, string> = {
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

const TARGET_ATTRS = ['running', 'position', 'fuel_flow', 'failed', 'failure_mode', 'flow_kg_s', 'temperature_c', 'pressure_bar', 'level_m'];

function equipmentOpts(equipment: EquipmentItem[]): { value: string; label: string }[] {
  return equipment.map((e) => ({ value: e.id, label: `${e.name} · ${e.id}` }));
}

function competencyOpts(competencies: LmsCompetency[]): { value: string; label: string }[] {
  return competencies.map((c) => ({ value: c.code, label: c.title ? `${c.title} (${c.code})` : c.code }));
}

function attrOptions(equipment: EquipmentItem[]): string[] {
  const s = new Set<string>(TARGET_ATTRS);
  equipment.forEach((e) => Object.keys(e.params ?? {}).forEach((p) => s.add(p)));
  return Array.from(s);
}

function TagPicker({ options, value, onChange, placeholder, empty }: {
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

function ObjectSelect({ equipment, value, onChange, width, placeholder }: {
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

function AttrSelect({ equipment, value, onChange, width }: {
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
      {known && <option value={value}>{value}</option>}
      {opts.map((a) => <option key={a} value={a}>{a}</option>)}
    </select>
  );
}

// ---------------------------------------------------------------------------
// Lesson editor
// ---------------------------------------------------------------------------

interface BlockRow extends LessonBlock {
  key: number;
}

function LessonModal({ lesson, equipment, competencies, onSave, onClose }: {
  lesson: Lesson | null;
  equipment: EquipmentItem[];
  competencies: LmsCompetency[];
  onSave: (w: { title: string; blocks: LessonBlock[]; equipment_ids: string[]; competency_codes: string[] }) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(lesson?.title ?? '');
  const [blocks, setBlocks] = useState<BlockRow[]>(
    (lesson?.blocks ?? []).length
      ? (lesson?.blocks ?? []).map((b, i) => ({ ...b, key: i }))
      : [{ kind: 'text', title: '', content: '', url: '', node_id: '', key: 0 }],
  );
  const [equipmentIds, setEquipmentIds] = useState<string[]>(lesson?.equipment_ids ?? []);
  const [competencyCodes, setCompetencyCodes] = useState<string[]>(lesson?.competency_codes ?? []);

  const nextKey = blocks.reduce((m, b) => Math.max(m, b.key), 0) + 1;
  const upd = (key: number, patch: Partial<BlockRow>) =>
    setBlocks((bs) => bs.map((b) => (b.key === key ? { ...b, ...patch } : b)));

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите название урока');
    onSave({
      title: title.trim(),
      blocks: blocks.map(({ key: _k, ...b }) => ({ ...b })),
      equipment_ids: equipmentIds,
      competency_codes: competencyCodes,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
        <div className="page-title" style={{ fontSize: 16 }}>
          {lesson ? `Урок #${lesson.id}` : 'Новый урок'}
        </div>
        <div className="form-field">
          <label className="form-label">Название</label>
          <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div className="card-title" style={{ marginBottom: 6 }}>Блоки материала</div>
        <div className="col" style={{ gap: 10 }}>
          {blocks.map((b) => (
            <div className="card" key={b.key} style={{ boxShadow: 'none' }}>
              <div className="row-between" style={{ marginBottom: 8 }}>
                <select className="scenario-select" value={b.kind} onChange={(e) => upd(b.key, { kind: e.target.value as LessonBlock['kind'] })}>
                  {BLOCK_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
                <button className="btn btn-danger" onClick={() => setBlocks((bs) => bs.filter((x) => x.key !== b.key))}>Удалить</button>
              </div>
              <div className="form-field" style={{ marginBottom: 8 }}>
                <label className="form-label">Заголовок</label>
                <input className="form-input" value={b.title} onChange={(e) => upd(b.key, { title: e.target.value })} />
              </div>
              {b.kind === 'text' || b.kind === 'scheme' || b.kind === 'scheme_highlight' ? (
                <div className="form-field" style={{ marginBottom: 8 }}>
                  <label className="form-label">Содержимое</label>
                  <textarea className="form-input" rows={3} value={b.content} onChange={(e) => upd(b.key, { content: e.target.value })} />
                </div>
              ) : null}
              {b.kind === 'image' || b.kind === 'video' || b.kind === 'scheme' ? (
                <div className="form-field" style={{ marginBottom: 8 }}>
                  <label className="form-label">URL</label>
                  <input className="form-input" value={b.url} onChange={(e) => upd(b.key, { url: e.target.value })} />
                </div>
              ) : null}
              {b.kind === 'equipment_card' || b.kind === 'scheme_highlight' || b.kind === 'interactive_scheme' ? (
                <div className="form-field">
                  <label className="form-label">Оборудование (узел схемы)</label>
                  <ObjectSelect equipment={equipment} value={b.node_id} onChange={(v) => upd(b.key, { node_id: v })} />
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <button className="btn" onClick={() => setBlocks((bs) => [...bs, { kind: 'text', title: '', content: '', url: '', node_id: '', key: nextKey }])}>
          + Добавить блок
        </button>

        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Оборудование</label>
            <TagPicker options={equipmentOpts(equipment)} value={equipmentIds} onChange={setEquipmentIds} empty="Не выбрано" placeholder="+ оборудование" />
          </div>
          <div className="form-field">
            <label className="form-label">Компетенции</label>
            <TagPicker options={competencyOpts(competencies)} value={competencyCodes} onChange={setCompetencyCodes} empty="Не выбрано" placeholder="+ компетенция" />
          </div>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Отмена</button>
          <button className="btn btn-start" onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Test editor (настройки + вопросы)
// ---------------------------------------------------------------------------

interface OptRow { key: string; label: string; correct: boolean; rowKey: number }
interface PairRow { left: string; right: string; rowKey: number }

function buildQuestionState(q: Question | null) {
  const kind: QuestionKind = q?.kind ?? 'single';
  const answer = q?.answer;
  const options = q?.options ?? [];
  if (kind === 'single' || kind === 'multi') {
    const correctSet = new Set(asStringArray(answer));
    const rows: OptRow[] = options.map((o, i) => ({
      key: asString(o.key),
      label: asString(o.label ?? o.key),
      correct: correctSet.has(asString(o.key)),
      rowKey: i,
    }));
    return { kind, opts: rows, pairs: [] as PairRow[], items: [] as string[], nodeId: '' };
  }
  if (kind === 'match') {
    const pairs = (Array.isArray(answer) && answer.length ? answer : options) as { left?: unknown; right?: unknown }[];
    return {
      kind,
      opts: [] as OptRow[],
      pairs: pairs.map((p, i) => ({ left: asString(p.left), right: asString(p.right), rowKey: i })),
      items: [] as string[],
      nodeId: '',
    };
  }
  if (kind === 'sequence') {
    const items = (Array.isArray(answer) && answer.length ? answer : options.map((o) => asString(o.label ?? o))) as unknown[];
    return { kind, opts: [] as OptRow[], pairs: [] as PairRow[], items: items.map(String), nodeId: '' };
  }
  const nodeId = Array.isArray(answer) ? asString(answer[0]) : asString(answer);
  return { kind, opts: [] as OptRow[], pairs: [] as PairRow[], items: [] as string[], nodeId };
}

function QuestionModal({ question, equipment, onSave, onClose }: {
  question: Question | null;
  equipment: EquipmentItem[];
  onSave: (w: { kind: QuestionKind; title: string; text: string; options: Record<string, unknown>[]; answer: unknown; max_score: number; penalty: number; required: boolean; hint: string }) => void;
  onClose: () => void;
}) {
  const init = useMemo(() => buildQuestionState(question), [question]);
  const [kind, setKind] = useState<QuestionKind>(init.kind);
  const [title, setTitle] = useState(question?.title ?? '');
  const [text, setText] = useState(question?.text ?? '');
  const [hint, setHint] = useState(question?.hint ?? '');
  const [maxScore, setMaxScore] = useState(question?.max_score ?? 1);
  const [penalty, setPenalty] = useState(question?.penalty ?? 0);
  const [required, setRequired] = useState(question?.required ?? true);
  const [opts, setOpts] = useState<OptRow[]>(init.opts);
  const [pairs, setPairs] = useState<PairRow[]>(init.pairs);
  const [items, setItems] = useState<string[]>(init.items);
  const [nodeId, setNodeId] = useState(init.nodeId);

  const nextOpt = opts.reduce((m, o) => Math.max(m, o.rowKey), 0) + 1;
  const nextPair = pairs.reduce((m, p) => Math.max(m, p.rowKey), 0) + 1;

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите текст вопроса');
    let options: Record<string, unknown>[] = [];
    let answer: unknown = undefined;
    if (kind === 'single') {
      const picked = opts.filter((o) => o.correct);
      options = opts.map(({ rowKey: _k, correct: _c, ...o }) => o);
      answer = picked.slice(0, 1).map((o) => o.key);
    } else if (kind === 'multi') {
      const picked = opts.filter((o) => o.correct).map((o) => o.key);
      options = opts.map(({ rowKey: _k, correct: _c, ...o }) => o);
      answer = picked;
    } else if (kind === 'match') {
      options = pairs.map(({ rowKey: _k, ...p }) => p);
      answer = pairs.map(({ rowKey: _k, ...p }) => p);
    } else if (kind === 'sequence') {
      options = items.map((it) => ({ label: it }));
      answer = items;
    } else {
      options = equipment.map((e) => ({ key: e.id, label: e.name }));
      answer = nodeId ? [nodeId] : undefined;
    }
    onSave({
      kind,
      title: title.trim(),
      text: text.trim(),
      options,
      answer,
      max_score: maxScore,
      penalty,
      required,
      hint: hint.trim(),
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 620 }} onClick={(e) => e.stopPropagation()}>
        <div className="page-title" style={{ fontSize: 16 }}>
          {question ? `Вопрос #${question.id}` : 'Новый вопрос'}
        </div>
        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Тип</label>
            <select className="scenario-select full" value={kind} onChange={(e) => setKind(e.target.value as QuestionKind)}>
              {(Object.keys(QUESTION_KIND_LABEL) as QuestionKind[]).map((k) => (
                <option key={k} value={k}>{QUESTION_KIND_LABEL[k]}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Макс. балл</label>
            <input className="form-input" type="number" step="0.5" min={0} value={maxScore} onChange={(e) => setMaxScore(Number(e.target.value) || 0)} />
          </div>
        </div>
        <div className="form-field">
          <label className="form-label">Формулировка вопроса</label>
          <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">Пояснение</label>
          <textarea className="form-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">Подсказка</label>
          <input className="form-input" value={hint} onChange={(e) => setHint(e.target.value)} />
        </div>

        {(kind === 'single' || kind === 'multi') && (
          <div className="col" style={{ gap: 8 }}>
            <div className="card-title" style={{ marginBottom: 4 }}>Варианты ответа</div>
            {opts.map((o) => (
              <div className="row" key={o.rowKey} style={{ gap: 8 }}>
                <input
                  type={kind === 'single' ? 'radio' : 'checkbox'}
                  checked={o.correct}
                  onChange={() =>
                    setOpts((os) => os.map((x) =>
                      x.rowKey === o.rowKey ? { ...x, correct: !x.correct } : kind === 'single' ? { ...x, correct: false } : x,
                    ))
                  }
                />
                <input className="form-input" style={{ flex: 1 }} placeholder="Ключ (id)" value={o.key} onChange={(e) => setOpts((os) => os.map((x) => x.rowKey === o.rowKey ? { ...x, key: e.target.value } : x))} />
                <input className="form-input" style={{ flex: 2 }} placeholder="Текст" value={o.label} onChange={(e) => setOpts((os) => os.map((x) => x.rowKey === o.rowKey ? { ...x, label: e.target.value } : x))} />
                <button className="btn btn-danger" onClick={() => setOpts((os) => os.filter((x) => x.rowKey !== o.rowKey))}>✕</button>
              </div>
            ))}
            <button className="btn" onClick={() => setOpts((os) => [...os, { key: '', label: '', correct: false, rowKey: nextOpt }])}>+ Вариант</button>
          </div>
        )}

        {kind === 'match' && (
          <div className="col" style={{ gap: 8 }}>
            <div className="card-title" style={{ marginBottom: 4 }}>Пары соответствия (лево → право)</div>
            {pairs.map((p) => (
              <div className="row" key={p.rowKey} style={{ gap: 8 }}>
                <input className="form-input" style={{ flex: 1 }} placeholder="Левая часть" value={p.left} onChange={(e) => setPairs((ps) => ps.map((x) => x.rowKey === p.rowKey ? { ...x, left: e.target.value } : x))} />
                <span>→</span>
                <input className="form-input" style={{ flex: 1 }} placeholder="Правая часть" value={p.right} onChange={(e) => setPairs((ps) => ps.map((x) => x.rowKey === p.rowKey ? { ...x, right: e.target.value } : x))} />
                <button className="btn btn-danger" onClick={() => setPairs((ps) => ps.filter((x) => x.rowKey !== p.rowKey))}>✕</button>
              </div>
            ))}
            <button className="btn" onClick={() => setPairs((ps) => [...ps, { left: '', right: '', rowKey: nextPair }])}>+ Пара</button>
          </div>
        )}

        {kind === 'sequence' && (
          <div className="col" style={{ gap: 8 }}>
            <div className="card-title" style={{ marginBottom: 4 }}>Правильный порядок (сверху вниз)</div>
            {items.map((it, i) => (
              <div className="row" key={i} style={{ gap: 8 }}>
                <span className="muted num">{i + 1}.</span>
                <input className="form-input" style={{ flex: 1 }} value={it} onChange={(e) => setItems((xs) => xs.map((x, xi) => (xi === i ? e.target.value : x)))} />
                <button className="btn" onClick={() => setItems((xs) => { const a = [...xs]; if (i > 0) [a[i - 1], a[i]] = [a[i], a[i - 1]]; return a; })}>↑</button>
                <button className="btn" onClick={() => setItems((xs) => { const a = [...xs]; if (i < a.length - 1) [a[i + 1], a[i]] = [a[i], a[i + 1]]; return a; })}>↓</button>
                <button className="btn btn-danger" onClick={() => setItems((xs) => xs.filter((_x, xi) => xi !== i))}>✕</button>
              </div>
            ))}
            <button className="btn" onClick={() => setItems((xs) => [...xs, ''])}>+ Элемент</button>
          </div>
        )}

        {kind === 'object' && (
          <div className="form-field">
            <label className="form-label">Правильный узел схемы</label>
            <select className="scenario-select full" value={nodeId} onChange={(e) => setNodeId(e.target.value)}>
              <option value="">— выберите —</option>
              {equipment.map((e) => <option key={e.id} value={e.id}>{e.name} ({e.id})</option>)}
            </select>
          </div>
        )}

        <div className="row" style={{ gap: 16 }}>
          <div className="form-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <label className="form-label" style={{ textTransform: 'none' }}>Обязательный</label>
            <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
          </div>
          <div className="form-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <label className="form-label" style={{ textTransform: 'none' }}>Штраф</label>
            <input className="form-input" type="number" step="0.5" min={0} value={penalty} onChange={(e) => setPenalty(Number(e.target.value) || 0)} style={{ width: 80 }} />
          </div>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Отмена</button>
          <button className="btn btn-start" onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}

function TestModal({ test, competencies, onSave, onClose }: {
  test: TestConfig | null;
  competencies: LmsCompetency[];
  onSave: (w: { title: string; passing_score: number; attempts: number; retry_required: boolean; shuffle: boolean; competency_codes: string[] }) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(test?.title ?? 'Контроль знаний');
  const [passing, setPassing] = useState(test?.passing_score ?? 70);
  const [attempts, setAttempts] = useState(test?.attempts ?? 0);
  const [retryRequired, setRetryRequired] = useState(test?.retry_required ?? false);
  const [shuffle, setShuffle] = useState(test?.shuffle ?? false);
  const [competencyCodes, setCompetencyCodes] = useState<string[]>(test?.competency_codes ?? []);

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите название теста');
    onSave({
      title: title.trim(),
      passing_score: passing,
      attempts,
      retry_required: retryRequired,
      shuffle,
      competency_codes: competencyCodes,
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="page-title" style={{ fontSize: 16 }}>Настройки теста</div>
        <div className="form-field">
          <label className="form-label">Название</label>
          <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Проходной балл, %</label>
            <input className="form-input" type="number" min={0} max={100} value={passing} onChange={(e) => setPassing(Number(e.target.value) || 0)} />
          </div>
          <div className="form-field">
            <label className="form-label">Попыток (0 — без ограничений)</label>
            <input className="form-input" type="number" min={0} value={attempts} onChange={(e) => setAttempts(Number(e.target.value) || 0)} />
          </div>
        </div>
        <div className="form-field">
          <label className="form-label">Компетенции</label>
          <TagPicker options={competencyOpts(competencies)} value={competencyCodes} onChange={setCompetencyCodes} empty="Не выбрано" placeholder="+ компетенция" />
        </div>
        <div className="row" style={{ gap: 16 }}>
          <label className="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6, textTransform: 'none' }}>
            <input type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} /> Перемешивать вопросы
          </label>
          <label className="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6, textTransform: 'none' }}>
            <input type="checkbox" checked={retryRequired} onChange={(e) => setRetryRequired(e.target.checked)} /> Пересдача обязательна
          </label>
        </div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Отмена</button>
          <button className="btn btn-start" onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Task editor
// ---------------------------------------------------------------------------

interface CondRow extends TaskCondition { rowKey: number }
interface RestrRow extends RestrictionRule { rowKey: number }
interface CritRow extends Criterion { rowKey: number }
interface ExpRow extends ExpectedAction { rowKey: number }

function TaskModal({ task, scenarios, moduleScenario, equipment, competencies, onSave, onClose }: {
  task: TrainingTask | null;
  scenarios: { id: string; name: string }[];
  moduleScenario: ScenarioDefinition | null;
  equipment: EquipmentItem[];
  competencies: LmsCompetency[];
  onSave: (w: Parameters<typeof api.lmsSaveTask>[1]) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(task?.title ?? '');
  const [goal, setGoal] = useState(task?.goal ?? '');
  const [scenarioId, setScenarioId] = useState(task?.scenario_id ?? '');
  const [durationMin, setDurationMin] = useState(task?.duration_min ?? 10);
  const [enabled, setEnabled] = useState(task?.enabled ?? true);
  const [competencyCodes, setCompetencyCodes] = useState<string[]>(task?.competency_codes ?? []);
  const [equipmentIds, setEquipmentIds] = useState<string[]>(task?.equipment_ids ?? []);
  const [targetState, setTargetState] = useState<CondRow[]>(
    (task?.target_state ?? []).map((c, i) => ({ ...c, rowKey: i })),
  );
  const [restrictions, setRestrictions] = useState<RestrRow[]>(
    (task?.restrictions ?? []).map((r, i) => ({ ...r, rowKey: i })),
  );
  const [criteria, setCriteria] = useState<CritRow[]>(
    (task?.criteria ?? []).length
      ? (task?.criteria ?? []).map((c, i) => ({ ...c, rowKey: i }))
      : CRITERION_KEYS.map((c, i) => ({ ...c, weight: 1, rowKey: i })),
  );
  const [expectedActions, setExpectedActions] = useState<ExpRow[]>(
    (task?.expected_actions ?? []).map((a, i) => ({ ...a, seq: i + 1, rowKey: i })),
  );
  const [criticalErrors, setCriticalErrors] = useState<RestrRow[]>(
    (task?.critical_errors ?? []).map((r, i) => ({ ...r, rowKey: i })),
  );

  const nextCond = targetState.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextRestr = restrictions.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCrit = criteria.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextExp = expectedActions.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCritErr = criticalErrors.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите название задания');
    onSave({
      title: title.trim(),
      goal: goal.trim(),
      scenario_id: scenarioId,
      duration_min: durationMin,
      enabled,
      competency_codes: competencyCodes,
      equipment_ids: equipmentIds,
      target_state: targetState.map(({ rowKey: _k, ...c }) => ({ ...c, value: numOr(asString(c.value)) })),
      restrictions: restrictions.map(({ rowKey: _k, ...r }) => ({ ...r, value: numOr(asString(r.value)) })),
      criteria: criteria.map(({ rowKey: _k, ...c }) => ({ ...c, weight: Number(c.weight) || 1 })),
      expected_actions: expectedActions.map(({ rowKey: _k, ...a }) => ({ ...a, value: numOr(asString(a.value)) })),
      critical_errors: criticalErrors.map(({ rowKey: _k, ...r }) => ({ ...r, value: numOr(asString(r.value)) })),
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 760 }} onClick={(e) => e.stopPropagation()}>
        <div className="page-title" style={{ fontSize: 16 }}>
          {task ? `Задание #${task.id}` : 'Новое практическое задание'}
        </div>
        <div className="form-field">
          <label className="form-label">Название</label>
          <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="form-field">
          <label className="form-label">Цель</label>
          <textarea className="form-input" rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} />
        </div>
        <div className="settings-grid">
          <div className="form-field">
            <label className="form-label">Сценарий</label>
            <select className="scenario-select full" value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
              <option value="">— без сценария —</option>
              {moduleScenario && <option value={`LMS-${moduleScenario.id}`}>Сценарий модуля: {moduleScenario.title}</option>}
              {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name || s.id}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Длительность, мин</label>
            <input className="form-input" type="number" min={1} value={durationMin} onChange={(e) => setDurationMin(Number(e.target.value) || 10)} />
          </div>
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
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Задание активно
        </label>

        <div className="card-title" style={{ marginTop: 4 }}>Целевое состояние (target_state)</div>
        <div className="col" style={{ gap: 6 }}>
          {targetState.map((c) => (
            <div className="row" key={c.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <ObjectSelect equipment={equipment} width={150} value={c.object_id} onChange={(v) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, object_id: v } : x))} />
              <AttrSelect equipment={equipment} width={120} value={c.attribute} onChange={(v) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, attribute: v } : x))} />
              <select className="scenario-select" value={c.relation} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, relation: e.target.value } : x))}>
                {['==', '!=', '>', '<', '>=', '<=', 'between'].map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <input className="form-input" style={{ width: 90 }} placeholder="значение" value={asString(c.value)} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, value: e.target.value } : x))} />
              {c.relation === 'between' && (
                <input className="form-input" style={{ width: 90 }} placeholder="до" value={asString(c.value2)} onChange={(e) => setTargetState((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, value2: e.target.value } : x))} />
              )}
              <button className="btn btn-danger" onClick={() => setTargetState((rs) => rs.filter((x) => x.rowKey !== c.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setTargetState((rs) => [...rs, { object_id: '', attribute: 'running', relation: '==', value: 'true', value2: '', rowKey: nextCond }])}>+ Условие</button>
        </div>

        <div className="card-title" style={{ marginTop: 10 }}>Критерии оценки</div>
        <div className="col" style={{ gap: 6 }}>
          {criteria.map((c) => (
            <div className="row" key={c.rowKey} style={{ gap: 8 }}>
              <select className="scenario-select" style={{ flex: 1 }} value={c.key} onChange={(e) => setCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, key: e.target.value } : x))}>
                {CRITERION_KEYS.map((k) => <option key={k.key} value={k.key}>{k.title}</option>)}
              </select>
              <input className="form-input" style={{ width: 100 }} placeholder="название" value={c.title} onChange={(e) => setCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, title: e.target.value } : x))} />
              <input className="form-input" style={{ width: 70 }} placeholder="вес" value={c.weight} onChange={(e) => setCriteria((rs) => rs.map((x) => x.rowKey === c.rowKey ? { ...x, weight: Number(e.target.value) || 0 } : x))} />
              <button className="btn btn-danger" onClick={() => setCriteria((rs) => rs.filter((x) => x.rowKey !== c.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setCriteria((rs) => [...rs, { key: '', title: '', weight: 1, rowKey: nextCrit }])}>+ Критерий</button>
        </div>

        <div className="card-title" style={{ marginTop: 10 }}>Ожидаемые действия (expected_actions)</div>
        <div className="col" style={{ gap: 6 }}>
          {expectedActions.map((a) => (
            <div className="row" key={a.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <ObjectSelect equipment={equipment} width={130} value={a.object_id} onChange={(v) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, object_id: v } : x))} />
              <select className="scenario-select" value={a.action_type} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, action_type: e.target.value } : x))}>
                <option value="">— действие —</option>
                {ACTION_TYPES.map((t) => <option key={t} value={t}>{actionLabel(t)}</option>)}
              </select>
              <input className="form-input" style={{ width: 80 }} placeholder="знач." value={asString(a.value)} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, value: e.target.value } : x))} />
              <input className="form-input" style={{ flex: 1 }} placeholder="описание" value={a.description} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, description: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setExpectedActions((rs) => rs.filter((x) => x.rowKey !== a.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setExpectedActions((rs) => [...rs, { seq: rs.length + 1, object_id: '', action_type: 'TURN_ON', value: '', description: '', deadline_t: null, weight: 1, rowKey: nextExp }])}>+ Действие</button>
        </div>

        <div className="card-title" style={{ marginTop: 10 }}>Запрещённые действия (restrictions)</div>
        <div className="col" style={{ gap: 6 }}>
          {restrictions.map((r) => (
            <div className="row" key={r.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <select className="scenario-select" value={r.action_type} onChange={(e) => setRestrictions((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, action_type: e.target.value } : x))}>
                <option value="">— действие —</option>
                {ACTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <ObjectSelect equipment={equipment} width={140} value={r.object_id} onChange={(v) => setRestrictions((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, object_id: v } : x))} />
              <input className="form-input" style={{ width: 90 }} placeholder="знач." value={asString(r.value)} onChange={(e) => setRestrictions((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, value: e.target.value } : x))} />
              <select className="scenario-select" value={r.severity} onChange={(e) => setRestrictions((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, severity: e.target.value } : x))}>
                <option value="warning">warning</option>
                <option value="critical">critical</option>
              </select>
              <input className="form-input" style={{ flex: 1 }} placeholder="сообщение" value={r.message} onChange={(e) => setRestrictions((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, message: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setRestrictions((rs) => rs.filter((x) => x.rowKey !== r.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setRestrictions((rs) => [...rs, { action_type: 'INJECT_FAILURE', object_id: '', relation: '', value: '', severity: 'warning', message: '', rowKey: nextRestr }])}>+ Ограничение</button>
        </div>

        <div className="card-title" style={{ marginTop: 10 }}>Критические ошибки (critical_errors)</div>
        <div className="col" style={{ gap: 6 }}>
          {criticalErrors.map((r) => (
            <div className="row" key={r.rowKey} style={{ gap: 6, flexWrap: 'wrap' }}>
              <select className="scenario-select" value={r.action_type} onChange={(e) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, action_type: e.target.value } : x))}>
                <option value="">— действие —</option>
                {ACTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <ObjectSelect equipment={equipment} width={130} value={r.object_id} onChange={(v) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, object_id: v } : x))} />
              <input className="form-input" style={{ flex: 1 }} placeholder="сообщение" value={r.message} onChange={(e) => setCriticalErrors((rs) => rs.map((x) => x.rowKey === r.rowKey ? { ...x, message: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setCriticalErrors((rs) => rs.filter((x) => x.rowKey !== r.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setCriticalErrors((rs) => [...rs, { action_type: '', object_id: '', relation: '', value: '', severity: 'critical', message: '', rowKey: nextCritErr }])}>+ Ошибка</button>
        </div>

        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Отмена</button>
          <button className="btn btn-start" onClick={save}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scenario editor
// ---------------------------------------------------------------------------

type EventRow = ScenarioDefinition['events'][number] & { rowKey: number };

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="sc-section">
      <div className="card-title">{title}</div>
      <div className="sc-hint">{hint}</div>
    </div>
  );
}

function tryJson(s: string): { ok: boolean; error: string } {
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

function StateEditor({ label, hint, equipment, value, onChange }: {
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

function EventTimeline({ events }: { events: EventRow[] }) {
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

function ScenarioModal({ scenario, equipment, competencies, onSave, onClose }: {
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

  const nextEvent = events.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextExp = expectedActions.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCrit = successCriteria.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;
  const nextCritErr = criticalErrors.reduce((m, r) => Math.max(m, r.rowKey), 0) + 1;

  const save = () => {
    if (!title.trim()) return notifyToast('Укажите название сценария');
    const init = tryJson(initialState);
    const fin = tryJson(finalState);
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
      final_state: JSON.parse(finalState || '{}'),
      events: events.map(({ rowKey: _k, ...e }) => ({ ...e, time: Number(e.time) || 0, value: numOr(asString(e.value)) })),
      expected_actions: expectedActions.map(({ rowKey: _k, ...a }) => ({ ...a, value: numOr(asString(a.value)) })),
      success_criteria: successCriteria.map(({ rowKey: _k, ...c }) => ({ ...c, weight: Number(c.weight) || 1 })),
      critical_errors: criticalErrors.map(({ rowKey: _k, ...r }) => ({ ...r, value: numOr(asString(r.value)) })),
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
        <StateEditor label="Финальное состояние" hint="Требуемые параметры для успешного завершения" equipment={equipment} value={finalState} onChange={setFinalState} />

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
              <input className="form-input" style={{ width: 100 }} placeholder="параметр" value={ev.param} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, param: e.target.value } : x))} />
              <input className="form-input" style={{ width: 80 }} placeholder="значение" value={asString(ev.value)} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, value: e.target.value } : x))} />
              <input className="form-input" style={{ flex: 1, minWidth: 140 }} placeholder="напр.: Отказ насоса Н-1" value={ev.message} onChange={(e) => setEvents((rs) => rs.map((x) => x.rowKey === ev.rowKey ? { ...x, message: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setEvents((rs) => rs.filter((x) => x.rowKey !== ev.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setEvents((rs) => [...rs, { time: 30, event_type: 'fault', object_id: '', param: '', value: '', severity: 'warning', message: '', rowKey: nextEvent }])}>+ Событие</button>
        </div>

        <div className="sc-sep" />

        <SectionTitle title="ОЖИДАЕМЫЕ ДЕЙСТВИЯ ОПЕРАТОРА" hint="Что оператор должен сделать в ходе практики. Порядок нумеруется автоматически." />
        <div className="sc-col-head">
          <span style={{ width: 26 }}>№</span>
          <span style={{ width: 130 }}>Объект</span>
          <span style={{ width: 150 }}>Действие</span>
          <span style={{ width: 80 }}>Значение</span>
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
              <input className="form-input" style={{ width: 80 }} placeholder="значение" value={asString(a.value)} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, value: e.target.value } : x))} />
              <input className="form-input" style={{ flex: 1, minWidth: 140 }} placeholder="пояснение" value={a.description} onChange={(e) => setExpectedActions((rs) => rs.map((x) => x.rowKey === a.rowKey ? { ...x, description: e.target.value } : x))} />
              <button className="btn btn-danger" onClick={() => setExpectedActions((rs) => rs.filter((x) => x.rowKey !== a.rowKey))}>✕</button>
            </div>
          ))}
          <button className="btn" onClick={() => setExpectedActions((rs) => [...rs, { seq: rs.length + 1, object_id: '', action_type: 'TURN_ON', value: '', description: '', deadline_t: null, weight: 1, rowKey: nextExp }])}>+ Действие</button>
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'lesson', label: 'Уроки' },
  { id: 'test', label: 'Тест' },
  { id: 'task', label: 'Задание' },
  { id: 'scenario', label: 'Сценарий' },
];

export default function ModuleConstructorPage() {
  const { moduleId } = useParams<{ moduleId: string }>();
  const id = Number(moduleId);
  const view = useAsync<ModuleAuthoringView>(() => api.lmsAuthoringModule(id), [id]);
  const equipment = useAsync<EquipmentItem[]>(() => api.lmsAuthoringEquipment(), []);
  const competencies = useAsync<LmsCompetency[]>(() => api.lmsCompetencies(), []);
  const scenarios = useAsync<{ id: string; name: string }[]>(() => api.lmsScenarios(), []);

  const [tab, setTab] = useState('lesson');
  const [lessonModal, setLessonModal] = useState<{ lesson: Lesson | null } | null>(null);
  const [testModal, setTestModal] = useState(false);
  const [questionModal, setQuestionModal] = useState<{ question: Question | null } | null>(null);
  const [taskModal, setTaskModal] = useState(false);
  const [scenarioModal, setScenarioModal] = useState(false);

  if (view.loading && !view.data) return <Loader />;
  if (view.error && !view.data) return <Err text={view.error} />;

  const data = view.data;
  const refresh = view.reload;
  const module = data?.module;
  const lessons = data?.lessons ?? [];
  const test = data?.test ?? null;
  const task = data?.task ?? null;
  const scenario = data?.scenario ?? null;

  const notifyError = (e: unknown) => notifyToast(`Ошибка: ${e instanceof Error ? e.message : e}`);

  const togglePublish = async () => {
    try {
      await api.lmsPublishModule(id, !module?.published);
      notifyToast(module?.published ? 'Модуль снят с публикации' : 'Модуль опубликован');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const saveLesson = async (w: { title: string; blocks: LessonBlock[]; equipment_ids: string[]; competency_codes: string[] }) => {
    try {
      if (lessonModal?.lesson?.id) {
        await api.lmsUpdateLesson(lessonModal.lesson.id, w);
        notifyToast('Урок обновлён');
      } else {
        await api.lmsCreateLesson(id, w);
        notifyToast('Урок создан');
      }
      setLessonModal(null);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const deleteLesson = async (lessonId: number) => {
    if (!window.confirm(`Удалить урок #${lessonId}?`)) return;
    try {
      await api.lmsDeleteLesson(lessonId);
      notifyToast('Урок удалён');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const saveTest = async (w: { title: string; passing_score: number; attempts: number; retry_required: boolean; shuffle: boolean; competency_codes: string[] }) => {
    try {
      await api.lmsSaveTest(id, w);
      notifyToast('Тест сохранён');
      setTestModal(false);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const deleteTest = async () => {
    if (!test?.id) return;
    if (!window.confirm('Удалить тест вместе с вопросами?')) return;
    try {
      await api.lmsDeleteTest(test.id);
      notifyToast('Тест удалён');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const saveQuestion = async (w: { kind: QuestionKind; title: string; text: string; options: Record<string, unknown>[]; answer: unknown; max_score: number; penalty: number; required: boolean; hint: string }) => {
    if (!test?.id) return;
    try {
      if (questionModal?.question?.id) {
        await api.lmsUpdateQuestion(questionModal.question.id, w);
        notifyToast('Вопрос обновлён');
      } else {
        await api.lmsCreateQuestion(test.id, w);
        notifyToast('Вопрос добавлен');
      }
      setQuestionModal(null);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const deleteQuestion = async (qid: number) => {
    if (!window.confirm(`Удалить вопрос #${qid}?`)) return;
    try {
      await api.lmsDeleteQuestion(qid);
      notifyToast('Вопрос удалён');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const saveTask = async (w: Parameters<typeof api.lmsSaveTask>[1]) => {
    try {
      await api.lmsSaveTask(id, w);
      notifyToast('Задание сохранено');
      setTaskModal(false);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const deleteTask = async () => {
    if (!task?.id) return;
    if (!window.confirm('Удалить практическое задание?')) return;
    try {
      await api.lmsDeleteTask(task.id);
      notifyToast('Задание удалено');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const saveScenario = async (w: Parameters<typeof api.lmsSaveScenario>[1]) => {
    try {
      await api.lmsSaveScenario(id, w);
      notifyToast('Сценарий сохранён');
      setScenarioModal(false);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const deleteScenario = async () => {
    if (!scenario?.id) return;
    if (!window.confirm('Удалить сценарий?')) return;
    try {
      await api.lmsDeleteScenario(scenario.id);
      notifyToast('Сценарий удалён');
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const setStatus = async (status: ScenarioStatus) => {
    if (!scenario?.id) return;
    try {
      await api.lmsSetScenarioStatus(scenario.id, status);
      notifyToast(`Статус сценария: ${SCENARIO_STATUS_LABEL[status]}`);
      await refresh();
    } catch (e) { notifyError(e); }
  };

  const statusIndex = scenario ? STATUS_FLOW.indexOf(scenario.status) : -1;
  const nextStatus = statusIndex >= 0 && statusIndex < STATUS_FLOW.length - 1 ? STATUS_FLOW[statusIndex + 1] : null;

  return (
    <Page
      title={`Конструктор модуля #${id}`}
      subtitle={module?.title || 'Содержание учебного модуля'}
      actions={
        <>
          <button className="btn" onClick={() => void refresh()}>Обновить</button>
          <button className="btn btn-ghost" onClick={() => window.open(`/study/${id}`, '_blank')}>Просмотр оператором</button>
          {module && (
            <button className={module.published ? 'btn btn-stop' : 'btn btn-start'} onClick={() => void togglePublish()}>
              {module.published ? 'Снять с публикации' : 'Опубликовать'}
            </button>
          )}
        </>
      }
    >
      <div className="row-between" style={{ flexWrap: 'wrap' }}>
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={`tab${t.id === tab ? ' on' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
        <Chip tone={module?.published ? 'ok' : 'warn'}>{module?.published ? 'Опубликован' : 'Не опубликован'}</Chip>
      </div>

      {tab === 'lesson' && (
        <Card title="Теория (уроки)" actions={
          <button className="btn btn-start" onClick={() => setLessonModal({ lesson: null })}>Новый урок</button>
        }>
          {lessons.length === 0 ? (
            <Empty text="Уроков нет — создайте первый урок" />
          ) : (
            <div className="col" style={{ gap: 8 }}>
              {lessons.map((l) => (
                <div className="module-row" key={l.id}>
                  <div className="module-row-main">
                    <div className="module-row-title">{l.seq}. {l.title}</div>
                    <div className="module-row-sub">
                      Блоков: {l.blocks.length} · Оборудование: {l.equipment_ids.join(', ') || '—'} · Компетенции: {l.competency_codes.join(', ') || '—'}
                    </div>
                  </div>
                  <button className="btn" onClick={() => setLessonModal({ lesson: l })}>Изменить</button>
                  <button className="btn btn-danger" onClick={() => l.id != null && void deleteLesson(l.id)}>Удалить</button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === 'test' && (
        <Card
          title="Тест (контроль знаний)"
          actions={
            <>
              {test && <button className="btn btn-danger" onClick={() => void deleteTest()}>Удалить тест</button>}
              <button className="btn btn-start" onClick={() => setTestModal(true)}>
                {test ? 'Изменить тест' : 'Создать тест'}
              </button>
            </>
          }
        >
          {!test ? (
            <Empty text="Тест не создан" />
          ) : (
            <>
              <div className="row-between" style={{ marginBottom: 12 }}>
                <span className="muted">{test.title} · Проходной балл: {test.passing_score}% · Вопросов: {test.questions.length}</span>
                <div className="row" style={{ gap: 6 }}>
                  {test.shuffle && <Chip tone="accent">перемешивание</Chip>}
                  {test.retry_required && <Chip tone="warn">пересдача</Chip>}
                  <Chip tone="muted">попыток: {test.attempts || '∞'}</Chip>
                </div>
              </div>
              {test.questions.length === 0 ? (
                <Empty text="Вопросов нет" />
              ) : (
                <div className="col" style={{ gap: 8 }}>
                  {test.questions.map((q) => (
                    <div className="module-row" key={q.id}>
                      <div className="module-row-main">
                        <div className="module-row-title">
                          {q.seq}. {q.title} <Chip tone="accent">{QUESTION_KIND_LABEL[q.kind]}</Chip>
                        </div>
                        <div className="module-row-sub">
                          {q.text || '—'} · {q.max_score} б. {q.required ? '' : '· необязательный'}
                        </div>
                      </div>
                      <button className="btn" onClick={() => setQuestionModal({ question: q })}>Изменить</button>
                      <button className="btn btn-danger" onClick={() => q.id != null && void deleteQuestion(q.id)}>Удалить</button>
                    </div>
                  ))}
                </div>
              )}
              <button className="btn btn-start" style={{ marginTop: 12 }} onClick={() => setQuestionModal({ question: null })}>+ Вопрос</button>
            </>
          )}
        </Card>
      )}

      {tab === 'task' && (
        <Card
          title="Практическое задание"
          actions={
            <>
              {task && <button className="btn btn-danger" onClick={() => void deleteTask()}>Удалить задание</button>}
              <button className="btn btn-start" onClick={() => setTaskModal(true)}>
                {task ? 'Изменить задание' : 'Создать задание'}
              </button>
            </>
          }
        >
          {!task ? (
            <Empty text="Практическое задание не создано" />
          ) : (
            <div className="col" style={{ gap: 8 }}>
              <div className="module-row">
                <div className="module-row-main">
                  <div className="module-row-title">
                    {task.title} {task.enabled ? <Chip tone="ok">активно</Chip> : <Chip tone="bad">отключено</Chip>}
                  </div>
                  <div className="module-row-sub">
                    Сценарий: {task.scenario_id || '—'} · ⏱ {task.duration_min} мин
                  </div>
                </div>
              </div>
              {task.goal && <p className="muted" style={{ margin: 0 }}>{task.goal}</p>}
              <div className="settings-grid">
                <div>
                  <div className="card-title">Целевое состояние</div>
                  {task.target_state.length === 0 ? <div className="muted">—</div> : task.target_state.map((c, i) => (
                    <div key={i} className="muted" style={{ fontSize: 12 }}>
                      {c.object_id}.{c.attribute} {c.relation} {asString(c.value)}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="card-title">Критерии</div>
                  {task.criteria.length === 0 ? <div className="muted">—</div> : task.criteria.map((c, i) => (
                    <div key={i} className="muted" style={{ fontSize: 12 }}>{c.title}: ×{c.weight}</div>
                  ))}
                </div>
              </div>
              <div>
                <div className="card-title">Ожидаемые действия</div>
                {task.expected_actions.length === 0 ? <div className="muted">—</div> : task.expected_actions.map((a, i) => (
                  <div key={i} className="muted" style={{ fontSize: 12 }}>
                    {i + 1}. {a.action_type} → {a.object_id} {a.value != null && asString(a.value) !== '' ? `=${asString(a.value)}` : ''} {a.description ? `(${a.description})` : ''}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === 'scenario' && (
        <Card
          title="Сценарий"
          actions={
            <>
              {scenario && <button className="btn btn-danger" onClick={() => void deleteScenario()}>Удалить сценарий</button>}
              <button className="btn btn-start" onClick={() => setScenarioModal(true)}>
                {scenario ? 'Изменить сценарий' : 'Создать сценарий'}
              </button>
            </>
          }
        >
          {!scenario ? (
            <Empty text="Сценарий не создан" />
          ) : (
            <>
              <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                {STATUS_FLOW.map((st) => (
                  <button
                    key={st}
                    className={`btn ${st === scenario.status ? 'btn-active' : ''}`}
                    onClick={() => void setStatus(st)}
                    disabled={scenario.status === st}
                  >
                    {SCENARIO_STATUS_LABEL[st]}
                  </button>
                ))}
                {nextStatus && (
                  <button className="btn btn-start" onClick={() => void setStatus(nextStatus)}>
                    Перевести в «{SCENARIO_STATUS_LABEL[nextStatus]}»
                  </button>
                )}
              </div>
              <div className="module-row" style={{ marginBottom: 8 }}>
                <div className="module-row-main">
                  <div className="module-row-title">
                    {scenario.title} {scenario.is_exam ? <Chip tone="bad">экзамен</Chip> : <Chip tone="ok">практика</Chip>}
                  </div>
                  <div className="module-row-sub">
                    ⏱ {scenario.duration_min} мин · Событий: {scenario.events.length} · Действий: {scenario.expected_actions.length} · Критериев: {scenario.success_criteria.length} · Крит. ошибок: {scenario.critical_errors.length}
                  </div>
                </div>
              </div>
              {scenario.description && <p className="muted" style={{ margin: 0 }}>{scenario.description}</p>}
              {scenario.goal && <p className="muted" style={{ margin: 0 }}>Цель: {scenario.goal}</p>}
              {scenario.events.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div className="sc-hint" style={{ marginBottom: 6 }}>Хронология событий сценария:</div>
                  <EventTimeline events={(scenario.events ?? []).map((e, i) => ({ ...e, rowKey: i }))} />
                </div>
              )}
              <div className="col" style={{ gap: 4, marginTop: 8 }}>
                {scenario.events.map((ev, i) => (
                  <div key={i} className="muted" style={{ fontSize: 12 }}>
                    t={ev.time}с · {typeLabel(ev.event_type)} → {ev.object_id} {ev.param && `(${ev.param})`} {asString(ev.value) !== '' && ` = ${asString(ev.value)}`} {ev.message ? `· ${ev.message}` : ''}
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {lessonModal && (
        <LessonModal
          lesson={lessonModal.lesson}
          equipment={equipment.data ?? []}
          competencies={competencies.data ?? []}
          onSave={(w) => void saveLesson(w)}
          onClose={() => setLessonModal(null)}
        />
      )}

      {testModal && <TestModal test={test} competencies={competencies.data ?? []} onSave={(w) => void saveTest(w)} onClose={() => setTestModal(false)} />}

      {questionModal && (
        <QuestionModal
          question={questionModal.question}
          equipment={equipment.data ?? []}
          onSave={(w) => void saveQuestion(w)}
          onClose={() => setQuestionModal(null)}
        />
      )}

      {taskModal && (
        <TaskModal
          task={task}
          scenarios={scenarios.data ?? []}
          moduleScenario={scenario}
          equipment={equipment.data ?? []}
          competencies={competencies.data ?? []}
          onSave={(w) => void saveTask(w)}
          onClose={() => setTaskModal(false)}
        />
      )}

      {scenarioModal && (
        <ScenarioModal
          scenario={scenario}
          equipment={equipment.data ?? []}
          competencies={competencies.data ?? []}
          onSave={(w) => void saveScenario(w)}
          onClose={() => setScenarioModal(false)}
        />
      )}
    </Page>
  );
}
