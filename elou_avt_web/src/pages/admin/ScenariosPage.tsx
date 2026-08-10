import { useState } from 'react';
import { api } from '../../api';
import type { EquipmentItem, LmsCompetency, ScenarioCatalogItem, ScenarioStatus } from '../../types';
import { Card, Chip, Empty, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';
import { ScenarioModal } from '../../lms/scenarioEditor';

const STATUS_LABEL: Record<ScenarioStatus, string> = {
  DRAFT: 'Черновик',
  REVIEW: 'На проверке',
  PUBLISHED: 'Опубликован',
  ARCHIVED: 'Архив',
};

const STATUS_TONE: Record<ScenarioStatus, 'ok' | 'warn' | 'accent' | 'muted'> = {
  DRAFT: 'muted',
  REVIEW: 'accent',
  PUBLISHED: 'ok',
  ARCHIVED: 'warn',
};

export default function ScenariosPage() {
  const view = useAsync<ScenarioCatalogItem[]>(() => api.lmsAuthoringScenarios(), []);
  const equipment = useAsync<EquipmentItem[]>(() => api.lmsAuthoringEquipment(), []);
  const competencies = useAsync<LmsCompetency[]>(() => api.lmsCompetencies(), []);
  const courses = useAsync<{ id: number; title: string; modules: { id: number; kind: string; title: string }[] }[]>(
    () => api.lmsCourses(),
    [],
  );

  const [modal, setModal] = useState<{ moduleId: number; scenario: ScenarioCatalogItem | null } | null>(null);
  const [creating, setCreating] = useState(false);

  const scenarios = view.data ?? [];
  const notifyError = (e: unknown) => notifyToast(`Ошибка: ${e instanceof Error ? e.message : e}`);

  const saveScenario = async (w: Parameters<typeof api.lmsSaveScenario>[1]) => {
    if (!modal) return;
    try {
      await api.lmsSaveScenario(modal.moduleId, w);
      notifyToast('Сценарий сохранён');
      setModal(null);
      await view.reload();
    } catch (e) { notifyError(e); }
  };

  const deleteScenario = async (s: ScenarioCatalogItem) => {
    if (s.id == null) return;
    if (!window.confirm(`Удалить сценарий «${s.title}»?`)) return;
    try {
      await api.lmsDeleteScenario(s.id);
      notifyToast('Сценарий удалён');
      await view.reload();
    } catch (e) { notifyError(e); }
  };

  const setStatus = async (s: ScenarioCatalogItem, status: ScenarioStatus) => {
    if (s.id == null) return;
    try {
      await api.lmsSetScenarioStatus(s.id, status);
      notifyToast(`Статус: ${STATUS_LABEL[status]}`);
      await view.reload();
    } catch (e) { notifyError(e); }
  };

  const openCreate = (moduleId: number) => {
    setCreating(false);
    setModal({ moduleId, scenario: null });
  };

  if (view.loading && !view.data) return <Loader />;
  if (view.error && !view.data) return <Err text={view.error} />;

  return (
    <Page
      title="Сценарии"
      subtitle="Учебные сценарии модулей (редактирование, статусы, удаление)"
      actions={
        <>
          <button className="btn" onClick={() => void view.reload()}>Обновить</button>
          <button className="btn btn-start" onClick={() => setCreating(true)}>Новый сценарий</button>
        </>
      }
    >
      <Card>
        {scenarios.length === 0 ? (
          <Empty text="Сценариев нет" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Модуль</th>
                  <th>Курс</th>
                  <th>Статус</th>
                  <th>Длит.</th>
                  <th>Событий</th>
                  <th>Действий</th>
                  <th>Тип</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {scenarios.map((s) => (
                  <tr key={s.id}>
                    <td className="num">#{s.id}</td>
                    <td className="bold">{s.title}</td>
                    <td className="muted">{s.module_title || `модуль #${s.module_id}`}</td>
                    <td className="muted">{s.course_title || '—'}</td>
                    <td>
                      <select
                        className="scenario-select"
                        value={s.status}
                        onChange={(e) => void setStatus(s, e.target.value as ScenarioStatus)}
                        title={STATUS_LABEL[s.status]}
                      >
                        {(Object.keys(STATUS_LABEL) as ScenarioStatus[]).map((st) => (
                          <option key={st} value={st}>{STATUS_LABEL[st]}</option>
                        ))}
                      </select>
                    </td>
                    <td className="num">{s.duration_min} мин</td>
                    <td className="num">{s.events.length}</td>
                    <td className="num">{s.expected_actions.length}</td>
                    <td>{s.is_exam ? <Chip tone="bad">экзамен</Chip> : <Chip tone="ok">практика</Chip>}</td>
                    <td className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                      <button className="btn" onClick={() => setModal({ moduleId: s.module_id, scenario: s })}>Изменить</button>
                      <button className="btn btn-danger" onClick={() => void deleteScenario(s)}>Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="sc-hint" style={{ marginTop: 8 }}>
        Сценарий привязан к модулю (один на модуль). Изменение статуса влияет на доступность сценария операторам.
      </div>

      {creating && (
        <div className="modal-overlay" onClick={() => setCreating(false)}>
          <div className="modal" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 16 }}>Новый сценарий</div>
            <p className="muted" style={{ marginTop: 0 }}>
              Выберите модуль без сценария — новый сценарий будет привязан к нему.
            </p>
            {(courses.data ?? []).map((c) => {
              const free = c.modules.filter((m) => !scenarios.some((s) => s.module_id === m.id));
              if (free.length === 0) return null;
              return (
                <div key={c.id} className="form-field">
                  <div className="card-title">{c.title}</div>
                  <div className="col" style={{ gap: 6 }}>
                    {free.map((m) => (
                      <div className="row" key={m.id} style={{ gap: 8, justifyContent: 'space-between' }}>
                        <span className="muted">{m.title} <Chip tone="muted">{m.kind}</Chip></span>
                        <button className="btn btn-start" onClick={() => openCreate(m.id)}>Создать</button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {(courses.data ?? []).every((c) => !c.modules.some((m) => !scenarios.some((s) => s.module_id === m.id))) && (
              <Empty text="Все модули уже имеют сценарии. Сначала удалите один из существующих." />
            )}
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setCreating(false)}>Отмена</button>
            </div>
          </div>
        </div>
      )}

      {modal && (
        <ScenarioModal
          scenario={modal.scenario}
          equipment={equipment.data ?? []}
          competencies={competencies.data ?? []}
          onSave={(w) => void saveScenario(w)}
          onClose={() => setModal(null)}
        />
      )}
    </Page>
  );
}
