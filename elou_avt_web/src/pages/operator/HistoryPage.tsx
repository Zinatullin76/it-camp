import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import type { LmsHistoryRow } from '../../types';
import { Card, Chip, Empty, Err, Loader, Page, fmtDate, fmtDateTime, fmtDur, useAsync } from '../../lms/ui';

function scoreTone(n: number | null): 'ok' | 'warn' | 'bad' | 'muted' {
  if (n == null) return 'muted';
  if (n >= 80) return 'ok';
  if (n >= 60) return 'warn';
  return 'bad';
}

export default function HistoryPage() {
  const { data, error, loading, reload } = useAsync<LmsHistoryRow[]>(() => api.lmsHistory(200), []);
  const navigate = useNavigate();

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const rows = data ?? [];

  return (
    <Page
      title="История обучения"
      subtitle="Таблица всех выполненных занятий"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Card>
        {rows.length === 0 ? (
          <Empty text="История пуста — пройдите первое задание" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Курс / задание</th>
                  <th>Оценка</th>
                  <th>Время</th>
                  <th>Длительность</th>
                  <th>Квалификация</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.session_id}
                    className="clickable"
                    onClick={() => navigate(`/debrief/${r.session_id}`)}
                    title="Открыть разбор выполнения"
                  >
                    <td className="num">{fmtDateTime(r.wall_start)}</td>
                    <td className="bold">
                      {r.task_title || r.scenario_name || r.scenario_id}
                      <div className="muted" style={{ fontSize: 11 }}>{r.scenario_name || r.scenario_id}</div>
                    </td>
                    <td className="num bold">{r.performance_score != null ? r.performance_score.toFixed(0) : '—'}</td>
                    <td className="num">{r.duration_s != null ? fmtDur(r.duration_s) : '—'}</td>
                    <td className="num">{r.wall_end ? fmtDur((r.wall_end - r.wall_start)) : '—'}</td>
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
