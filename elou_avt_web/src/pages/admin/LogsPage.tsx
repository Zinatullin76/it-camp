import { api } from '../../api';
import type { SystemLogEntry } from '../../types';
import { Card, Empty, Err, Loader, Page, fmtDateTime, useAsync } from '../../lms/ui';

export default function LogsPage() {
  const { data, error, loading, reload } = useAsync<SystemLogEntry[]>(() => api.lmsLogs(300), []);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const logs = data ?? [];

  return (
    <Page
      title="Журнал системы"
      subtitle="Лог операций и событий платформы"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Card>
        {logs.length === 0 ? (
          <Empty text="Записей журнала нет" />
        ) : (
          <div className="table-wrap">
            <table className="table" style={{ fontSize: 11.5 }}>
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Уровень</th>
                  <th>Пользователь</th>
                  <th>Категория</th>
                  <th>Сообщение</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="num muted">{fmtDateTime(l.timestamp)}</td>
                    <td><span className={`log-lvl ${l.level}`}>{l.level}</span></td>
                    <td className="mono">{l.username || '—'}</td>
                    <td className="muted">{l.category}</td>
                    <td>{l.message}</td>
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
