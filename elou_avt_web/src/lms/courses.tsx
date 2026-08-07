import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import type { LmsCourse, LmsPracticeTask, LmsScenario, ModuleKind } from '../types';
import { Card, Chip, Empty, Err, KindTag, Loader, ModuleIcon, Page, notifyToast, useAsync } from './ui';

export function CourseConstructor({ canEdit }: { canEdit: boolean }) {
  const navigate = useNavigate();
  const courses = useAsync<LmsCourse[]>(() => api.lmsCourses(), []);
  const scenarios = useAsync<LmsScenario[]>(() => api.lmsScenarios(), []);
  const tasks = useAsync<LmsPracticeTask[]>(() => api.lmsPracticeTasks(true), []);

  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [mKind, setMKind] = useState<ModuleKind>('theory');
  const [mTitle, setMTitle] = useState('');
  const [mScenario, setMScenario] = useState('');

  const createCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const c = await api.lmsCreateCourse(newTitle.trim(), newDesc.trim());
      notifyToast(`Курс «${c.title}» создан`);
      setNewTitle('');
      setNewDesc('');
      await courses.reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const setStatus = async (id: number, status: string) => {
    try {
      await api.lmsUpdateCourse(id, { status });
      notifyToast(`Статус курса #${id}: ${status}`);
      await courses.reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const addModule = async (courseId: number) => {
    if (!mTitle.trim()) return notifyToast('Укажите название модуля');
    try {
      await api.lmsAddModule(courseId, {
        kind: mKind,
        title: mTitle.trim(),
        scenario_id: mScenario || null,
        description: '',
      });
      notifyToast('Модуль добавлен');
      setMTitle('');
      setMScenario('');
      await courses.reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const removeModule = async (courseId: number, moduleId: number) => {
    if (!window.confirm(`Удалить модуль #${moduleId}?`)) return;
    try {
      await api.lmsRemoveModule(courseId, moduleId);
      notifyToast('Модуль удалён');
      await courses.reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (courses.loading && !courses.data) return <Loader />;
  if (courses.error && !courses.data) return <Err text={courses.error} />;

  const list = courses.data ?? [];
  const scenarioIds = (scenarios.data ?? []).map((s) => s.id);

  return (
    <Page
      title="Курсы"
      subtitle={canEdit ? 'Конструктор учебных программ: Теория → Практика → Экзамен' : 'Учебные программы'}
    >
      {canEdit && (
        <Card title="Новый курс">
          <form className="row" onSubmit={createCourse} style={{ alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-field" style={{ flex: 1, minWidth: 220 }}>
              <label className="form-label">Название</label>
              <input className="form-input" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} required />
            </div>
            <div className="form-field" style={{ flex: 2, minWidth: 280 }}>
              <label className="form-label">Описание</label>
              <input className="form-input" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-start">Создать</button>
          </form>
        </Card>
      )}

      {list.length === 0 ? (
        <Card><Empty text="Курсов пока нет" /></Card>
      ) : (
        list.map((c) => {
          const open = expanded === c.id;
          return (
            <Card
              key={c.id}
              title={c.title}
              subtitle={c.description || 'Программа подготовки'}
              actions={
                <>
                  <Chip tone={c.status === 'ACTIVE' ? 'ok' : c.status === 'DRAFT' ? 'warn' : 'muted'}>{c.status}</Chip>
                  {canEdit && (
                    <>
                      <button
                        className="btn"
                        onClick={() => setStatus(c.id, c.status === 'ACTIVE' ? 'DRAFT' : 'ACTIVE')}
                      >
                        {c.status === 'ACTIVE' ? 'Снять с публикации' : 'Опубликовать'}
                      </button>
                      <button className="btn" onClick={() => setExpanded(open ? null : c.id)}>
                        {open ? 'Свернуть' : 'Модули'}
                      </button>
                    </>
                  )}
                </>
              }
            >
              <div className="row-between" style={{ marginBottom: 8 }}>
                <span className="muted">Прогресс освоения</span>
                <span className="bold num">{c.progress_percent.toFixed(0)}%</span>
              </div>
              <div className="col" style={{ gap: 6 }}>
                {c.modules.map((m) => (
                  <div className="module-row" key={m.id}>
                    <ModuleIcon status={m.status} />
                    <div className="module-row-main">
                      <div className="module-row-title">
                        {m.seq}. {m.title} <KindTag kind={m.kind} />
                      </div>
                      <div className="module-row-sub">
                        {m.scenario_id && `Сценарий: ${m.scenario_id}`}
                        {m.practice_task_id && ` · Задание #${m.practice_task_id}`}
                      </div>
                    </div>
                    {canEdit && (
                      <>
                        <button className="btn btn-ghost" onClick={() => navigate(`/instructor/modules/${m.id}`)}>
                          Конструктор
                        </button>
                        <button className="btn btn-danger" onClick={() => void removeModule(c.id, m.id)}>
                          Удалить
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>

              {open && canEdit && (
                <div className="card" style={{ marginTop: 12 }}>
                  <div className="card-title" style={{ marginBottom: 10 }}>Добавить модуль</div>
                  <div className="row" style={{ flexWrap: 'wrap' }}>
                    <div className="form-field">
                      <label className="form-label">Тип</label>
                      <select className="scenario-select" value={mKind} onChange={(e) => setMKind(e.target.value as ModuleKind)}>
                        <option value="theory">Теория</option>
                        <option value="practice">Практика</option>
                        <option value="exam">Экзамен</option>
                      </select>
                    </div>
                    <div className="form-field" style={{ flex: 1, minWidth: 220 }}>
                      <label className="form-label">Название</label>
                      <input className="form-input" value={mTitle} onChange={(e) => setMTitle(e.target.value)} />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Сценарий</label>
                      <select className="scenario-select" value={mScenario} onChange={(e) => setMScenario(e.target.value)}>
                        <option value="">— без сценария —</option>
                        {scenarioIds.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <button className="btn btn-start" onClick={() => void addModule(c.id)}>Добавить</button>
                  </div>
                </div>
              )}
            </Card>
          );
        })
      )}
    </Page>
  );
}
