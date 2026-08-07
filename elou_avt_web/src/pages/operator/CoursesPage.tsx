import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import type { LmsCourse, LmsModule } from '../../types';
import {
  Bar,
  Card,
  Chip,
  Empty,
  Err,
  KindTag,
  Loader,
  ModuleIcon,
  Page,
  StatusTag,
  notifyToast,
  useAsync,
} from '../../lms/ui';

export default function CoursesPage() {
  const { data: courses, error, loading, reload } = useAsync<LmsCourse[]>(() => api.lmsCourses(), []);
  const [theory, setTheory] = useState<LmsModule | null>(null);
  const navigate = useNavigate();

  const grouped = useMemo(() => courses ?? [], [courses]);

  if (loading && !courses) return <Loader />;
  if (error && !courses) return <Err text={error} />;

  const startPractice = async (m: LmsModule) => {
    navigate(`/study/${m.id}?step=practice`);
  };

  const completeTheory = async (m: LmsModule) => {
    try {
      await api.lmsModuleTheory(m.id);
      notifyToast(`Модуль «${m.title}» изучен`);
      setTheory(null);
      await reload();
    } catch (e) {
      notifyToast(`Ошибка: ${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <Page title="Мои курсы" subtitle="Учебные программы и модули подготовки" actions={
      <button className="btn" onClick={() => void reload()}>Обновить</button>
    }>
      {grouped.length === 0 ? (
        <Card><Empty text="Курсы не назначены" /></Card>
      ) : (
        grouped.map((c) => (
          <Card
            key={c.id}
            title={c.title}
            subtitle={c.description || 'Программа подготовки'}
            actions={<Chip tone={c.status === 'ACTIVE' ? 'ok' : 'muted'}>{c.status}</Chip>}
          >
            <div className="row-between" style={{ marginBottom: 12 }}>
              <span className="muted">Прогресс освоения курса</span>
              <span className="bold num">{c.progress_percent.toFixed(0)}%</span>
            </div>
            <Bar value={c.progress_percent} tone="gradient" height={10} />
            <div className="col" style={{ gap: 8, marginTop: 14 }}>
              {c.modules.map((m) => (
                <div className="module-row" key={m.id}>
                  <ModuleIcon status={m.status} />
                  <div className="module-row-main">
                    <div className="module-row-title">
                      {m.seq}. {m.title}
                      <span style={{ marginLeft: 8 }}><KindTag kind={m.kind} /></span>
                    </div>
                    <div className="module-row-sub">
                      {m.description}
                      {m.score != null && <span> · Оценка: {m.score.toFixed(0)}</span>}
                      {m.attempts > 0 && <span> · Попыток: {m.attempts}</span>}
                      {m.practice_title && <span> · Практика: {m.practice_title}</span>}
                    </div>
                  </div>
                  <div className="module-row-bar">
                    <Bar
                      value={m.percent}
                      tone={m.status === 'COMPLETED' ? 'ok' : 'accent'}
                      height={7}
                    />
                  </div>
                  <div className="module-row-meta">
                    <StatusTag status={m.status} />
                    <button className="btn btn-ghost" onClick={() => navigate(`/study/${m.id}`)}>Открыть</button>
                    {m.kind === 'theory' && (
                      <button
                        className="btn"
                        disabled={m.status === 'COMPLETED'}
                        onClick={() => setTheory(m)}
                      >
                        {m.status === 'COMPLETED' ? 'Изучено' : 'Изучить'}
                      </button>
                    )}
                    {m.kind !== 'theory' && (
                      <button
                        className={m.kind === 'exam' ? 'btn btn-danger' : 'btn btn-start'}
                        onClick={() => void startPractice(m)}
                      >
                        {m.status === 'COMPLETED' ? 'Повторить' : m.kind === 'exam' ? 'Пройти экзамен' : 'Выполнить практику'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))
      )}

      {theory && (
        <div className="modal-overlay" onClick={() => setTheory(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 16 }}>{theory.title}</div>
            <div className="muted" style={{ marginTop: -8 }}><KindTag kind={theory.kind} /></div>
            {theory.description && <div className="muted">{theory.description}</div>}
            <div className="card" style={{ maxHeight: 320, overflowY: 'auto', boxShadow: 'none' }}>
              {theory.content ? (
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 12.5, lineHeight: 1.6, color: 'var(--text)', margin: 0 }}>
                  {theory.content}
                </pre>
              ) : (
                <Empty text="Теоретический материал ещё не загружен" />
              )}
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setTheory(null)}>Закрыть</button>
              <button
                className="btn btn-start"
                disabled={theory.status === 'COMPLETED'}
                onClick={() => void completeTheory(theory)}
              >
                {theory.status === 'COMPLETED' ? 'Изучено' : 'Отметить изученным'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
