import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

interface SessionRow {
  id: string;
  scenario_id: string;
  status: string;
  operator_id?: string;
  performance_score?: number | null;
  ai_verdict?: unknown;
  wall_start?: number;
  wall_end?: number | null;
}

function fmtTime(t?: number | null): string {
  if (!t) return '—';
  return new Date(t * 1000).toLocaleString('ru-RU');
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<{
    actions: unknown[];
    snapshots: unknown[];
    alarms: unknown[];
    error_events: unknown[];
  } | null>(null);

  const reload = useCallback(async () => {
    try {
      setSessions(await api.listTrainingSessions());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить журнал');
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const toggle = async (id: string) => {
    if (expanded === id) {
      setExpanded(null);
      setDetails(null);
      return;
    }
    try {
      const data = await api.getTrainingSession(id);
      setDetails(data);
      setExpanded(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки сессии');
    }
  };

  return (
    <div className="admin-wrap">
      <div className="admin">
        <div className="dash-hero">
          <div>
            <div className="dash-hero-title">Журнал тренировок</div>
            <div className="dash-empty">
              Персистентный лог сессий (датасет для ИИ-классификации ошибок)
            </div>
          </div>
          <button className="btn" onClick={() => void reload()}>
            Обновить
          </button>
        </div>

        {error && <div className="login-error">{error}</div>}

        <div className="dash-card">
          {sessions.length === 0 && <div className="dash-empty">Сессий пока нет</div>}
          {sessions.map((s) => (
            <div key={s.id}>
              <div className="user-row">
                <span
                  className="status-dot"
                  style={{
                    background:
                      s.status === 'COMPLETED'
                        ? 'var(--ok)'
                        : s.status === 'ABORTED'
                          ? 'var(--danger)'
                          : 'var(--warn)',
                  }}
                />
                <span className="user-name">
                  {s.id}
                  <span className="dash-id-sub"> {s.operator_id}</span>
                </span>
                <span className="user-meta">
                  <span>{s.scenario_id}</span>
                  <span className="perm-tag on">{s.status}</span>
                </span>
                <span className="user-meta">
                  Оценка:{' '}
                  <b>{s.performance_score != null ? s.performance_score.toFixed(1) : '—'}</b>
                </span>
                <span className="user-meta">{fmtTime(s.wall_start)}</span>
                <button className="btn" onClick={() => void toggle(s.id)}>
                  {expanded === s.id ? 'Свернуть' : 'Экспорт'}
                </button>
              </div>
              {expanded === s.id && details && (
                <div className="dash-group">
                  <div className="dash-group-title">
                    <span>Экспорт сессии {s.id}</span>
                    <span className="dash-count">
                      действия {details.actions.length} · снапшоты {details.snapshots.length} ·
                      алармы {details.alarms.length} · ошибки {details.error_events.length}
                    </span>
                  </div>
                  <pre
                    style={{
                      background: 'var(--panel-2)',
                      borderRadius: 6,
                      padding: 10,
                      overflow: 'auto',
                      maxHeight: 320,
                      fontSize: 11,
                      color: 'var(--muted)',
                    }}
                  >
                    {JSON.stringify(details, null, 1)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
