import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import type { LmsCourse, LmsGroup } from '../../types';
import { Card, Chip, Empty, Err, Grid, Loader, Page, fmtDate, notifyToast, useAsync } from '../../lms/ui';

export default function GroupsPage() {
  const { data: groups, error, loading, reload } = useAsync<LmsGroup[]>(() => api.lmsGroups(), []);
  const courses = useAsync<LmsCourse[]>(() => api.lmsCourses(), []);
  const [show, setShow] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [courseId, setCourseId] = useState<string>('');
  const navigate = useNavigate();

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const g = await api.lmsCreateGroup(name.trim(), desc.trim(), courseId ? Number(courseId) : null);
      notifyToast(`Группа «${g.name}» создана`);
      setShow(false);
      setName('');
      setDesc('');
      setCourseId('');
      await reload();
    } catch (err) {
      notifyToast(`Ошибка: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (loading && !groups) return <Loader />;
  if (error && !groups) return <Err text={error} />;

  return (
    <Page
      title="Группы"
      subtitle="Учебные группы операторов"
      actions={<button className="btn btn-start" onClick={() => setShow(true)}>Создать группу</button>}
    >
      {(groups ?? []).length === 0 ? (
        <Card><Empty text="Групп пока нет — создайте первую" /></Card>
      ) : (
        <Grid min={280}>
          {(groups ?? []).map((gr) => (
            <Card
              key={gr.id}
              title={gr.name}
              subtitle={gr.description || 'Учебная группа'}
              actions={<Chip tone="accent">{gr.member_count} опер.</Chip>}
              className="clickable"
            >
              <div className="col" style={{ gap: 4 }}>
                {gr.course_title && (
                  <div className="muted" style={{ fontSize: 12 }}>Курс: <span className="bold">{gr.course_title}</span></div>
                )}
                <div className="muted" style={{ fontSize: 11 }}>Создана {fmtDate(gr.created_at)}</div>
              </div>
              <button
                className="btn"
                style={{ marginTop: 12 }}
                onClick={() => navigate(`/instructor/groups/${gr.id}`)}
              >
                Открыть группу →
              </button>
            </Card>
          ))}
        </Grid>
      )}

      {show && (
        <div className="modal-overlay" onClick={() => setShow(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={create}>
            <div className="page-title" style={{ fontSize: 16 }}>Новая группа</div>
            <div className="form-field">
              <label className="form-label">Название</label>
              <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </div>
            <div className="form-field">
              <label className="form-label">Описание</label>
              <input className="form-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Курс</label>
              <select className="scenario-select full" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">Без курса</option>
                {(courses.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn" onClick={() => setShow(false)}>Отмена</button>
              <button type="submit" className="btn btn-start">Создать</button>
            </div>
          </form>
        </div>
      )}
    </Page>
  );
}
