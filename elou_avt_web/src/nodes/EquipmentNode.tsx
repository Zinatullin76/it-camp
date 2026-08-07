import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { Node, NodeProps } from '@xyflow/react';
import type { NodeTelemetry, AlarmData } from '../types';
import type { MnemoItem } from '../mnemo/mnemoTypes';
import type { MnemoLive } from '../mnemo/sources';
import { itemBBox, renderItem } from '../mnemo/symbols';
import { TYPE_COLORS, nodeSize, PARAM_LABELS, fmtValue } from '../schemeConfig';

export type EquipmentNodeData = {
  nodeType: string;
  name: string;
  telemetry: NodeTelemetry | null;
  schemeParams?: Record<string, unknown>;
  size?: { w: number; h: number };
  mnemo?: Partial<MnemoItem>;
  disp?: string[];
  alarms?: AlarmData[];
};

export type EquipmentNode = Node<EquipmentNodeData, 'equipment'>;

const HANDLE_STYLE = { width: 7, height: 7, background: 'var(--bg)', border: '1.5px solid var(--accent)' };

/**
 * ReactFlow node type -> mnemo symbol drawn exactly like avt4.html.
 */
const SYMBOL: Record<string, Partial<MnemoItem>> = {
  source: { t: 'box', w: 132, h: 38 },
  sink: { t: 'box', w: 132, h: 38 },
  pump: { t: 'pump' },
  valve: { t: 'valve', vt: 'cv' },
  elou: { t: 'ed', w: 120, h: 44, lv: 'lv' },
  heat_exchanger: { t: 'hx', w: 132, h: 40 },
  heater: { t: 'fur', w: 118, h: 66 },
  column: { t: 'col', w: 46, h: 118, tr: 10, sump: 24, lv: 'lv' },
  separator: { t: 'vves', w: 40, h: 88, lv: 'lv', lvw: 'lvw' },
};

const NOMINAL_LEVEL_H = 4;

/** Build a minimal MnemoLive from one node's telemetry. */
function buildLive(t: NodeTelemetry | null, color: string): MnemoLive {
  const pct = (): number => {
    if (!t) return 0;
    const lv = t.params?.level_m;
    if (typeof lv !== 'number' || !Number.isFinite(lv)) return 0;
    return Math.min(100, Math.max(0, (lv / NOMINAL_LEVEL_H) * 100));
  };
  let fuel = 0;
  if (t) {
    const f = t.params?.fuel_flow;
    if (typeof f === 'number' && Number.isFinite(f)) fuel = f;
  }
  return {
    ctrl: () => undefined,
    sval: () => null,
    lvl: () => pct(),
    lw: () => pct(),
    flowColor: () => color,
    run: () => 'unknown',
    equip: () => undefined,
    param: () => null,
    fireOn: fuel > 0.15,
    edVolt: true,
  };
}

const handles = (type: string) => {
  const left = (top: number) => ({ ...HANDLE_STYLE, top: `${top}%` });
  const right = (top: number) => ({ ...HANDLE_STYLE, top: `${top}%` });

  switch (type) {
    case 'source':
      return <Handle type="source" position={Position.Right} id="out" style={right(50)} />;
    case 'sink':
      return <Handle type="target" position={Position.Left} id="in" style={left(50)} />;
    case 'heat_exchanger':
      return (
        <>
          <Handle type="target" position={Position.Left} id="cold_in" style={left(30)} />
          <Handle type="target" position={Position.Left} id="hot_in" style={left(70)} />
          <Handle type="source" position={Position.Right} id="cold_out" style={right(30)} />
          <Handle type="source" position={Position.Right} id="hot_out" style={right(70)} />
        </>
      );
    case 'column':
      return (
        <>
          <Handle type="target" position={Position.Left} id="in" style={left(50)} />
          <Handle type="source" position={Position.Right} id="distillate" style={right(30)} />
          <Handle type="source" position={Position.Right} id="bottoms" style={right(70)} />
        </>
      );
    default:
      return (
        <>
          <Handle type="target" position={Position.Left} id="in" style={left(50)} />
          <Handle type="source" position={Position.Right} id="out" style={right(50)} />
        </>
      );
  }
};

function MnemoEquipmentNode({ data, selected }: NodeProps<EquipmentNode>) {
  const { nodeType, name, telemetry, size, mnemo, disp, alarms } = data;
  const box = size ?? nodeSize(nodeType);
  const color = telemetry?.failed ? '#f87171' : TYPE_COLORS[nodeType] ?? '#38bdf8';
  const item: MnemoItem = {
    t: 'box',
    x: 0,
    y: 0,
    n: name,
    ...(mnemo ?? SYMBOL[nodeType] ?? {}),
  };
  const bb = itemBBox(item);
  const live = buildLive(telemetry, color);
  const svgW = box.w - 6;
  const svgH = Math.max(box.h - 6, (bb[3] * svgW) / bb[2]);
  const dispParams = (disp ?? []).filter((k) => telemetry?.params?.[k] !== null && telemetry?.params?.[k] !== undefined);

  const failed = !!telemetry?.failed;
  const nodeAlarms = alarms ?? [];
  const critical = !failed && nodeAlarms.some((a) => a.severity === 'CRITICAL');
  const warning = !failed && !critical && nodeAlarms.some((a) => a.severity !== 'CRITICAL');
  const state = failed ? 'fault' : critical ? 'alarm' : warning ? 'warning' : 'normal';

  return (
    <div
      className={`mn-node${selected ? ' sel' : ''}`}
      style={{ width: box.w, height: svgH + 6 }}
    >
      <svg
        viewBox={`${bb[0]} ${bb[1]} ${bb[2]} ${bb[3]}`}
        width={svgW}
        height={svgH}
      >
        {renderItem(item, live)}
      </svg>
      {dispParams.length > 0 && (
        <div className="mn-node-tags">
          {dispParams.map((k) => {
            const meta = PARAM_LABELS[k];
            const v = telemetry?.params?.[k];
            const num = typeof v === 'number' && Number.isFinite(v);
            return (
              <div key={k} className={`mn-node-tag state-${state}`}>
                <div className="tag">{meta?.label ?? k}</div>
                <div className={`val${failed ? ' text' : ''}`}>{failed ? 'ОТКАЗ' : num ? fmtValue(v, '') : '—'}</div>
                <div className="unit">{meta?.unit ?? ''}</div>
              </div>
            );
          })}
        </div>
      )}
      {telemetry?.failed ? (
        <span className="mn-node-alarm">АВАРИЯ</span>
      ) : null}
      {handles(nodeType)}
    </div>
  );
}

export default memo(MnemoEquipmentNode);
