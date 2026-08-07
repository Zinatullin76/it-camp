import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiState, HistoryResponse } from '../types';
import { api } from '../api';
import type { MnemoItem, MnemoData } from './mnemoTypes';
import dataRaw from './mnemoData.json';
import { buildLive, fmtSimTime, fmtVal, PUMP_PARAMS } from './sources';
import { MnemoScreen } from './MnemoScreen';
import TrendChart, { SERIES_META } from '../components/TrendChart';

const data = dataRaw as MnemoData;

interface Props {
  live: ApiState | null;
  refresh: () => Promise<void> | void;
  history: HistoryResponse | null;
  user: string;
  connected: boolean;
}

const K_MIN = 0.35;
const K_MAX = 4;

const DISP_KEY = 'mnemo-disp-v1';

function loadDisp(): Record<string, string[]> {
  try {
    return JSON.parse(localStorage.getItem(DISP_KEY) ?? '{}');
  } catch {
    return {};
  }
}

function saveDisp(d: Record<string, string[]>) {
  try {
    localStorage.setItem(DISP_KEY, JSON.stringify(d));
  } catch {
    // ignore storage errors
  }
}

export function MnemoPanel({ live, refresh, history, user, connected }: Props) {
  const [cur, setCur] = useState<string>(data.order[0]);
  const [k, setK] = useState(1);
  const [pan, setPan] = useState({ tx: 0, ty: 0 });
  const [sel, setSel] = useState<{ idx: number; item: MnemoItem } | null>(null);
  const [sp, setSp] = useState('');
  const [out, setOut] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [now, setNow] = useState(() => new Date());
  const [trendParam, setTrendParam] = useState('column_pressure_bar');
  const [disp, setDisp] = useState<Record<string, string[]>>(loadDisp);
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const liveVals = useMemo(() => buildLive(live), [live]);
  const screen = data.screens[cur];

  const alarms = live?.alarms ?? [];
  const critical = alarms.some((a) => a.severity === 'CRITICAL');
  const mode = alarms.length === 0 ? 'НОРМА' : critical ? 'АВАРИЯ' : 'ВНИМАНИЕ';
  const modeCls = alarms.length === 0 ? 'mode-norm' : critical ? 'mode-alarm' : 'mode-warn';

  const ctrl = sel?.item.ctrl ? live?.controllers?.[sel.item.ctrl] : undefined;
  const pumpNode = sel?.item.n ? liveVals.equip(sel.item.n) : undefined;
  const pumpTelemetry = pumpNode ? live?.equipment?.[pumpNode] : undefined;
  const pumpState = pumpNode ? liveVals.run(sel!.item.n!) : 'unknown';

  const pumpAction = async (t: string) => {
    if (!pumpNode) return;
    setBusy(true);
    setErr('');
    try {
      await api.action(pumpNode, t);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleDisp = (label: string, key: string) => {
    setDisp((d) => {
      const cur = d[label] ?? [];
      const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
      const nd = { ...d, [label]: next };
      saveDisp(nd);
      return nd;
    });
  };

  useEffect(() => {
    if (ctrl) {
      setSp(String(ctrl.sp));
      setOut(String(Math.round(ctrl.out)));
    }
  }, [ctrl?.tag, ctrl?.sp, ctrl?.out]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSel(null);
  }, [cur]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    setK((prev) => Math.min(K_MAX, Math.max(K_MIN, prev * (e.deltaY < 0 ? 1.12 : 0.89))));
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, tx: 0, ty: 0 };
    setPan((p) => {
      if (drag.current) {
        drag.current.tx = p.tx;
        drag.current.ty = p.ty;
      }
      return p;
    });
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return;
    setPan({
      tx: drag.current.tx + (e.clientX - drag.current.x),
      ty: drag.current.ty + (e.clientY - drag.current.y),
    });
  }, []);

  const onPointerUp = useCallback(() => {
    drag.current = null;
  }, []);

  const send = useCallback(
    async (tag: string, action: string, value?: number | string | null) => {
      setBusy(true);
      setErr('');
      try {
        await api.command(tag, action, value ?? null);
        await refresh();
      } catch (e) {
        setErr(String(e));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const setMode = (mode: 'АВТ' | 'РУЧ') => {
    if (sel?.item.ctrl) void send(sel.item.ctrl, 'SET_MODE', mode);
  };

  const submitSp = () => {
    const v = parseFloat(sp);
    if (sel?.item.ctrl && Number.isFinite(v)) void send(sel.item.ctrl, 'SET_SP', v);
  };

  const submitOut = () => {
    const v = parseFloat(out);
    if (sel?.item.ctrl && Number.isFinite(v)) void send(sel.item.ctrl, 'SET_VALUE', v);
  };

  return (
    <div className="mnemo">
      <div className="mnemo-tabs">
        <div className="mnemo-left">
          <span className="mnemo-plant">УСТАНОВКА ЭЛОУ-АВТ</span>
          <span className={`mnemo-mode ${modeCls}`}>{mode}</span>
        </div>
        <div className="mnemo-right">
          <span className="mnemo-kpi">👤 {user}</span>
          <span className={`mnemo-link ${connected ? 'link-ok' : 'link-bad'}`}>
            <span className="dot" /> {connected ? 'СВЯЗЬ ЕСТЬ' : 'ОТКЛЮЧЕНО'}
          </span>
          <span className="mnemo-clock">{now.toLocaleTimeString('ru-RU')}</span>
          <span className={`mnemo-kpi ${alarms.length > 0 ? 'kpi-alarm' : ''}`}>⚠ {alarms.length}</span>
        </div>
      </div>

      <div className="mnemo-screens">
        {data.order.map((id) => (
          <button
            key={id}
            className={`mnemo-tab ${id === cur ? 'on' : ''}`}
            onClick={() => setCur(id)}
          >
            {data.screens[id].name}
          </button>
        ))}
      </div>

      <div className="mnemo-body">
        <div
          className="mnemo-stage"
          ref={stageRef}
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          <div
            className="mnemo-pan"
            style={{ transform: `translate(${pan.tx}px, ${pan.ty}px) scale(${k})` }}
          >
            <MnemoScreen
              data={screen}
              live={liveVals}
              disp={disp}
              selected={sel?.idx ?? null}
              onSelect={(idx, item) => setSel({ idx, item })}
              onDeselect={() => setSel(null)}
            />
          </div>
          <div className="mnemo-hint">
            колесо — масштаб · зажать — перемещение · клик по оборудованию — панель
          </div>
        </div>

        <div className="mnemo-side">
          {sel && sel.item.ctrl && ctrl ? (
            <div className="fp">
              <div className="fp-title">{ctrl.tag}</div>
              <div className="fp-desc">{ctrl.desc}</div>
              <div className="fp-unit">{ctrl.unit} · {ctrl.cascade ? `каскад ← ${ctrl.cascade}` : ctrl.tracked ? 'слежение' : 'автономный'}</div>

              <div className="fp-row">
                <span className="fp-lbl">ПВ</span>
                <span className="fp-pv">{ctrl.pv.toFixed(ctrl.pv < 10 ? 2 : 1)}</span>
              </div>
              <div className="fp-row">
                <span className="fp-lbl">ЗАД</span>
                <input
                  className="fp-input"
                  type="number"
                  value={sp}
                  step="any"
                  onChange={(e) => setSp(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitSp()}
                />
                <button className="fp-btn" disabled={busy || ctrl.man} onClick={submitSp} title={ctrl.man ? 'Ручной клапан — только РУЧ' : ''}>
                  ok
                </button>
              </div>
              <div className="fp-row">
                <span className="fp-lbl">ВЫХ</span>
                <input
                  className="fp-input"
                  type="number"
                  value={out}
                  step="any"
                  disabled={ctrl.mode === 'АВТ'}
                  onChange={(e) => setOut(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitOut()}
                />
                <span className="fp-pct">%</span>
              </div>
              <div className="fp-mode">
                <button
                  className={`fp-btn ${ctrl.mode === 'АВТ' ? 'fp-btn-on' : ''}`}
                  disabled={busy || ctrl.man}
                  onClick={() => setMode('АВТ')}
                >
                  АВТ
                </button>
                <button
                  className={`fp-btn ${ctrl.mode === 'РУЧ' ? 'fp-btn-on' : ''}`}
                  disabled={busy}
                  onClick={() => setMode('РУЧ')}
                >
                  РУЧ
                </button>
                <span className="fp-mode-val">{ctrl.mode}</span>
              </div>
              <div className="fp-bar">
                <div className="fp-bar-fill" style={{ width: `${Math.max(0, Math.min(100, ctrl.out))}%` }} />
              </div>
              {ctrl.man ? <div className="fp-note">ручной клапан — управление только в режиме РУЧ</div> : null}
              {err ? <div className="fp-err">{err}</div> : null}
            </div>
          ) : sel && pumpNode ? (
            <div className="fp">
              <div className="fp-title">НАСОС {sel.item.n}</div>
              <div className="fp-desc">{pumpTelemetry?.name ?? 'Насос'}</div>
              <div className="fp-unit">{pumpNode}</div>
              <div className="fp-row">
                <span className="fp-lbl">Статус</span>
                <span className={`fp-pv fp-state st-${pumpState}`}>
                  {pumpState === 'run' ? 'Работает' : pumpState === 'fail' ? 'ОТКАЗ' : pumpState === 'off' ? 'Остановлен' : '—'}
                </span>
              </div>
              <div className="fp-actions">
                <button
                  className="fp-btn fp-btn-start"
                  disabled={busy || pumpState === 'run'}
                  onClick={() => void pumpAction('TURN_ON')}
                >
                  ПУСК
                </button>
                <button
                  className="fp-btn fp-btn-stop"
                  disabled={busy || pumpState !== 'run'}
                  onClick={() => void pumpAction('TURN_OFF')}
                >
                  СТОП
                </button>
              </div>
              <div className="fp-params-title">Показывать на схеме</div>
              {PUMP_PARAMS.map(([key, label]) => {
                const v = pumpTelemetry?.params?.[key];
                const num = typeof v === 'number' && Number.isFinite(v) ? v : null;
                const on = (disp[sel.item.n ?? ''] ?? []).includes(key);
                return (
                  <label key={key} className="fp-param">
                    <input type="checkbox" checked={on} onChange={() => toggleDisp(sel.item.n ?? '', key)} />
                    <span className="fp-lbl">{label}</span>
                    <span className="fp-pv">{fmtVal(num)}</span>
                  </label>
                );
              })}
              {err ? <div className="fp-err">{err}</div> : null}
            </div>
          ) : sel ? (
            <div className="fp-empty">Выбран объект без регулятора</div>
          ) : (
            <div className="fp-empty">
              Выберите оборудование на схеме, чтобы открыть лицевую панель (Faceplate).
            </div>
          )}
        </div>
      </div>

      <div className="mnemo-legend">
        {Object.entries(data.flows).map(([f, v]) => (
          <span key={f} className="mnemo-flow">
            <span className="mnemo-flow-dot" style={{ background: v.c }} />
            {v.n}
          </span>
        ))}
      </div>

      <div className="mnemo-bottom">
        <div className="mnemo-alarms">
          <div className="panel-title">ALARM LIST</div>
          {alarms.length === 0 ? (
            <div className="mnemo-alarms-empty">Аварий нет</div>
          ) : (
            <div className="alarm-table-wrap">
              <table className="alarm-table">
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>Приоритет</th>
                    <th>Тег</th>
                    <th>Описание</th>
                  </tr>
                </thead>
                <tbody>
                  {alarms.map((a) => (
                    <tr
                      key={a.id}
                      className={`alarm-row sev-${a.severity.toLowerCase()}`}
                    >
                      <td>{fmtSimTime(a.timestamp)}</td>
                      <td>{a.severity}</td>
                      <td>{a.parameter}</td>
                      <td className="alarm-desc">{a.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="mnemo-trend">
          <div className="panel-title">ТРЕНД</div>
          <select
            className="scenario-select full"
            value={trendParam}
            onChange={(e) => setTrendParam(e.target.value)}
          >
            {Object.entries(SERIES_META).map(([kk, m]) => (
              <option key={kk} value={kk}>{m.label} ({m.unit})</option>
            ))}
          </select>
          <TrendChart history={history} param={trendParam} height={150} />
        </div>
      </div>
    </div>
  );
}
