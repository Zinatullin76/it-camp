import { memo, useContext } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { BaseEdge, useReactFlow } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import { SchemeEditorContext } from '../nodes/EquipmentNode';
import type { TagCfg } from '../nodes/EquipmentNode';
import { STREAM_PARAMS, phaseMeta, fmtValue } from '../schemeConfig';

/**
 * Поток (ребро мнемосхемы): ортогональная линия с углами 90°.
 * В режиме редактирования линию можно перетаскивать мышью в любом
 * направлении — сдвиг по двум осям (offsetX/offsetY) позволяет развести
 * параллельные линии и передвинуть их вдоль потока.
 * Свойства потока выводятся квадратиками у средней части линии.
 * В режиме SCADA линия некликабельна.
 */

export interface StreamEdgeData {
  phase?: string;
  disp?: string[];
  tags?: Record<string, TagCfg>;
  sourceTelemetry?: {
    failed?: boolean | null;
    params?: Record<string, number | boolean | string | null>;
  } | null;
}

type Point = { x: number; y: number };

const DIR: Record<string, Point> = {
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  top: { x: 0, y: -1 },
  bottom: { x: 0, y: 1 },
};

const LEAD = 20;
const TAG_W = 92;
const TAG_H = 54;
const TAG_STACK = 56;

/**
 * Собственная ортогональная трасса с углами 90°.
 * `offsetX`/`offsetY` сдвигают средний участок линии:
 * перпендикулярно потоку — средний сегмент, вдоль потока — изгибы.
 * Возвращает также точку-якорь для квадратиков свойств.
 */
function orthogonalPath(
  sx: number,
  sy: number,
  sourcePosition: string,
  tx: number,
  ty: number,
  targetPosition: string,
  offsetX: number,
  offsetY: number,
): { path: string; anchor: Point; horizontal: boolean } {
  const s: Point = { x: sx, y: sy };
  const t: Point = { x: tx, y: ty };
  const ds = DIR[sourcePosition] ?? DIR.right;
  const dt = DIR[targetPosition] ?? DIR.left;
  const so: Point = { x: s.x + ds.x * LEAD, y: s.y + ds.y * LEAD };
  const to: Point = { x: t.x + dt.x * LEAD, y: t.y + dt.y * LEAD };

  const horizontalFlow = Math.abs(so.x - to.x) >= Math.abs(so.y - to.y);
  const oppositeX = ds.x !== 0 && dt.x !== 0 && ds.x !== dt.x;
  const oppositeY = ds.y !== 0 && dt.y !== 0 && ds.y !== dt.y;

  let m: number;
  if (oppositeX && oppositeY) {
    m = horizontalFlow ? (s.y + t.y) / 2 : (s.x + t.x) / 2;
  } else {
    m = horizontalFlow ? (so.y + to.y) / 2 : (so.x + to.x) / 2;
  }
  const d = horizontalFlow ? offsetX : offsetY;
  const p = horizontalFlow ? offsetY : offsetX;

  const soPts: Point = horizontalFlow ? { x: so.x + d, y: so.y } : { x: so.x, y: so.y + d };
  const toPts: Point = horizontalFlow ? { x: to.x + d, y: to.y } : { x: to.x, y: to.y + d };
  const corner1: Point = horizontalFlow ? { x: soPts.x, y: m + p } : { x: m + p, y: soPts.y };
  const corner2: Point = horizontalFlow ? { x: toPts.x, y: m + p } : { x: m + p, y: toPts.y };
  const anchor: Point = horizontalFlow
    ? { x: (corner1.x + corner2.x) / 2, y: corner1.y }
    : { x: corner1.x, y: (corner1.y + corner2.y) / 2 };

  let path = `M${s.x} ${s.y}`;
  for (const pt of [soPts, corner1, corner2, toPts]) path += `L${pt.x} ${pt.y}`;
  path += `L${t.x} ${t.y}`;
  return { path, anchor, horizontal: horizontalFlow };
}

function StreamTags({
  id,
  data,
  anchor,
  horizontal,
}: {
  id: string;
  data: StreamEdgeData;
  anchor: Point;
  horizontal: boolean;
}) {
  const { edit, onEdgeTagChange } = useContext(SchemeEditorContext);
  const { getZoom } = useReactFlow();
  const disp = data.disp ?? [];
  const tags = data.tags ?? {};
  const src = data.sourceTelemetry;
  const phase = phaseMeta(data.phase ?? 'crude');

  if (disp.length === 0) return null;

  const startDrag = (e: ReactPointerEvent, key: string, cfg: TagCfg | undefined, index: number) => {
    e.stopPropagation();
    e.preventDefault();
    const zoom = getZoom();
    const baseX = cfg?.dx ?? 0;
    const baseY = cfg?.dy ?? 0;
    const sx = e.clientX;
    const sy = e.clientY;
    const onMove = (ev: PointerEvent) => {
      onEdgeTagChange(id, key, { dx: baseX + (ev.clientX - sx) / zoom, dy: baseY + (ev.clientY - sy) / zoom });
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const startScale = (e: ReactPointerEvent, key: string, cfg: TagCfg | undefined) => {
    e.stopPropagation();
    e.preventDefault();
    const zoom = getZoom();
    const base = cfg?.scale ?? 1;
    const sx = e.clientX;
    const onMove = (ev: PointerEvent) => {
      const scale = Math.max(0.4, Math.min(3, base + (ev.clientX - sx) / 150 / zoom));
      onEdgeTagChange(id, key, { scale });
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const rename = (key: string, cfg: TagCfg | undefined) => {
    const meta = STREAM_PARAMS[key];
    const n = window.prompt('Название квадратика:', cfg?.label ?? meta?.label ?? key);
    if (n !== null) onEdgeTagChange(id, key, { label: n.trim() || undefined });
  };

  return (
    <g>
      {disp.map((k, j) => {
        const cfg = tags[k];
        const meta = STREAM_PARAMS[k];
        const failed = !!src?.failed;
        let text: string;
        if (failed) {
          text = 'ОТКАЗ';
        } else if (k === 'phase') {
          text = phase.label;
        } else {
          const v = src?.params?.[k];
          text = typeof v === 'number' && Number.isFinite(v)
            ? fmtValue(v, meta?.unit ?? '')
            : typeof v === 'boolean'
              ? v ? 'ДА' : 'НЕТ'
              : '—';
        }
        const state = failed ? 'fault' : 'normal';
        const left = horizontal
          ? anchor.x - TAG_W / 2 + (cfg?.dx ?? 0)
          : anchor.x + 18 + j * (TAG_W + 6) + (cfg?.dx ?? 0);
        const top = horizontal
          ? anchor.y + 18 + j * TAG_STACK + (cfg?.dy ?? 0)
          : anchor.y - TAG_H / 2 + (cfg?.dy ?? 0);
        return (
          <foreignObject
            key={k}
            x={left}
            y={top}
            width={TAG_W}
            height={TAG_H}
            style={{ overflow: 'visible', pointerEvents: edit ? 'auto' : 'none' }}
          >
            <div
              className={`mn-node-tag edge-tag state-${state}${edit ? ' tag-editable' : ''}`}
              style={{
                transform: `scale(${cfg?.scale ?? 1})`,
                transformOrigin: '0 0',
              }}
              onPointerDown={edit ? (e) => startDrag(e, k, cfg, j) : undefined}
              onDoubleClick={edit ? (e) => { e.stopPropagation(); rename(k, cfg); } : undefined}
            >
              <div className="tag">{cfg?.label ?? meta?.label ?? k}</div>
              <div className={`val${failed ? ' text' : ''}`}>{text}</div>
              <div className="unit">{meta?.unit ?? ''}</div>
              {edit && (
                <div
                  className="mn-node-tag-scale"
                  onPointerDown={(e) => startScale(e, k, cfg)}
                />
              )}
            </div>
          </foreignObject>
        );
      })}
    </g>
  );
}

function StreamEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  pathOptions,
  data,
}: EdgeProps) {
  const { edit, onEdgeOffset } = useContext(SchemeEditorContext);
  const { getZoom } = useReactFlow();
  const opts = (pathOptions as { offsetX?: number; offsetY?: number } | undefined) ?? {};
  const offsetX = opts.offsetX ?? 0;
  const offsetY = opts.offsetY ?? 0;

  const { path, anchor, horizontal } = orthogonalPath(
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, offsetX, offsetY,
  );
  const streamData = (data ?? {}) as StreamEdgeData;

  const startDrag = (e: ReactPointerEvent) => {
    if (!edit) return;
    e.preventDefault();
    e.stopPropagation();
    const zoom = getZoom();
    const baseX = offsetX;
    const baseY = offsetY;
    const sx = e.clientX;
    const sy = e.clientY;
    const onMove = (ev: PointerEvent) => {
      onEdgeOffset(id, baseX + (ev.clientX - sx) / zoom, baseY + (ev.clientY - sy) / zoom);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  return (
    <g>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} interactionWidth={edit ? 20 : 2} />
      {edit && (
        <path
          d={path}
          fill="none"
          stroke="transparent"
          strokeWidth={22}
          style={{ cursor: 'grab' }}
          onPointerDown={startDrag}
        />
      )}
      <StreamTags id={id} data={streamData} anchor={anchor} horizontal={horizontal} />
    </g>
  );
}

export default memo(StreamEdge);
