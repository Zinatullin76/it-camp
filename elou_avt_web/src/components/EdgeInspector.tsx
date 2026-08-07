import { useState } from 'react';
import type { Edge } from '@xyflow/react';
import { PHASE_TYPES, phaseMeta, contrastText, DEFAULT_PHASE } from '../schemeConfig';

interface Props {
  edge: Edge | null;
  onPhase: (edgeId: string, phaseId: string) => void;
  onOffset: (edgeId: string, offset: number) => void;
  canEditScheme?: boolean;
}

const OFFSET_STEP = 6;

export default function EdgeInspector({ edge, onPhase, onOffset, canEditScheme = true }: Props) {
  const phase = edge ? phaseMeta((edge.data as { phase?: string } | undefined)?.phase ?? DEFAULT_PHASE) : phaseMeta(DEFAULT_PHASE);
  const offset = (edge as Edge & { pathOptions?: { offset?: number } }).pathOptions?.offset ?? 0;
  const [draft, setDraft] = useState<string | null>(null);

  if (!edge) {
    return (
      <div className="inspector-empty">
        Кликните по линии на схеме, чтобы задать фазу потока и развести параллельные линии.
      </div>
    );
  }

  const setOffset = (v: number) => {
    const clamped = Math.max(-120, Math.min(120, v));
    onOffset(edge.id, clamped);
  };

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

      <div className="inspector-group-title">РАЗВОДКА ЛИНИИ (сдвиг параллельных)</div>
      <div className="edge-offset-row">
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffset(offset - OFFSET_STEP)} disabled={!canEditScheme}>−</button>
        <input
          className="edge-offset-range"
          type="range"
          min={-120}
          max={120}
          step={2}
          value={offset}
          onChange={(e) => setOffset(Number(e.target.value))}
          disabled={!canEditScheme}
        />
        <button className="btn btn-ghost edge-offset-btn" onClick={() => setOffset(offset + OFFSET_STEP)} disabled={!canEditScheme}>＋</button>
        <span className="edge-offset-val">{offset} px</span>
      </div>
      <div className="inspector-hint">
        Сдвиг перпендикулярно направлению линии. Отрицательные значения — в противоположную сторону. Для
        «разнесения» параллельных линий задайте разным линиям сдвиг в разные стороны.
      </div>
    </div>
  );
}
