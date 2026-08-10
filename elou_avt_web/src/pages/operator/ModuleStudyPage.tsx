import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api';
import { useAuth } from '../../auth';
import type {
  AssessmentView,
  EquipmentItem,
  ModuleStudy,
  Question,
  QuestionKind,
  TestConfig,
} from '../../types';
import ScadaScheme from '../../scada/ScadaScheme';
import { useSimulation } from '../../lms/sim';
import { actionLabel, attrLabel } from '../../lms/scenarioEditor';
import {
  Bar,
  Card,
  Chip,
  Empty,
  Err,
  Loader,
  Page,
  Score,
  fmtDur,
  notifyToast,
  useAsync,
} from '../../lms/ui';

const QUESTION_KIND_LABEL: Record<QuestionKind, string> = {
  single: 'Один вариант',
  multi: 'Несколько вариантов',
  match: 'Соответствие',
  sequence: 'Последовательность',
  object: 'Оборудование',
};

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------------------------------------------------------------------------
// Практика на физическом ядре (полноэкранная SCADA-сессия)
// ---------------------------------------------------------------------------

function PracticeFrame({ moduleId, onDone }: {
  moduleId: number;
  onDone: (a: AssessmentView) => void;
}) {
  const sim = useSimulation();
  const { user } = useAuth();
  const [sessionId, setSessionId] = useState('');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const started = useRef(false);
  const readySession = useRef('');

  const run = async () => {
    if (started.current) return;
    started.current = true;
    setError('');
    setReady(false);
    readySession.current = '';
    try {
      const s = await api.lmsPracticeStart(moduleId);
      setSessionId(s.session_id);
      await sim.refresh();
    } catch (e) {
      started.current = false;
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const markReady = async () => {
    if (!sessionId || readySession.current === sessionId) return;
    readySession.current = sessionId;
    try {
      await api.lmsPracticeReady(sessionId);
      await sim.refresh();
      setReady(true);
    } catch (e) {
      readySession.current = '';
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const finish = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      const a = await api.lmsPracticeFinish(sessionId);
      onDone(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <div className="practice-frame">
      <div className="practice-bar">
        <span className="practice-bar-title">Практика по модулю</span>
        {sessionId && <span className="muted mono">сессия {sessionId.slice(0, 12)}</span>}
        <span className="grow" />
        <span className={`chip ${sim.connected ? 'chip-ok' : 'chip-bad'}`}>
          <span className="dot" /> {sim.connected ? 'LIVE' : 'НЕТ СВЯЗИ'}
        </span>
        <span className="chip chip-info">t = {(sim.live?.simulation_time ?? 0).toFixed(0)} с</span>
        <span className={`chip ${(sim.live?.alarms?.length ?? 0) > 0 ? 'chip-alarm' : 'chip-ok'}`}>
          ⚠ {(sim.live?.alarms?.length ?? 0)} аварий
        </span>
        <button className="btn btn-start" disabled={busy || !sessionId || !ready} onClick={() => void finish()}>
          Завершить задание
        </button>
      </div>
      {error ? (
        <div style={{ padding: 20 }}>
          <Err text={error} />
          <button className="btn" style={{ marginTop: 10 }} onClick={() => void run()}>Повторить запуск</button>
        </div>
      ) : (
        <div className="mnemo-wrap">
          <ScadaScheme
            key={sessionId}
            live={sim.live}
            user={user?.username}
            onReady={() => void markReady()}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Тест
// ---------------------------------------------------------------------------

function TestRunner({ test, equipment, onDone }: {
  test: TestConfig;
  equipment: EquipmentItem[];
  onDone: (a: AssessmentView) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const startedAt = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt.current) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  const questions = useMemo(() => (test.shuffle ? shuffle(test.questions) : test.questions), [test]);

  const setAnswer = (qid: string, value: unknown) => setAnswers((a) => ({ ...a, [qid]: value }));

  const setMulti = (qid: string, key: string, on: boolean) => {
    setAnswers((a) => {
      const cur = Array.isArray(a[qid]) ? (a[qid] as string[]) : [];
      return { ...a, [qid]: on ? [...cur, key] : cur.filter((k) => k !== key) };
    });
  };

  const setSequence = (qid: string, label: string, order: number) => {
    setAnswers((a) => {
      const prev = (a[qid] as Record<string, number>) ?? {};
      return { ...a, [qid]: { ...prev, [label]: order } };
    });
  };

  const submit = async () => {
    setBusy(true);
    try {
      const duration = (Date.now() - startedAt.current) / 1000;
      const payload: Record<string, unknown> = {};
      for (const q of questions) {
        if (q.id == null) continue;
        const qid = String(q.id);
        if (q.kind === 'sequence') {
          const orderMap = (answers[qid] as Record<string, number>) ?? {};
          const labels = (q.options ?? []).map((o) => String(o.label ?? o.key));
          payload[qid] = labels.slice().sort((x, y) => (orderMap[x] ?? 999) - (orderMap[y] ?? 999));
        } else {
          payload[qid] = answers[qid];
        }
      }
      const a = await api.lmsSubmitTest(test.id ?? 0, payload, duration);
      onDone(a);
    } catch (e) {
      notifyToast(`Ошибка: ${e instanceof Error ? e.message : e}`);
      setBusy(false);
    }
  };

  const answered = questions.filter((q) => {
    const v = q.id != null ? answers[String(q.id)] : undefined;
    return v !== undefined && (typeof v !== 'object' || Object.keys(v as object).length > 0);
  }).length;

  const renderQuestion = (q: Question) => {
    const qid = q.id != null ? String(q.id) : '';
    const options = q.options ?? [];
    if (q.kind === 'single') {
      return (
        <div className="col" style={{ gap: 6 }}>
          {options.map((o) => {
            const key = String(o.key ?? '');
            return (
              <label key={key} className="module-row" style={{ cursor: 'pointer', alignItems: 'center', gap: 8 }}>
                <input type="radio" name={qid} checked={answers[qid] === key} onChange={() => setAnswer(qid, key)} />
                <span>{String(o.label ?? o.key)}</span>
              </label>
            );
          })}
        </div>
      );
    }
    if (q.kind === 'multi') {
      return (
        <div className="col" style={{ gap: 6 }}>
          {options.map((o) => {
            const key = String(o.key ?? '');
            const cur = Array.isArray(answers[qid]) ? (answers[qid] as string[]) : [];
            return (
              <label key={key} className="module-row" style={{ cursor: 'pointer', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" checked={cur.includes(key)} onChange={(e) => setMulti(qid, key, e.target.checked)} />
                <span>{String(o.label ?? o.key)}</span>
              </label>
            );
          })}
        </div>
      );
    }
    if (q.kind === 'match') {
      const pairs = options.map((o) => ({ left: String(o.left ?? ''), right: String(o.right ?? '') }));
      const rights = [...new Set(pairs.map((p) => p.right))];
      const current = (answers[qid] as Record<string, string>) ?? {};
      return (
        <div className="col" style={{ gap: 8 }}>
          {pairs.map((p) => (
            <div className="row" key={p.left} style={{ gap: 8 }}>
              <span style={{ flex: 1 }}>{p.left}</span>
              <span>→</span>
              <select
                className="scenario-select"
                style={{ flex: 1 }}
                value={current[p.left] ?? ''}
                onChange={(e) => setAnswer(qid, { ...current, [p.left]: e.target.value })}
              >
                <option value="">— выберите —</option>
                {rights.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          ))}
        </div>
      );
    }
    if (q.kind === 'sequence') {
      const labels = options.map((o) => String(o.label ?? o.key));
      const orderMap = (answers[qid] as Record<string, number>) ?? {};
      const assigned = Object.keys(orderMap).filter((l) => orderMap[l] != null);
      return (
        <div className="col" style={{ gap: 8 }}>
          {labels.map((label) => (
            <div className="row" key={label} style={{ gap: 8 }}>
              <input
                className="form-input"
                style={{ width: 60 }}
                type="number"
                min={1}
                max={labels.length}
                placeholder="порядок"
                value={orderMap[label] != null ? orderMap[label] + 1 : ''}
                onChange={(e) => setSequence(qid, label, Number(e.target.value) - 1)}
              />
              <span style={{ flex: 1 }}>{label}</span>
            </div>
          ))}
          {assigned.length === 0 && <div className="muted" style={{ fontSize: 11 }}>Укажите порядок цифрами 1…{labels.length}</div>}
        </div>
      );
    }
    // object
    return (
      <select
        className="scenario-select full"
        value={answers[qid] != null ? String(answers[qid]) : ''}
        onChange={(e) => setAnswer(qid, e.target.value)}
      >
        <option value="">— выберите оборудование —</option>
        {(options.length ? options : equipment.map((e) => ({ key: e.id, label: e.name }))).map((o) => (
          <option key={String(o.key)} value={String(o.key)}>{String(o.label ?? o.key)}</option>
        ))}
      </select>
    );
  };

  return (
    <>
      <div className="row-between" style={{ marginBottom: 12 }}>
        <span className="muted">Вопросов: {questions.length} · Отвечено: {answered} / {questions.length}</span>
        <Chip tone="accent">⏱ {fmtDur(elapsed)}</Chip>
      </div>
      {questions.map((q, i) => (
        <Card key={q.id} title={`${i + 1}. ${q.title}`} subtitle={q.text || undefined} actions={<Chip tone="accent">{QUESTION_KIND_LABEL[q.kind]}</Chip>}>
          {renderQuestion(q)}
          {q.hint && <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>Подсказка: {q.hint}</div>}
        </Card>
      ))}
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn-start" disabled={busy} onClick={() => void submit()}>
          {busy ? 'Отправка…' : 'Отправить ответы'}
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Результат
// ---------------------------------------------------------------------------

function ResultCard({ a, onClose }: { a: AssessmentView; onClose: () => void }) {
  return (
    <Card
      title="Результат"
      subtitle={a.kind === 'test' ? 'Контроль знаний' : a.kind === 'practice' ? 'Практическое задание' : 'Экзамен'}
      actions={<Chip tone={a.passed ? 'ok' : 'bad'}>{a.passed ? 'Зачтено' : 'Не зачтено'}</Chip>}
    >
      <div className="row" style={{ gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
        <Score value={a.score} />
        <div className="col" style={{ gap: 6 }}>
          <div className="muted">Потрачено времени: {fmtDur(a.duration_s)}</div>
          <div className="muted">Модуль: {a.module_title || `#${a.module_id}`}</div>
          <div className="muted">Ошибок: {a.errors_count} · Критических: {a.critical_errors_count}</div>
        </div>
      </div>
      <div className="row-between" style={{ marginTop: 16 }}>
        <span className="muted">Оценка</span>
        <span className="bold num">{a.score.toFixed(1)}%</span>
      </div>
      <Bar value={a.score} tone={a.passed ? 'ok' : 'bad'} height={10} />

      {a.feedback_good.length > 0 && (
        <div className="col" style={{ marginTop: 14 }}>
          <div className="card-title">Верно</div>
          {a.feedback_good.map((f, i) => <div key={i} className="muted" style={{ fontSize: 12 }}>✓ {f}</div>)}
        </div>
      )}
      {a.feedback_bad.length > 0 && (
        <div className="col" style={{ marginTop: 10 }}>
          <div className="card-title">Замечания</div>
          {a.feedback_bad.map((f, i) => <div key={i} className="muted" style={{ fontSize: 12, color: 'var(--warn)' }}>✗ {f}</div>)}
        </div>
      )}
      <div className="row" style={{ justifyContent: 'flex-end', marginTop: 16 }}>
        <button className="btn" onClick={onClose}>Вернуться к курсам</button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Страница прохождения модуля
// ---------------------------------------------------------------------------

const STEPS = [
  { id: 'lessons', label: 'Теория' },
  { id: 'test', label: 'Тест' },
  { id: 'practice', label: 'Практика' },
];

export default function ModuleStudyPage() {
  const { moduleId } = useParams<{ moduleId: string }>();
  const id = Number(moduleId);
  const { data, error, loading, reload } = useAsync<ModuleStudy>(() => api.lmsModuleStudy(id), [id]);
  const navigate = useNavigate();
  const [step, setStep] = useState<'lessons' | 'test' | 'practice' | 'result'>(
    new URLSearchParams(window.location.search).get('step') === 'practice' ? 'practice' : 'lessons',
  );
  const [assessment, setAssessment] = useState<AssessmentView | null>(null);
  const [startPractice, setStartPractice] = useState(false);

  if (loading && !data) return <Loader />;

  if (error && !data) {
    return (
      <Page title={`Модуль #${id}`}>
        <Card><Err text={error} /></Card>
        <button className="btn" onClick={() => void reload()}>Повторить</button>
      </Page>
    );
  }

  const study = data;
  if (!study) return <Empty text="Нет данных" />;

  const hasTest = !!study.test?.id && study.test.questions.length > 0;
  const hasPractice = !!study.task && !!study.scenario;
  const canGoNext = step === 'lessons' ? hasTest : true;
  const activeStep = step === 'practice' && !hasPractice ? 'lessons' : step;

  const currentIndex = STEPS.findIndex((s) => s.id === activeStep);

  const stepIcon = (s: string) => {
    if (activeStep === 'result') return '';
    const idx = STEPS.findIndex((x) => x.id === s);
    if (idx < currentIndex) return '✓';
    if (idx === currentIndex) return '▶';
    return '';
  };

  return (
    <Page
      title={study.module.title}
      subtitle={`Модуль #${study.module.id} · ${study.module.description || 'Учебная программа'}`}
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <div className="row-between" style={{ flexWrap: 'wrap' }}>
        <div className="tabs">
          {STEPS.map((s) => {
            const disabled = !canGoNext && s.id === 'practice' && activeStep === 'lessons';
            return (
              <button
                key={s.id}
                className={`tab${s.id === activeStep ? ' on' : ''}`}
                disabled={s.id !== 'lessons' && !hasTest && s.id === 'test'}
                onClick={() => setStep(s.id as 'lessons' | 'test' | 'practice')}
              >
                {stepIcon(s.id)} {s.label}
              </button>
            );
          })}
        </div>
        <Chip tone={hasPractice ? 'ok' : 'muted'}>
          {hasTest ? `Тест: ${study.test?.questions.length} вопросов` : 'Тест не опубликован'}
          {hasPractice ? ` · Практика: ${study.task?.title}` : ''}
        </Chip>
      </div>

      {activeStep === 'lessons' && (
        <div className="col" style={{ gap: 12 }}>
          {study.lessons.length === 0 ? (
            <Card><Empty text="Теоретический материал ещё не загружен" /></Card>
          ) : (
            study.lessons.map((l) => (
              <Card key={l.id} title={`${l.seq}. ${l.title}`}>
                {l.blocks.length === 0 ? (
                  <Empty text="Пустой урок" />
                ) : (
                  <div className="col" style={{ gap: 12 }}>
                    {l.blocks.map((b, i) => {
                      if (b.kind === 'text' || b.kind === 'scheme') {
                        return (
                          <div key={i}>
                            {b.title && <div className="card-title" style={{ marginBottom: 6 }}>{b.title}</div>}
                            {b.content ? (
                              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, lineHeight: 1.65, color: 'var(--text)', margin: 0 }}>{b.content}</pre>
                            ) : null}
                            {b.url && <a href={b.url} target="_blank" rel="noreferrer">{b.url}</a>}
                          </div>
                        );
                      }
                      if (b.kind === 'image') {
                        return <img key={i} src={b.url} alt={b.title || 'Иллюстрация'} style={{ maxWidth: '100%', borderRadius: 8 }} />;
                      }
                      if (b.kind === 'video') {
                        return (
                          <div key={i}>
                            <div className="card-title" style={{ marginBottom: 6 }}>{b.title}</div>
                            <video src={b.url} controls style={{ maxWidth: '100%', borderRadius: 8 }} />
                          </div>
                        );
                      }
                      if (b.kind === 'equipment_card' || b.kind === 'scheme_highlight' || b.kind === 'interactive_scheme') {
                        const eq = study.equipment.find((e) => e.id === b.node_id);
                        return (
                          <div key={i} className="card" style={{ boxShadow: 'none' }}>
                            <div className="card-title" style={{ marginBottom: 6 }}>{b.title || eq?.name || b.node_id}</div>
                            {eq ? (
                              <>
                                <div className="muted">{eq.name} ({eq.type})</div>
                                <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                                  {Object.entries(eq.params).map(([k, v]) => (
                                    <Chip key={k}>{k}: {String(v)}</Chip>
                                  ))}
                                </div>
                              </>
                            ) : (
                              <div className="muted">Узел: {b.node_id || '—'}</div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    })}
                  </div>
                )}
              </Card>
            ))
          )}
          <div className="row" style={{ justifyContent: 'flex-end' }}>
            {hasTest ? (
              <button className="btn btn-start" onClick={() => setStep('test')}>Перейти к тесту →</button>
            ) : hasPractice ? (
              <button className="btn btn-start" onClick={() => setStep('practice')}>Перейти к практике →</button>
            ) : (
              <button className="btn" onClick={() => navigate('/courses')}>К курсам</button>
            )}
          </div>
        </div>
      )}

      {activeStep === 'test' && study.test && (
        <div className="col" style={{ gap: 12 }}>
          <TestRunner test={study.test} equipment={study.equipment} onDone={(a) => { setAssessment(a); setStep('result'); }} />
        </div>
      )}

      {activeStep === 'practice' && (
        <Card
          title="Практическое задание"
          subtitle={study.task ? `${study.task.title} · ⏱ ${study.task.duration_min} мин` : undefined}
          actions={hasPractice ? <Chip tone="ok">Сценарий готов</Chip> : <Chip tone="bad">Сценарий недоступен</Chip>}
        >
          {!hasPractice ? (
            <>
              <Empty text="Для этого модуля практика не опубликована" />
              <button className="btn" onClick={() => navigate('/courses')}>К курсам</button>
            </>
          ) : (
            <>
              {study.task?.goal && <p className="muted">{study.task.goal}</p>}
              <div className="col" style={{ gap: 4, marginBottom: 14 }}>
                {study.task?.expected_actions.map((a, i) => (
                  <div key={i} className="muted" style={{ fontSize: 12 }}>
                    {i + 1}. {actionLabel(a.action_type)} → {a.object_id} {a.attribute ? ` (${attrLabel(a.attribute)})` : ''} {a.description ? `(${a.description})` : ''}
                  </div>
                ))}
              </div>
              <div className="row" style={{ justifyContent: 'flex-end' }}>
                <button className="btn" onClick={() => setStep('test')}>← К тесту</button>
                <button className="btn btn-start" onClick={() => setStartPractice(true)}>Начать практику</button>
              </div>
            </>
          )}
        </Card>
      )}

      {activeStep === 'result' && assessment && (
        <ResultCard a={assessment} onClose={() => navigate('/courses')} />
      )}

      {activeStep === 'result' && !assessment && <Empty text="Нет результата" />}

      {startPractice && hasPractice && (
        <PracticeFrame
          moduleId={id}
          onDone={(a) => { setAssessment(a); setStartPractice(false); setStep('result'); }}
        />
      )}
    </Page>
  );
}
