import { api } from '../../api';
import type { LmsMonitorOperator } from '../../types';
import { Card, Chip, Empty, Err, Loader, Page, fmtClock, usePoll } from '../../lms/ui';

export default function MonitoringPage() {
  const { data, error, loading } = usePoll<LmsMonitorOperator[]>(() => api.lmsMonitoring(), 4000);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;

  const ops = data ?? [];

  return (
    <Page
      title="Мониторинг"
      subtitle="Живой контроль операторов за работой на тренажёре (обновление каждые 4 с)"
    >
      <Card>
        {ops.length === 0 ? (
          <Empty text="Активных сессий нет" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Оператор</th>
                  <th>Задание</th>
                  <th>Симуляция</th>
                  <th>Действий</th>
                  <th>Ошибок</th>
                  <th>Текущее действие</th>
                  <th>Активные аварии</th>
                </tr>
              </thead>
              <tbody>
                {ops.map((op) => (
                  <tr key={op.session_id}>
                    <td>
                      <div className="bold">{op.full_name || op.username}</div>
                      <div className="muted" style={{ fontSize: 11 }}>{op.session_id.slice(0, 16)}</div>
                    </td>
                    <td>
                      <div>{op.scenario_name || op.scenario_id}</div>
                      <div className="muted" style={{ fontSize: 11 }}>{op.scenario_id}</div>
                    </td>
                    <td className="num bold">{fmtClock(op.sim_time)}</td>
                    <td className="num">{op.actions_count}</td>
                    <td className="num" style={{ color: op.errors_count > 0 ? 'var(--danger)' : 'inherit' }}>
                      {op.errors_count}
                    </td>
                    <td className="muted" style={{ fontSize: 11.5, maxWidth: 260 }}>
                      {op.last_action
                        ? `${String(op.last_action.action_type ?? '')} ${String(op.last_action.equipment_id ?? '')}`
                        : '—'}
                    </td>
                    <td>
                      {op.alarms.length === 0 ? (
                        <Chip tone="ok">0</Chip>
                      ) : (
                        <Chip tone="bad">⚠ {op.alarms.length}</Chip>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {ops.length > 0 && (
        <Card title="Тревоги по сессиям" subtitle="Последние события аварий">
          {ops.map((op) =>
            op.alarms.length > 0 ? (
              <div key={op.session_id} style={{ marginBottom: 10 }}>
                <div className="muted bold" style={{ fontSize: 12, marginBottom: 4 }}>
                  {op.full_name || op.username} · {op.scenario_name || op.scenario_id}
                </div>
                <div className="table-wrap">
                  <table className="table" style={{ fontSize: 11.5 }}>
                    <thead>
                      <tr>
                        <th>Время</th>
                        <th>Тег</th>
                        <th>Значение</th>
                        <th>Описание</th>
                      </tr>
                    </thead>
                    <tbody>
                      {op.alarms.slice(0, 10).map((a, i) => (
                        <tr key={i}>
                          <td className="num">{fmtClock(Number(a.timestamp ?? 0))}</td>
                          <td className="mono">{String(a.parameter ?? '—')}</td>
                          <td className="num">{a.actual_value != null ? Number(a.actual_value).toFixed(1) : '—'}</td>
                          <td className="muted">{String(a.description ?? '—')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null,
          )}
        </Card>
      )}
    </Page>
  );
}
