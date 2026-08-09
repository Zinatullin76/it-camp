import { useState } from 'react';
import type { Edge } from '@xyflow/react';
import { PHASE_TYPES, phaseMeta, contrastText, DEFAULT_PHASE } from '../schemeConfig';
import { STREAM_PARAMS } from '../schemeConfig';

interface Props {
  edge: Edge | null;
  onPhase: (edgeId: string, phaseId: string) => void;
  onOffset: (edgeId: string, offsetX: number, offsetY: number) => void;
  onUpdateDisp?: (edgeId: string, keys: string[]) => void;
  onDeleteEdge?: (edgeId: string) => void;
  disp?: string[];
  canEditScheme?: boolean;
}

const OFFSET_STEP = 6;
const OFFSET_LIMIT = 160;

export default function EdgeInspector({ edge, onPhase, onOffset, onUpdateDisp, onDeleteEdge, disp = [], canEditScheme = true }: Props) {
  const phase = edge ? phaseMeta((edge.data as { phase?: string } | undefined)?.phase ?? DEFAULT_PHASE) : phaseMeta(DEFAULT_PHASE);
  const pathOptions = (edge as Edge & { pathOptions?: { offsetX?: number; offsetY?: number } }).pathOptions;
  const offsetX = pathOptions?.offsetX ?? 0;
  const offsetY = pathOptions?.offsetY ?? 0;
  const [draft, setDraft] = useState<string | null>(null);

  if (!edge) {
    return (
      <div className="inspector-empty">
        Кликните по линии на схеме, чтобы задать фазу потока, развести/передвинуть линии, показать свойства потока и удалить линию.
      </div>
    );
  }

  const setOffsetX = (v: number) => onOffset(edge.id, Math.max(-OFFSET_LIMIT, Math.min(OFFSET_LIMIT, v)), offsetY);
  const setOffsetY = (v: number) => onOffset(edge.id, offsetX, Math.max(-OFFSET_LIMIT, Math.min(OFFSET_LIMIT, v)));

  return (
    <div>
      <div className="inspector-header" style={{ borderLeft: `3px solid ${phase.color}` }}>
        <div style={{ fontWeight: 700 }}>Поток: {edge.source} → {edge.target}</div>
        <div style={{ fontSize: 10, color: '#7f93a6' }}>{edge.id}</div>
      </div>

      <div className="inspector-group-title">ФАЗА / СРЕДА В ЛИНИИ</div>
      <select
        className="scenario-select full"
        value={draft ?? phase.id}
        onChange={(e) => {
          setDraft(null);
          onPhase(edge.id, e.target.value);
        }}
        disabled={!canEditScheme}
      >
        {PHASE_TYPES.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>
      <div className="edge-swatch" style={{ background: phase.color, color: contrastText(phase.color) }}>
        <span>{phase.label}</span>
      </div>

      <div className="inspector-group-title">РАЗВОДКА ЛИНИИ (по осям)</div>
      <label className="ctrl-label">
        Сдвиг по горизонтали: {offsetX} px
        <input
          className="edge-offset-range"
          type="range"
          min={-OFFSET_LIMIT}
          max={OFFSET_LIMIT}
          step={2}
          value={offsetX}
          onChange={(e) => setOffsetX(Number(e.target.value))}
          disabled={!canEditScheme}
        />
      </label>
      <label className="ctrl-label">
        Сдвиг по вертикали: {offsetY} px
        <input
          className="edge-offset-range"
          type="range"
          min={-OFFSET_LIMIT}
          max={OFFSET_LIMIT}
          step={2}
          value={offsetY}
          onChange={(e) => setOffsetY(Number(e.target.value))}
          disabled={!canEditScheme}
        />
      </label>
      <div className="edge-offset-row">
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffsetX(offsetX - OFFSET_STEP)} disabled={!canEditScheme}>←</button>
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffsetY(offsetY - OFFSET_STEP)} disabled={!canEditScheme}>↑</button>
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffsetX(offsetX + OFFSET_STEP)} disabled={!canEditScheme}>→</button>
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffsetY(offsetY + OFFSET_STEP)} disabled={!canEditScheme}>↓</button>
        <button className="btn btn-ghost edge-offset-btn" onClick={() => { setOffsetX(0); setOffsetY(0); }} disabled={!canEditScheme}>◼</button>
      </div>
      <div className="inspector-hint">
        Перетаскивайте линию мышью или двигайте ползунки. «←→» сдвигают линию вдоль оси OX, «↑↓» — по вертикали.
        Это удобно для разнесения параллельных линий.
      </div>

      {canEditScheme && onUpdateDisp && (
        <div style={{ marginTop: 12 }}>
          <div className="panel-title">ПОКАЗЫВАТЬ НА СХЕМЕ</div>
          <div className="param-list">
            {Object.keys(STREAM_PARAMS).map((k) => {
              const on = disp.includes(k);
              return (
                <label className="param-check" key={k}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => {
                      const next = on ? disp.filter((x) => x !== k) : [...disp, k];
                      onUpdateDisp(edge.id, next);
                    }}
                  />
                  <span>{STREAM_PARAMS[k].label}</span>
                </label>
              );
            })}
          </div>
          <div className="inspector-hint">
            Отмеченные свойства показываются квадратиком у средней части линии. Значения берутся из телеметрии
            узла-источника. Перетаскивайте квадратик, чтобы подвинуть его; ручка в углу меняет размер; двойной клик —
            переименовать подпись.
          </div>
        </div>
      )}

      {canEditScheme && onDeleteEdge && (
        <div style={{ marginTop: 12 }}>
          <button className="btn btn-danger" onClick={() => onDeleteEdge(edge.id)}>🗑 Удалить линию</button>
          <div className="inspector-hint">Также линию можно удалить клавишей Delete/Backspace после клика по ней.</div>
        </div>
      )}
    </div>
  );
}
