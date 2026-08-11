import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import type { LmsReportRow } from '../../types';
import { Card, Chip, Empty, Err, Loader, Page, fmtDateTime, fmtDur, useAsync } from '../../lms/ui';

export default function ReportsPage() {
  const { data, error, loading, reload } = useAsync<LmsReportRow[]>(() => api.lmsReports(200), []);
  const navigate = useNavigate();

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const rows = data ?? [];

  return (
    <Page
      title="Отчёты о практиках"
      subtitle="Пройденные практики операторов с результатами"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Card>
        {rows.length === 0 ? (
          <Empty text="Отчётов пока нет — операторы ещё не завершали практики" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Оператор</th>
                  <th>Задание</th>
                  <th>Оценка</th>
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
                    onClick={() => navigate(`/instructor/reports/${r.session_id}`)}
                    title="Открыть отчёт о выполнении"
                  >
                    <td className="num">{fmtDateTime(r.wall_start)}</td>
                    <td className="bold">
                      {r.full_name || r.operator_id}
                      <div className="muted" style={{ fontSize: 11 }}>{r.operator_id}</div>
                    </td>
                    <td className="bold">
                      {r.task_title || r.scenario_name || r.scenario_id}
                      <div className="muted" style={{ fontSize: 11 }}>{r.scenario_name || r.scenario_id}</div>
                    </td>
                    <td className="num bold">{r.performance_score != null ? r.performance_score.toFixed(0) : '—'}</td>
                    <td className="num">{r.duration_s != null ? fmtDur(r.duration_s) : '—'}</td>
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
