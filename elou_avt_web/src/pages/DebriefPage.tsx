import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import type { LmsDebrief } from '../types';
import {
  Card,
  Chip,
  Empty,
  Err,
  Loader,
  Page,
  Score,
  fmtClock,
  fmtDur,
  useAsync,
} from '../lms/ui';

const ERROR_LABELS: Record<string, string> = {
  WRONG_SEQUENCE: 'Нарушение последовательности действий',
  DELAYED_ACTION: 'Действие выполнено с задержкой',
  WRONG_EQUIPMENT: 'Выбрано неправильное оборудование',
  WRONG_ACTION_TYPE: 'Выбран неправильный тип действия',
  WRONG_PARAMETER_VALUE: 'Задано неправильное значение параметра',
  MISSED_ACTION: 'Пропущено обязательное действие',
  REGULATORY_VIOLATION: 'Нарушение технологического регламента',
};

const SEVERITY_LABELS: Record<string, string> = {
  LOW: 'низкий',
  MEDIUM: 'средний',
  HIGH: 'высокий',
  CRITICAL: 'критический',
};

function qualTone(q: string): 'q-ok' | 'q-warn' | 'q-bad' {
  if (q.includes('ОТЛИЧНО')) return 'q-ok';
  if (q.includes('НЕ СДАНО')) return 'q-bad';
  return 'q-warn';
}

export default function DebriefPage({ mode = 'operator' }: { mode?: 'operator' | 'instructor' }) {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const isInstructor = mode === 'instructor';
  const [dominantAgreed, setDominantAgreed] = useState<boolean | null>(null);
  const [secondaryAgreed, setSecondaryAgreed] = useState<boolean | null>(null);
  const [selfLabel, setSelfLabel] = useState('');
  const [instructorLabel, setInstructorLabel] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const { data, error, loading } = useAsync<LmsDebrief>(
    () =>
      sessionId
        ? isInstructor
          ? api.lmsReport(sessionId)
          : api.lmsDebrief(sessionId)
        : Promise.reject(new Error('Нет сессии')),
    [sessionId, isInstructor],
  );

  useEffect(() => {
    const prediction = data?.ml_prediction;
    if (!prediction) return;
    setDominantAgreed(prediction.dominant_agreed);
    setSecondaryAgreed(prediction.secondary_agreed);
    setSelfLabel(prediction.self_assessment_label ?? '');
    setInstructorLabel(prediction.instructor_label ?? '');
  }, [data]);

  if (loading) return <Loader text="Формируем разбор выполнения…" />;
  if (error) return <Err text={error} />;
  if (!data) return <Empty />;

  const d = data;
  const prediction = d.ml_prediction;
  const top = prediction?.top_causes ?? [];
  const needsSelfAssessment = dominantAgreed === false && secondaryAgreed === false;

  async function saveOperatorFeedback() {
    if (!sessionId || dominantAgreed == null || secondaryAgreed == null) return;
    if (needsSelfAssessment && !selfLabel) {
      setFeedbackStatus('Укажите причину или выберите вариант «Ни одна причина не подходит»');
      return;
    }
    setSaving(true);
    setFeedbackStatus('');
    try {
      await api.lmsMlFeedback(sessionId, {
        dominant_agreed: dominantAgreed,
        secondary_agreed: secondaryAgreed,
        self_assessment_label: needsSelfAssessment ? selfLabel : null,
      });
      setFeedbackStatus('Ответ сохранён');
    } catch (saveError) {
      setFeedbackStatus(saveError instanceof Error ? saveError.message : 'Не удалось сохранить ответ');
    } finally {
      setSaving(false);
    }
  }

  async function saveInstructorFeedback() {
    if (!sessionId || !instructorLabel) return;
    setSaving(true);
    setFeedbackStatus('');
    try {
      await api.lmsInstructorMlFeedback(sessionId, instructorLabel);
      setFeedbackStatus('Оценка инструктора сохранена');
    } catch (saveError) {
      setFeedbackStatus(saveError instanceof Error ? saveError.message : 'Не удалось сохранить оценку');
    } finally {
      setSaving(false);
    }
  }

  const agreement = (value: boolean | null, setValue: (next: boolean) => void) => (
    <div className="row" style={{ gap: 8 }}>
      <button type="button" className={`btn${value === true ? ' btn-start' : ''}`} onClick={() => setValue(true)}>Да</button>
      <button type="button" className={`btn${value === false ? ' btn-danger' : ''}`} onClick={() => setValue(false)}>Нет</button>
    </div>
  );

  return (
    <Page
      title={isInstructor ? 'Отчёт о выполненной практике' : 'Анализ выполнения задания'}
      subtitle={d.task_title || d.scenario_name || d.scenario_id}
      actions={
        isInstructor ? (
          <button className="btn" onClick={() => navigate('/instructor/reports')}>К отчётам</button>
        ) : (
          <>
            <button className="btn" onClick={() => navigate('/practice')}>К практике</button>
            <button className="btn btn-ghost" onClick={() => navigate('/history')}>К истории</button>
          </>
        )
      }
    >
      <Card title="Итоги">
        <div className="debrief-score">
          <Score value={d.performance_score} size={112} />
          <div className="col" style={{ gap: 8 }}>
            <div>
              <div className="muted" style={{ fontSize: 11 }}>Квалификационная оценка</div>
              <div className={`qual ${qualTone(d.qualification)}`}>{d.qualification || '—'}</div>
            </div>
            <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Длительность</div>
                <div className="bold num">{fmtDur(d.duration_s)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Симуляционное время</div>
                <div className="bold num">{fmtClock(d.sim_start)} – {fmtClock(d.sim_end)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 11 }}>Оператор</div>
                <div className="bold">
                  {d.operator_full_name ? `${d.operator_full_name} (${d.operator_id})` : d.operator_id}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div className="hero-row">
        <div className="hero-main">
          <Card title="Последовательность действий" subtitle={`Журнал операций · ${d.steps.length}`}>
            {d.steps.length === 0 ? (
              <Empty text="Действий не зафиксировано" />
            ) : (
              <ul className="steps">
                {d.steps.map((s) => (
                  <li key={s.seq} className="step-row">
                    <span className="step-seq">{s.seq}</span>
                    <div className="step-body">
                      <div className="step-desc">{s.description}</div>
                      <div className="step-detail">{s.detail}</div>
                    </div>
                    <span className="step-time">{fmtClock(s.timestamp)}</span>
                    {s.status === 'rejected' && (
                      <span className="step-status">
                        <Chip tone="bad">отклонено</Chip>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Ошибки и замечания" subtitle={`${d.remarks.length + d.errors.length}`}>
            {d.remarks.length > 0 && (
              <ul className="err-list">
                {d.remarks.map((r, i) => (
                  <li key={i} className="err-item remark-item">
                    <div className="err-title remark-title">{r}</div>
                  </li>
                ))}
              </ul>
            )}
            {d.errors.length === 0 ? (
              d.remarks.length > 0 ? null : <Empty text="Ошибок не зафиксировано — отличная работа" />
            ) : (
              <ul className="err-list">
                {d.errors.map((e, i) => (
                  e.rule_error_type === 'PRACTICE_FEEDBACK' ? (
                    <li key={i} className="err-item remark-item">
                      <div className="err-title remark-title">{e.cause || e.rule_error_type}</div>
                    </li>
                  ) : (
                  <li key={i} className="err-item">
                    <div className="err-title">{ERROR_LABELS[e.rule_error_type] ?? e.rule_error_type}</div>
                    <div className="err-meta">
                      {e.severity && `Уровень: ${SEVERITY_LABELS[e.severity] ?? e.severity} · `}Время: {fmtClock(e.timestamp)}
                    </div>
                    {e.cause && <div className="err-meta">Причина: {e.cause}</div>}
                    {e.consequence && <div className="err-meta">Последствие: {e.consequence}</div>}
                    {e.expected_action && <div className="err-meta">Ожидалось: {e.expected_action}</div>}
                  </li>
                  )
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="hero-side">
          {prediction && top.length >= 2 && (
            <Card title="Возможные причины неудачного прохождения" subtitle="Гипотезы модели требуют подтверждения человеком">
              <div className="col" style={{ gap: 10 }}>
                <div><div className="muted">Доминирующая гипотеза</div><div className="bold">{top[0].name}</div><div className="muted num">Уверенность: {(top[0].probability * 100).toFixed(0)}%</div></div>
                {!isInstructor && <><div className="bold" style={{ fontSize: 12 }}>Согласны ли вы с причиной?</div>{agreement(dominantAgreed, setDominantAgreed)}</>}
                <hr style={{ width: '100%', border: 0, borderTop: '1px solid var(--border)' }} />
                <div><div className="muted">Следующая вероятная причина</div><div className="bold">{top[1].name}</div><div className="muted num">Уверенность: {(top[1].probability * 100).toFixed(0)}%</div></div>
                {!isInstructor && <><div className="bold" style={{ fontSize: 12 }}>Согласны ли вы с причиной?</div>{agreement(secondaryAgreed, setSecondaryAgreed)}</>}

                {!isInstructor && needsSelfAssessment && (
                  <label className="col" style={{ gap: 6 }}>
                    <span className="bold" style={{ fontSize: 12 }}>Пожалуйста, укажите ваше мнение, почему сценарий не был сдан</span>
                    <select className="scenario-select" value={selfLabel} onChange={(event) => setSelfLabel(event.target.value)}>
                      <option value="">Выберите причину</option>
                      {prediction.causes.map((cause) => <option key={cause.label} value={cause.label}>{cause.name}</option>)}
                      <option value="none">Ни одна причина не подходит</option>
                    </select>
                  </label>
                )}

                {isInstructor && (
                  <>
                    <div className="muted" style={{ fontSize: 12 }}>
                      Самооценка оператора: {prediction.self_assessment_label
                        ? prediction.causes.find((cause) => cause.label === prediction.self_assessment_label)?.name ?? 'Ни одна причина не подходит'
                        : 'не указана'}
                    </div>
                    <label className="col" style={{ gap: 6 }}>
                      <span className="bold" style={{ fontSize: 12 }}>Оценка инструктора</span>
                      <select className="scenario-select" value={instructorLabel} onChange={(event) => setInstructorLabel(event.target.value)}>
                        <option value="">Выберите причину</option>
                        {prediction.causes.map((cause) => <option key={cause.label} value={cause.label}>{cause.name}</option>)}
                      </select>
                    </label>
                  </>
                )}

                {feedbackStatus && <div className="muted" style={{ fontSize: 12 }}>{feedbackStatus}</div>}
                {isInstructor ? (
                  <button className="btn btn-start" disabled={saving || !instructorLabel} onClick={() => void saveInstructorFeedback()}>{saving ? 'Сохранение…' : 'Сохранить оценку'}</button>
                ) : (
                  <button className="btn btn-start" disabled={saving || dominantAgreed == null || secondaryAgreed == null} onClick={() => void saveOperatorFeedback()}>{saving ? 'Сохранение…' : 'Сохранить мнение'}</button>
                )}
              </div>
            </Card>
          )}
          <Card title="Рекомендации">
            {d.recommendations.length === 0 ? (
              <Empty text="Рекомендаций нет" />
            ) : (
              <ul className="reco-list">
                {d.recommendations.map((r, i) => (
                  <li key={i} className="reco-item">
                    <span className="reco-ico">→</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Изменение компетенций">
            {d.competency_delta.length === 0 ? (
              <Empty text="Связанные компетенции не определены" />
            ) : (
              <div>
                {d.competency_delta.map((c) => (
                  <div key={c.code} className="delta-row">
                    <span className="delta-title">{c.title}</span>
                    <span className="delta-old num">{c.old.toFixed(1)}</span>
                    <span className="delta-arrow">→</span>
                    <span className={`delta-new num ${c.delta >= 0 ? 'up' : 'down'}`}>
                      {c.new.toFixed(1)}
                    </span>
                    <span className="delta-val">
                      {c.delta >= 0 ? '+' : ''}{c.delta.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {d.alarms.length > 0 && (
            <Card title={`События аварий · ${d.alarms.length}`}>
              <div className="table-wrap">
                <table className="table" style={{ fontSize: 11.5 }}>
                  <thead>
                    <tr><th>Время</th><th>Тревога</th><th>Значение</th></tr>
                  </thead>
                  <tbody>
                    {d.alarms.slice(0, 20).map((a, i) => (
                      <tr key={i}>
                        <td className="num">{fmtClock(Number(a.raised_at ?? a.timestamp ?? 0))}</td>
                        <td>{String(a.parameter ?? a.description ?? '—')}</td>
                        <td className="num">{a.actual_value != null ? Number(a.actual_value).toFixed(1) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}
