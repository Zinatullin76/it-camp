import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiState } from '../types';
import { api } from '../api';
import type { MnemoItem, MnemoData } from './mnemoTypes';
import dataRaw from './mnemoData.json';
import { buildLive, fmtSimTime } from './sources';
import { MnemoScreen } from './MnemoScreen';

const data = dataRaw as MnemoData;

interface Props {
  live: ApiState | null;
  refresh: () => Promise<void> | void;
}

const K_MIN = 0.35;
const K_MAX = 4;

export function MnemoPanel({ live, refresh }: Props) {
  const [cur, setCur] = useState<string>(data.order[0]);
  const [k, setK] = useState(1);
  const [pan, setPan] = useState({ tx: 0, ty: 0 });
  const [sel, setSel] = useState<{ idx: number; item: MnemoItem } | null>(null);
  const [sp, setSp] = useState('');
  const [out, setOut] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  const liveVals = useMemo(() => buildLive(live), [live]);
  const screen = data.screens[cur];

  const ctrl = sel?.item.ctrl ? live?.controllers?.[sel.item.ctrl] : undefined;

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

  const feedTH = live?.feed ? live.feed.flow_kg_s * 3.6 : 0;

  return (
    <div className="mnemo">
      <div className="mnemo-tabs">
        <div className="mnemo-tabs-scroll">
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
        <div className="mnemo-kpis">
          <span className="mnemo-kpi">⏱ {fmtSimTime(live?.simulation_time ?? 0)}</span>
          <span className="mnemo-kpi">Сырьё <b>{feedTH.toFixed(1)}</b> т/ч</span>
          <span className="mnemo-kpi">Продукт <b>{((live?.product_flow ?? 0) * 3.6).toFixed(1)}</b> т/ч</span>
          <span className={`mnemo-kpi ${(live?.alarms?.length ?? 0) > 0 ? 'kpi-alarm' : ''}`}>
            ⚠ {(live?.alarms?.length ?? 0)}
          </span>
        </div>
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
              selected={sel?.idx ?? null}
              onSelect={(idx, item) => setSel({ idx, item })}
              onDeselect={() => setSel(null)}
            />
          </div>
          <div className="mnemo-hint">
            колесо — масштаб · зажать — перемещение · клик по регулятору — панель
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
          ) : sel ? (
            <div className="fp-empty">Выбран объект без регулятора</div>
          ) : (
            <div className="fp-empty">
              Выберите регулятор на схеме (бирюзовая рамка — кликабельный прибор) для открытия лицевой панели.
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
    </div>
  );
}
