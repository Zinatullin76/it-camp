import { useState } from 'react';
import { api } from '../../api';
import type { Difficulty, LmsPracticeTask, LmsScenario, TaskCategory } from '../../types';
import { Card, Chip, DifficultyTag, Empty, Err, Loader, Page, notifyToast, useAsync } from '../../lms/ui';

const EMPTY_FORM = {
  title: '',
  description: '',
  scenario_id: '',
  category: 'practice' as TaskCategory,
  difficulty: 'MIDDLE' as Difficulty,
  duration_min: 10,
  required_competencies: '',
  is_random: false,
  enabled: true,
};

export default function TasksPage() {
  const { data, error, loading, reload } = useAsync<LmsPracticeTask[]>(() => api.lmsPracticeTasks(true), []);
  const scenarios = useAsync<LmsScenario[]>(() => api.lmsScenarios(), []);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const openNew = () => {
    setForm({ ...EMPTY_FORM });
    setEditId(0);
  };

  const openEdit = (t: LmsPracticeTask) => {
    setForm({
      title: t.title,
      description: t.description,
      scenario_id: t.scenario_id,
      category: t.category,
      difficulty: t.difficulty,
      duration_min: t.duration_min,
      required_competencies: t.required_competencies.join(', '),
      is_random: t.is_random,
      enabled: t.enabled,
    });
    setEditId(t.id);
  };

  const save = async () => {
    const body = {
      ...form,
      required_competencies: form.required_competencies.split(',').map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editId === 0) {
        await api.lmsCreateTask(body);
        notifyToast('Задание создано');
      } else if (editId) {
        await api.lmsUpdateTask(editId, body);
        notifyToast('Задание обновлено');
      }
      setEditId(null);
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  const toggleEnabled = async (t: LmsPracticeTask) => {
    try {
      await api.lmsUpdateTask(t.id, { enabled: !t.enabled });
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const tasks = data ?? [];

  return (
    <Page
      title="Практические задания"
      subtitle="Управление библиотекой заданий тренажёра"
      actions={
        <>
          <button className="btn" onClick={() => void reload()}>Обновить</button>
          <button className="btn btn-start" onClick={openNew}>Новое задание</button>
        </>
      }
    >
      <Card>
        {tasks.length === 0 ? (
          <Empty text="Заданий нет" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Задание</th>
                  <th>Сценарий</th>
                  <th>Категория</th>
                  <th>Сложность</th>
                  <th>Длит.</th>
                  <th>Компетенции</th>
                  <th>Активно</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td className="bold">{t.title}</td>
                    <td className="muted">{t.scenario_name || t.scenario_id}</td>
                    <td><Chip tone={t.category === 'exam' ? 'bad' : 'ok'}>{t.category}</Chip></td>
                    <td><DifficultyTag d={t.difficulty} /></td>
                    <td className="num">{t.duration_min} мин</td>
                    <td className="muted" style={{ fontSize: 11 }}>{t.required_competencies.join(', ') || '—'}</td>
                    <td>
                      <button className={`btn ${t.enabled ? 'btn-start' : 'btn-danger'}`} onClick={() => void toggleEnabled(t)}>
                        {t.enabled ? 'Вкл' : 'Выкл'}
                      </button>
                    </td>
                    <td><button className="btn" onClick={() => openEdit(t)}>Изменить</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editId !== null && (
        <div className="modal-overlay" onClick={() => setEditId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 16 }}>
              {editId === 0 ? 'Новое задание' : `Задание #${editId}`}
            </div>
            <div className="form-field">
              <label className="form-label">Название</label>
              <input className="form-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="form-field">
              <label className="form-label">Описание</label>
              <textarea className="form-input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="settings-grid">
              <div className="form-field">
                <label className="form-label">Сценарий</label>
                <select className="scenario-select full" value={form.scenario_id} onChange={(e) => setForm({ ...form, scenario_id: e.target.value })}>
                  <option value="">— выберите —</option>
                  {(scenarios.data ?? []).map((s) => (
                    <option key={s.id} value={s.id}>{s.name || s.id}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label className="form-label">Категория</label>
                <select className="scenario-select full" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as TaskCategory })}>
                  <option value="practice">Практика</option>
                  <option value="exam">Экзамен</option>
                  <option value="random">Случайное</option>
                </select>
              </div>
              <div className="form-field">
                <label className="form-label">Сложность</label>
                <select className="scenario-select full" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value as Difficulty })}>
                  <option value="EASY">Просто</option>
                  <option value="MIDDLE">Средне</option>
                  <option value="HARD">Сложно</option>
                </select>
              </div>
              <div className="form-field">
                <label className="form-label">Длительность, мин</label>
                <input className="form-input" type="number" min={1} value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: Number(e.target.value) || 10 })} />
              </div>
            </div>
            <div className="form-field">
              <label className="form-label">Требуемые компетенции (через запятую)</label>
              <input className="form-input" value={form.required_competencies} onChange={(e) => setForm({ ...form, required_competencies: e.target.value })} />
            </div>
            <div className="row" style={{ gap: 16 }}>
              <label className="ctrl-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" checked={form.is_random} onChange={(e) => setForm({ ...form, is_random: e.target.checked })} />
                Случайные условия
              </label>
              <label className="ctrl-label" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                Активно
              </label>
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setEditId(null)}>Отмена</button>
              <button className="btn btn-start" onClick={() => void save()}>Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
