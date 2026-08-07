import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api';
import type { AuthUser } from '../../api';
import type { LmsGroupView } from '../../types';
import {
  Bar,
  Card,
  Chip,
  Empty,
  Err,
  Loader,
  Page,
  fmtDateTime,
  notifyToast,
  useAsync,
} from '../../lms/ui';

function fmtScore(n: number | null): string {
  return n == null ? '—' : n.toFixed(0);
}

export default function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const id = Number(groupId);
  const { data, error, loading, reload } = useAsync<LmsGroupView>(() => api.lmsGroup(id), [id]);
  const users = useAsync<AuthUser[]>(() => api.listUsers(), []);
  const [editing, setEditing] = useState(false);
  const [sel, setSel] = useState<number[]>([]);

  const openEditor = () => {
    setSel((data?.members ?? []).map((m) => m.user_id));
    setEditing(true);
  };

  const saveMembers = async () => {
    try {
      await api.lmsSetGroupMembers(id, sel);
      notifyToast('Состав группы обновлён');
      setEditing(false);
      await reload();
    } catch (e) {
      notifyToast(`Ошибка: ${e instanceof Error ? e.message : e}`);
    }
  };

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;
  if (!data) return <Empty />;

  const g = data;

  return (
    <Page
      title={g.group.name}
      subtitle={g.group.description || 'Учебная группа'}
      actions={
        <>
          <button className="btn" onClick={() => navigate('/instructor/groups')}>← К списку</button>
          <button className="btn" onClick={() => void reload()}>Обновить</button>
          <button className="btn btn-start" onClick={openEditor}>Состав группы</button>
        </>
      }
    >
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Chip tone="accent">{g.members.length} операторов</Chip>
        {g.course && <Chip tone="ok">Курс: {g.course.title}</Chip>}
        {!g.course && <Chip>Курс не назначен</Chip>}
      </div>

      <Card title="Прогресс операторов" subtitle="Курс, мастерство и последняя сессия">
        {g.members.length === 0 ? (
          <Empty text="В группе пока нет операторов" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Оператор</th>
                  <th>Этап</th>
                  <th>Курс, %</th>
                  <th>Мастерство</th>
                  <th>Последняя сессия</th>
                  <th>Оценка</th>
                </tr>
              </thead>
              <tbody>
                {g.members.map((m) => (
                  <tr key={m.user_id}>
                    <td>
                      <div className="bold">{m.full_name || m.username}</div>
                      <div className="muted" style={{ fontSize: 11 }}>@{m.username}</div>
                    </td>
                    <td><Chip tone="accent">{m.stage || 'Стажер'}</Chip></td>
                    <td className="num bold">{m.course_progress.toFixed(0)}</td>
                    <td>
                      <div className="row" style={{ gap: 8 }}>
                        <div style={{ width: 90 }}>
                          <Bar value={m.mastery} tone="gradient" height={7} />
                        </div>
                        <span className="num bold">{m.mastery.toFixed(0)}</span>
                      </div>
                    </td>
                    <td className="muted" style={{ fontSize: 11.5 }}>
                      {m.last_session ? fmtDateTime(m.last_session.wall_start) : '—'}
                    </td>
                    <td className="num bold">
                      {m.last_session?.performance_score != null
                        ? fmtScore(m.last_session.performance_score)
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Компетенции участников" subtitle="Карта компетенций группы">
        {g.members.length === 0 ? (
          <Empty text="Нет данных" />
        ) : (
          g.members.map((m) => (
            <div key={m.user_id} style={{ marginBottom: 14 }}>
              <div className="muted bold" style={{ fontSize: 12, marginBottom: 6 }}>
                {m.full_name || m.username}
              </div>
              <div className="col" style={{ gap: 4 }}>
                {m.competencies.length === 0 ? (
                  <div className="muted" style={{ fontSize: 11 }}>Компетенции не развиты</div>
                ) : (
                  m.competencies.map((c) => (
                    <div key={c.code} className="row-between" style={{ fontSize: 11.5 }}>
                      <span className="muted">{c.title}</span>
                      <span className="num bold">{c.level_percent.toFixed(0)}%</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))
        )}
      </Card>

      {editing && (
        <div className="modal-overlay" onClick={() => setEditing(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 16 }}>Состав группы</div>
            <div className="muted" style={{ marginTop: -6, fontSize: 12 }}>
              Выберите операторов (имеют роль «Оператор»)
            </div>
            <div className="picker">
              {(users.data ?? []).map((u) => {
                const candidate = u.roles.includes('operator');
                const on = sel.includes(u.id);
                return (
                  <span
                    key={u.id}
                    className={`picker-chip${on ? ' on' : ''}`}
                    title={candidate ? 'оператор' : 'без роли оператор'}
                    style={{ opacity: candidate ? 1 : 0.45 }}
                    onClick={() =>
                      candidate &&
                      setSel((prev) => (on ? prev.filter((x) => x !== u.id) : [...prev, u.id]))
                    }
                  >
                    {u.username}
                  </span>
                );
              })}
            </div>
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setEditing(false)}>Отмена</button>
              <button className="btn btn-start" onClick={() => void saveMembers()}>Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
