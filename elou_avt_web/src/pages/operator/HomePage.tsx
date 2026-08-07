import { Link } from 'react-router-dom';
import { api } from '../../api';
import type { LmsDashboard } from '../../types';
import { useAuth } from '../../auth';
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
  Score,
  StageLadder,
  fmtDate,
  usePoll,
} from '../../lms/ui';

function fmtScore(n: number | null): string {
  return n == null ? '—' : `${n.toFixed(0)}`;
}

export default function HomePage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = usePoll<LmsDashboard>(() => api.lmsDashboard(), 15000);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;
  if (!data) return <Empty />;

  const d = data;

  return (
    <Page
      title={`Здравствуйте, ${d.full_name || d.username}`}
      subtitle="Личное пространство подготовки оператора"
      actions={
        <button className="btn" onClick={() => void reload()}>
          Обновить
        </button>
      }
    >
      <div className="hero-row">
        <div className="hero-main">
          <Card title="Индекс мастерства">
            <div className="row" style={{ alignItems: 'center', gap: 18 }}>
              <Score value={d.mastery.index} size={104} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="muted" style={{ marginBottom: 6 }}>
                  Интегральная оценка подготовки рассчитывается по результатам практик,
                  экзаменов и уровню освоения компетенций.
                </div>
                <Bar value={d.mastery.index} tone="gradient" height={10} />
                <div className="row" style={{ marginTop: 6, justifyContent: 'space-between' }}>
                  <span className="muted">Прогресс до этапа</span>
                  <span className="bold">{d.mastery.next_stage ?? '—'}</span>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Профессиональный статус">
            <StageLadder mastery={d.mastery} />
          </Card>

          {d.current_course && (
            <Card
              title={d.current_course.title}
              subtitle={d.current_course.description || 'Программа подготовки'}
            >
              <div className="row-between" style={{ marginBottom: 8 }}>
                <span className="muted">Прогресс освоения курса</span>
                <span className="bold">{d.current_course.progress_percent.toFixed(0)}%</span>
              </div>
              <Bar value={d.current_course.progress_percent} tone="gradient" height={10} />
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(230px,1fr))', marginTop: 12 }}>
                {d.nearest_module && (
                  <div className="module-row" style={{ alignItems: 'flex-start' }}>
                    <ModuleIcon status={d.nearest_module.status} />
                    <div className="module-row-main">
                      <div className="module-row-sub">Ближайшее занятие</div>
                      <div className="module-row-title">{d.nearest_module.title}</div>
                      <div className="module-row-sub" style={{ marginTop: 4 }}>
                        <KindTag kind={d.nearest_module.kind} />
                      </div>
                    </div>
                  </div>
                )}
                {d.nearest_exam ? (
                  <div className="module-row" style={{ alignItems: 'flex-start' }}>
                    <ModuleIcon status={d.nearest_exam.status} />
                    <div className="module-row-main">
                      <div className="module-row-sub">Ближайший экзамен</div>
                      <div className="module-row-title">{d.nearest_exam.title}</div>
                      <div className="module-row-sub" style={{ marginTop: 4 }}>
                        <KindTag kind={d.nearest_exam.kind} />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="module-row">
                    <span className="mi mi-done">✓</span>
                    <div className="module-row-main">
                      <div className="module-row-title">Экзаменов не осталось</div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>

        <div className="hero-side">
          <Card title="Рекомендации системы">
            {d.recommendations.length === 0 ? (
              <Empty text="Рекомендаций пока нет" />
            ) : (
              <ul className="reco-list">
                {d.recommendations.map((r, i) => (
                  <li key={i} className="reco-item">
                    <span className="reco-ico">
                      {r.kind === 'practice' ? '▶' : r.kind === 'module' ? '→' : '✦'}
                    </span>
                    <span>{r.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Мои компетенции">
            {d.competencies.length === 0 ? (
              <Empty text="Компетенции ещё не развиты" />
            ) : (
              <div className="col">
                {d.competencies.slice(0, 6).map((c) => (
                  <div key={c.code} className="col" style={{ gap: 3 }}>
                    <div className="row-between">
                      <span className="muted" style={{ fontSize: 12 }}>{c.title}</span>
                      <span className="bold num">{c.level_percent.toFixed(0)}%</span>
                    </div>
                    <Bar
                      value={c.level_percent}
                      tone={c.level_percent >= 80 ? 'ok' : c.level_percent >= 50 ? 'warn' : 'bad'}
                      height={7}
                    />
                  </div>
                ))}
                <Link className="linklike" to="/competencies" style={{ marginTop: 4 }}>
                  Все компетенции →
                </Link>
              </div>
            )}
          </Card>

          <Card title="Уведомления">
            {d.notifications.length === 0 ? (
              <Empty text="Уведомлений нет" />
            ) : (
              <ul className="note-list">
                {d.notifications.slice(0, 5).map((n) => (
                  <li key={n.id} className="reco-item note">
                    <span className="note-ico">●</span>
                    <span>{n.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <Card title="Последние занятия" subtitle="Недавно завершённые тренировки">
        {d.recent_practices.length === 0 ? (
          <Empty text="Занятий пока не было — начните с практики" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Задание</th>
                  <th>Сценарий</th>
                  <th>Оценка</th>
                  <th>Квалификация</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {d.recent_practices.map((r) => (
                  <tr key={r.session_id}>
                    <td className="num">{fmtDate(r.wall_start)}</td>
                    <td className="bold">{r.task_title || r.scenario_name || r.scenario_id}</td>
                    <td className="muted">{r.scenario_name || r.scenario_id}</td>
                    <td className="num bold">{fmtScore(r.performance_score)}</td>
                    <td>{r.qualification || '—'}</td>
                    <td>
                      <Chip tone={r.status === 'COMPLETED' ? 'ok' : 'warn'}>{r.status}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Page>
  );
}
