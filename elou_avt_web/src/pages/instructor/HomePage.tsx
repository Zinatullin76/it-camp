import { Link } from 'react-router-dom';
import { api } from '../../api';
import type { LmsAnalytics, LmsGroup, LmsMonitorOperator } from '../../types';
import { Card, Empty, Err, Grid, Loader, Page, Stat, fmtDate, useAsync } from '../../lms/ui';

export default function InstructorHomePage() {
  const a = useAsync<LmsAnalytics>(() => api.lmsAnalytics(), []);
  const m = useAsync<LmsMonitorOperator[]>(() => api.lmsMonitoring(), []);
  const g = useAsync<LmsGroup[]>(() => api.lmsGroups(), []);

  if ((a.loading || m.loading || g.loading) && !a.data && !m.data && !g.data) return <Loader />;
  const err = a.error || m.error || g.error;

  const analytics = a.data;
  const monitoring = m.data ?? [];
  const groups = g.data ?? [];

  const today = new Date().toISOString().slice(0, 10);
  const todaySessions = (analytics?.learning_dynamics ?? [])
    .filter((d) => d.date === today)
    .reduce((n, d) => n + d.count, 0);
  const memberCount = groups.reduce((n, gr) => n + gr.member_count, 0);

  return (
    <Page
      title="Главная"
      subtitle="Оперативная сводка по учебному процессу"
      actions={
        <button className="btn" onClick={() => { void a.reload(); void m.reload(); void g.reload(); }}>
          Обновить
        </button>
      }
    >
      {err && <Err text={err} />}

      <Grid min={190}>
        <Stat label="Учебные группы" value={groups.length} hint={`операторов в группах: ${memberCount}`} />
        <Stat label="Активных занятий" value={monitoring.length} tone={monitoring.length > 0 ? 'warn' : 'ok'} hint="сейчас выполняются" />
        <Stat label="Занятий сегодня" value={todaySessions} hint={today} />
        <Stat label="Всего сессий" value={analytics?.total_sessions ?? '—'} hint={`завершено ${analytics?.completed_sessions ?? 0}`} />
        <Stat label="Средний балл" value={analytics?.avg_score.toFixed(1) ?? '—'} tone="accent" hint="по завершённым сессиям" />
      </Grid>

      <div className="hero-row">
        <div className="hero-main">
          <Card
            title="Операторы на тренажёре"
            subtitle="Активные сессии"
            actions={<Link className="linklike" to="/instructor/monitoring">Мониторинг →</Link>}
          >
            {monitoring.length === 0 ? (
              <Empty text="Сейчас никто не выполняет задания" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Оператор</th>
                      <th>Задание</th>
                      <th>Сценарий</th>
                      <th>Действий</th>
                      <th>Ошибок</th>
                      <th>Аварий</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monitoring.map((op) => (
                      <tr key={op.session_id}>
                        <td className="bold">{op.full_name || op.username}</td>
                        <td>{op.scenario_name || op.scenario_id}</td>
                        <td className="muted">{op.scenario_id}</td>
                        <td className="num">{op.actions_count}</td>
                        <td className="num">{op.errors_count}</td>
                        <td className="num">{op.alarms.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
        <div className="hero-side">
          <Card title="Динамика обучения" subtitle="Средний балл по дням">
            {analytics && analytics.learning_dynamics.length > 0 ? (
              <div className="col">
                {analytics.learning_dynamics.slice(-7).reverse().map((d) => (
                  <div key={d.date} className="row-between" style={{ fontSize: 12 }}>
                    <span className="muted num">{fmtDate(new Date(`${d.date}T00:00:00`).getTime() / 1000)}</span>
                    <span className="num bold">{d.avg_score.toFixed(1)} · {d.count} сес.</span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty text="Данных по динамике пока нет" />
            )}
          </Card>
        </div>
      </div>
    </Page>
  );
}
