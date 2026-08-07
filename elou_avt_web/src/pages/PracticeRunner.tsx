import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import type { LmsPracticeTask } from '../types';
import { MnemoPanel } from '../mnemo/MnemoPanel';
import { useSimulation } from '../lms/sim';
import { Err, Loader, notifyToast } from '../lms/ui';

export default function PracticeRunner() {
  const { taskId } = useParams<{ taskId: string }>();
  const [params] = useSearchParams();
  const moduleId = params.get('module');
  const { user } = useAuth();
  const navigate = useNavigate();

  const sim = useSimulation();
  const [task, setTask] = useState<LmsPracticeTask | null>(null);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  const run = useCallback(async () => {
    if (!taskId) return;
    setError('');
    try {
      const t = await api.lmsPracticeTask(Number(taskId));
      setTask(t);
      const session = await api.startTrainingSession(t.scenario_id, user?.username ?? 'operator');
      setSessionId(session.session_id);
      await api.startScenario(t.scenario_id);
      await sim.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [taskId, user, sim]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const finish = async () => {
    setBusy(true);
    try {
      const s = await api.finishTrainingSession();
      if (moduleId && s.performance_score != null) {
        try {
          await api.lmsModuleComplete(Number(moduleId), s.performance_score, s.session_id);
        } catch {
          /* модуль без привязки — не критично */
        }
      }
      navigate(`/debrief/${s.session_id}`, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  const abort = async () => {
    try {
      await api.finishTrainingSession();
    } catch {
      /* нет активной сессии — просто выход */
    }
    navigate('/practice', { replace: true });
  };

  return (
    <div className="hmi-scope practice-frame">
      <div className="practice-bar">
        <span className="practice-bar-title">{task?.title ?? 'Практическое задание'}</span>
        {task?.scenario_name && <span className="muted">{task.scenario_name}</span>}
        {sessionId && <span className="muted mono">сессия {sessionId.slice(0, 12)}</span>}
        <span className="grow" />
        <span className={`chip ${sim.connected ? 'chip-ok' : 'chip-bad'}`}>
          <span className="dot" /> {sim.connected ? 'LIVE' : 'НЕТ СВЯЗИ'}
        </span>
        <span className="chip chip-info">t = {(sim.live?.simulation_time ?? 0).toFixed(0)} с</span>
        <span className={`chip ${(sim.live?.alarms?.length ?? 0) > 0 ? 'chip-alarm' : 'chip-ok'}`}>
          ⚠ {(sim.live?.alarms?.length ?? 0)} аварий
        </span>
        <button className="btn btn-stop" disabled={busy} onClick={() => void abort()}>
          Прервать
        </button>
        <button className="btn btn-start" disabled={busy} onClick={() => void finish()}>
          Завершить задание
        </button>
      </div>

      {error ? (
        <div style={{ padding: 20 }}>
          <Err text={error} />
          <button className="btn" style={{ marginTop: 10 }} onClick={() => void run()}>
            Повторить запуск
          </button>
        </div>
      ) : !task ? (
        <Loader text="Загрузка задания и запуск сценария…" />
      ) : (
        <div className="mnemo-wrap">
          <MnemoPanel
            live={sim.live}
            refresh={sim.refresh}
            history={sim.history}
            user={user?.username ?? '—'}
            connected={sim.connected}
          />
        </div>
      )}
    </div>
  );
}
