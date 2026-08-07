import { memo, useContext } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { BaseEdge, useReactFlow } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import { SchemeEditorContext } from '../nodes/EquipmentNode';

/**
 * Поток (ребро мнемосхемы): ортогональная линия с углами 90°.
 * В режиме редактирования линию можно перетаскивать мышью — сдвиг
 * перпендикулярно направлению потока (разводка параллельных линий).
 * В режиме SCADA линия некликабельна и не имеет подписей.
 */

type Point = { x: number; y: number };

const DIR: Record<string, Point> = {
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  top: { x: 0, y: -1 },
  bottom: { x: 0, y: 1 },
};

const LEAD = 20;

/**
 * Собственная ортогональная трасса с углами 90°.
 * `offset` сдвигает СРЕДНИЙ сегмент линии перпендикулярно направлению
 * потока — в отличие от `getSmoothStepPath`, где `offset` при
 * противоположных позициях портов взаимно уничтожается и линия не двигается.
 */
function orthogonalPath(
  sx: number,
  sy: number,
  sourcePosition: string,
  tx: number,
  ty: number,
  targetPosition: string,
  offset: number,
): string {
  const s: Point = { x: sx, y: sy };
  const t: Point = { x: tx, y: ty };
  const ds = DIR[sourcePosition] ?? DIR.right;
  const dt = DIR[targetPosition] ?? DIR.left;
  const so: Point = { x: s.x + ds.x * LEAD, y: s.y + ds.y * LEAD };
  const to: Point = { x: t.x + dt.x * LEAD, y: t.y + dt.y * LEAD };

  const horizontalFlow = Math.abs(so.x - to.x) >= Math.abs(so.y - to.y);
  const oppositeX = ds.x !== 0 && dt.x !== 0 && ds.x !== dt.x;
  const oppositeY = ds.y !== 0 && dt.y !== 0 && ds.y !== dt.y;

  let pts: Point[];
  if (oppositeX && oppositeY && horizontalFlow) {
    const midY = (s.y + t.y) / 2 + offset;
    pts = [so, { x: so.x, y: midY }, { x: to.x, y: midY }, to];
  } else if (oppositeX && oppositeY && !horizontalFlow) {
    const midX = (s.x + t.x) / 2 + offset;
    pts = [so, { x: midX, y: so.y }, { x: midX, y: to.y }, to];
  } else if (horizontalFlow) {
    const midY = (so.y + to.y) / 2 + offset;
    pts = [so, { x: so.x, y: midY }, { x: to.x, y: midY }, to];
  } else {
    const midX = (so.x + to.x) / 2 + offset;
    pts = [so, { x: midX, y: so.y }, { x: midX, y: to.y }, to];
  }

  let path = `M${s.x} ${s.y}`;
  for (const p of pts) path += `L${p.x} ${p.y}`;
  path += `L${t.x} ${t.y}`;
  return path;
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
}: EdgeProps) {
  const { edit, onEdgeOffset } = useContext(SchemeEditorContext);
  const { getZoom } = useReactFlow();
  const offset = (pathOptions as { offset?: number } | undefined)?.offset ?? 0;

  const path = orthogonalPath(sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, offset);

  const startDrag = (e: ReactPointerEvent) => {
    if (!edit) return;
    e.preventDefault();
    e.stopPropagation();
    const zoom = getZoom();
    const base = offset;
    const sx = e.clientX;
    const sy = e.clientY;
    const horizontal = Math.abs(targetX - sourceX) >= Math.abs(targetY - sourceY);
    const onMove = (ev: PointerEvent) => {
      const d = horizontal ? ev.clientY - sy : ev.clientX - sx;
      onEdgeOffset(id, base + d / zoom);
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
    </g>
  );
}

export default memo(StreamEdge);
