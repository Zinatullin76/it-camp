import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import type { LmsPracticeTask } from '../types';
import ScadaScheme from '../scada/ScadaScheme';
import { useSimulation } from '../lms/sim';
import { Err, Loader, fmtClock } from '../lms/ui';

const SEVERITY_LABELS: Record<string, string> = {
  CRITICAL: 'Критическая',
  HIGH: 'Высокая',
  WARNING: 'Предупреждение',
  LOW: 'Низкая',
};

export default function PracticeRunner() {
  const { taskId } = useParams<{ taskId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const sim = useSimulation();
  const [task, setTask] = useState<LmsPracticeTask | null>(null);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [sessionSimStart, setSessionSimStart] = useState(0);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [alarmsOpen, setAlarmsOpen] = useState(false);
  const started = useRef(false);
  const readySession = useRef('');
  const knownAlarmIds = useRef(new Set<string>());

  const activeAlarms = sim.live?.alarms ?? [];
  const alarmHistory = sim.live?.alarm_history ?? activeAlarms;
  const activeAlarmIds = new Set(activeAlarms.map((alarm) => alarm.id));

  const run = useCallback(async () => {
    if (!taskId) return;
    setError('');
    setSessionId('');
    setSessionSimStart(0);
    setReady(false);
    setAlarmsOpen(false);
    knownAlarmIds.current.clear();
    readySession.current = '';
    sim.reset();
    try {
      const t = await api.lmsPracticeCatalogTask(Number(taskId));
      setTask(t);
      const session = await api.lmsPracticeStart(t.module_id ?? 0);
      await sim.refresh();
      setSessionId(session.session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [taskId, sim]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || alarmHistory.length === 0) return;
    const hasNewAlarm = alarmHistory.some((alarm) => !knownAlarmIds.current.has(alarm.id));
    alarmHistory.forEach((alarm) => knownAlarmIds.current.add(alarm.id));
    if (hasNewAlarm) setAlarmsOpen(true);
  }, [alarmHistory, ready]);

  useEffect(() => {
    if (!alarmsOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setAlarmsOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [alarmsOpen]);

  const finish = async () => {
    if (!sessionId || !ready) return;
    setBusy(true);
    try {
      const a = await api.lmsPracticeFinish(sessionId);
      navigate(`/debrief/${a.session_id ?? sessionId}`, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  const markReady = useCallback(async () => {
    if (!sessionId || readySession.current === sessionId) return;
    readySession.current = sessionId;
    try {
      const startedSession = await api.lmsPracticeReady(sessionId);
      setSessionSimStart(startedSession.sim_time);
      await sim.refresh();
      setReady(true);
    } catch (e) {
      readySession.current = '';
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [sessionId, sim]);

  const abort = async () => {
    navigate('/practice', { replace: true });
  };

  return (
    <div className="practice-frame">
      <div className="practice-bar">
        <span className="practice-bar-title">{task?.title ?? 'Практическое задание'}</span>
        {task?.scenario_name && <span className="muted">{task.scenario_name}</span>}
        {sessionId && <span className="muted mono">сессия {sessionId.slice(0, 12)}</span>}
        <span className="grow" />
        <span className={`chip ${sim.connected ? 'chip-ok' : 'chip-bad'}`}>
          <span className="dot" /> {sim.connected ? 'LIVE' : 'НЕТ СВЯЗИ'}
        </span>
        <span className="chip chip-info">
          t = {Math.max(0, (sim.live?.simulation_time ?? sessionSimStart) - sessionSimStart).toFixed(0)} с
        </span>
        <button
          type="button"
          className={`chip practice-alarm-trigger ${activeAlarms.length > 0 ? 'chip-alarm' : 'chip-ok'}`}
          aria-expanded={alarmsOpen}
          aria-controls="practice-alarm-panel"
          onClick={() => setAlarmsOpen((open) => !open)}
        >
          <span aria-hidden="true">⚠</span>
          {activeAlarms.length > 0
            ? `${activeAlarms.length} активных тревог`
            : `Журнал аварий${alarmHistory.length > 0 ? ` · ${alarmHistory.length}` : ''}`}
        </button>
        <button className="btn btn-stop" disabled={busy} onClick={() => void abort()}>
          Прервать
        </button>
        <button className="btn btn-start" disabled={busy || !ready} onClick={() => void finish()}>
          Завершить задание
        </button>
      </div>

      {alarmsOpen && (
        <section id="practice-alarm-panel" className="practice-alarm-panel" aria-label="Журнал аварий">
          <div className="practice-alarm-head">
            <div>
              <strong>Журнал аварий</strong>
              <span>{activeAlarms.length} активных · {alarmHistory.length} за сессию</span>
            </div>
            <button
              type="button"
              className="practice-alarm-close"
              aria-label="Закрыть журнал аварий"
              title="Закрыть"
              onClick={() => setAlarmsOpen(false)}
            >
              ×
            </button>
          </div>
          {alarmHistory.length === 0 ? (
            <div className="practice-alarm-empty">Аварий в текущей сессии нет</div>
          ) : (
            <div className="practice-alarm-list">
              {[...alarmHistory].reverse().map((alarm) => {
                const active = activeAlarmIds.has(alarm.id);
                return (
                  <article className={`practice-alarm-row severity-${alarm.severity.toLowerCase()}`} key={alarm.id}>
                    <div className="practice-alarm-row-top">
                      <time>{fmtClock(Math.max(0, alarm.timestamp - sessionSimStart))}</time>
                      <span className={active ? 'alarm-state-active' : 'alarm-state-cleared'}>
                        {active ? 'АКТИВНА' : 'СНЯТА'}
                      </span>
                      <span>{SEVERITY_LABELS[alarm.severity] ?? alarm.severity}</span>
                    </div>
                    <strong>{alarm.description || alarm.parameter}</strong>
                    <div className="practice-alarm-values">
                      <span className="mono">{alarm.parameter}</span>
                      <span>Значение: {alarm.actual_value}</span>
                      <span>Порог: {alarm.threshold}</span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {error ? (
        <div style={{ padding: 20 }}>
          <Err text={error} />
          <button className="btn" style={{ marginTop: 10 }} onClick={() => void run()}>
            Повторить запуск
          </button>
        </div>
      ) : !task || !sessionId ? (
        <Loader text="Загрузка задания и запуск сценария…" />
      ) : (
        <div className="mnemo-wrap">
          <ScadaScheme
            key={sessionId}
            live={sim.live}
            user={user?.username}
            onReady={() => void markReady()}
          />
        </div>
      )}
    </div>
  );
}
