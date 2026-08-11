import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  MarkerType,
} from '@xyflow/react';
import type { Edge, NodeMouseHandler } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { api } from '../api';
import type { ApiState, HistoryResponse, Scheme, ScadaLogEventType } from '../types';
import { nodeSizeFor, mnemoForNode, phaseMeta, normalizePhase, PHASE_TYPES } from '../schemeConfig';
import { mnemoLayout } from '../layout';
import EquipmentNodeComponent from '../nodes/EquipmentNode';
import type { EquipmentNode, EquipmentNodeData } from '../nodes/EquipmentNode';
import Inspector from '../components/Inspector';
import StreamEdge from '../components/StreamEdge';
import TrendChart, { SERIES_META } from '../components/TrendChart';
import { fmtSimTime } from '../lms/ui';

const nodeTypes = { equipment: EquipmentNodeComponent };
const edgeTypes = { stream: StreamEdge };

const EDGE_STROKE = 2;

function edgeMarker(color: string) {
  return { type: MarkerType.ArrowClosed, width: 13, height: 13, color };
}

interface EdgeCfg {
  phase?: string;
  offset?: number;
}

const DISP_KEY = 'scada-disp-v1';

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

function toRfNodes(scheme: Scheme): EquipmentNode[] {
  const layout = mnemoLayout(scheme.nodes, scheme.edges, (nd) => nodeSizeFor(nd));
  return scheme.nodes.map((n) => {
    const p = layout.get(n.id);
    return {
      id: n.id,
      type: 'equipment',
      position: { x: n.x, y: n.y },
      data: {
        nodeType: n.type,
        name: n.name,
        telemetry: null,
        schemeParams: n.params,
        size: p?.size ?? nodeSizeFor(n),
        mnemo: p?.mnemo ?? mnemoForNode(n.params),
      },
    };
  });
}

function toRfEdges(scheme: Scheme, edgeCfg: Record<string, EdgeCfg>): Edge[] {
  return scheme.edges.map((e) => {
    const cfg = edgeCfg[e.id];
    const phase = phaseMeta(normalizePhase(cfg?.phase ?? e.kind));
    const offset = cfg?.offset ?? 0;
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_port,
      targetHandle: e.target_port,
      type: 'stream',
      animated: false,
      pathOptions: { offset },
      markerEnd: edgeMarker(phase.color),
      style: { stroke: phase.color, strokeWidth: EDGE_STROKE },
      data: { phase: phase.id },
    };
  });
}

interface Props {
  live: ApiState | null;
  user?: string;
  onReady?: () => void;
}

function ScadaInner({ live, user, onReady }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<EquipmentNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [trendParam, setTrendParam] = useState('column_pressure_bar');
  const [dispMap, setDispMap] = useState<Record<string, string[]>>(loadDisp);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const { fitView } = useReactFlow();
  const msgTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inspectorRef = useRef<{ objectId: string; objectName: string; openedAt: number } | null>(null);
  const pageEnterRef = useRef<number>(Date.now());
  const scadaFlushedRef = useRef(false);
  const liveRef = useRef(live);
  liveRef.current = live;

  const notify = useCallback((text: string) => {
    setMsg(text);
    if (msgTimer.current) clearTimeout(msgTimer.current);
    msgTimer.current = setTimeout(() => setMsg(''), 3000);
  }, []);

  const logScada = useCallback(
    (eventType: ScadaLogEventType, objectId: string, objectName: string, durationS?: number) => {
      api.logScadaEvent({ event_type: eventType, object_id: objectId, object_name: objectName, duration_s: durationS })
        .catch(() => undefined);
    },
    [],
  );

  const closeInspector = useCallback(() => {
    const cur = inspectorRef.current;
    if (!cur) return;
    inspectorRef.current = null;
    const duration = (Date.now() - cur.openedAt) / 1000;
    logScada('inspector_close', cur.objectId, cur.objectName, duration);
  }, [logScada]);

  const openInspector = useCallback(
    (node: { id: string; name: string }) => {
      if (inspectorRef.current?.objectId === node.id) return;
      closeInspector();
      inspectorRef.current = { objectId: node.id, objectName: node.name, openedAt: Date.now() };
      logScada('inspector_open', node.id, node.name);
    },
    [closeInspector, logScada],
  );

  // SCADA-журнал: вход/выход из практики, открытие/закрытие окна объекта
  useEffect(() => {
    logScada('page_enter', '', '');
    const flush = () => {
      if (scadaFlushedRef.current) return;
      scadaFlushedRef.current = true;
      closeInspector();
      logScada('page_exit', '', '', (Date.now() - pageEnterRef.current) / 1000);
    };
    window.addEventListener('beforeunload', flush);
    return () => {
      window.removeEventListener('beforeunload', flush);
      flush();
    };
  }, [logScada, closeInspector]);

  // Смена выбранного объекта управляет окном инспектора
  useEffect(() => {
    if (!selectedId) {
      closeInspector();
      return;
    }
    const n = nodes.find((x) => x.id === selectedId);
    if (n) openInspector({ id: n.id, name: n.data.name });
  }, [selectedId, nodes, closeInspector, openInspector]);

  const withCfg = useCallback(
    (nds: EquipmentNode[]): EquipmentNode[] =>
      nds.map((n) => ({ ...n, data: { ...n.data, disp: dispMap[n.id] ?? [] } })),
    [dispMap],
  );

  const onUpdateDisp = useCallback(
    (nodeId: string, keys: string[]) => {
      setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, disp: keys } } : n)));
      setDispMap((m) => {
        const nm = { ...m, [nodeId]: keys };
        saveDisp(nm);
        return nm;
      });
    },
    [setNodes],
  );

  const applyTelemetry = useCallback(
    (s: ApiState) => {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            telemetry: s.equipment?.[n.id] ?? null,
            alarms: (s.alarms ?? []).filter((a) => a.node_id === n.id || a.parameter.startsWith(`${n.id}_`)),
          },
        })),
      );
      setEdges((eds) =>
        eds.map((e) => {
          const t = s.equipment?.[e.source];
          const flowing = !!t && (Number(t.params.flow_kg_s) ?? 0) > 0;
          return { ...e, animated: flowing };
        }),
      );
    },
    [setNodes, setEdges],
  );

  // Initial load
  useEffect(() => {
    api.getScheme()
      .then((scheme) => {
        setNodes(withCfg(toRfNodes(scheme)));
        setEdges(toRfEdges(scheme, {}));
        if (liveRef.current) applyTelemetry(liveRef.current);
        setTimeout(() => fitView({ padding: 0.15, duration: 350 }), 80);
        requestAnimationFrame(() => requestAnimationFrame(() => onReady?.()));
      })
      .catch(() => notify('Не удалось загрузить SCADA-схему'));
    api.getHistory().then(setHistory).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Live telemetry из родителя (WebSocket)
  useEffect(() => {
    if (live) applyTelemetry(live);
  }, [live, applyTelemetry]);

  // History refresh
  useEffect(() => {
    const id = setInterval(() => {
      api.getHistory().then(setHistory).catch(() => undefined);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const name = (node.data as EquipmentNodeData).name ?? node.id;
      logScada('click', node.id, name);
      setSelectedId(node.id);
    },
    [logScada],
  );

  const onPaneClick = useCallback(() => {
    setSelectedId(null);
  }, []);

  const onAction = useCallback(
    async (equipmentId: string, actionType: string, value?: number | null) => {
      try {
        setErr('');
        applyTelemetry(await api.action(equipmentId, actionType, value));
        const labels: Record<string, string> = {
          TURN_ON: 'Оборудование запущено',
          TURN_OFF: 'Оборудование остановлено',
          EMERGENCY_STOP: 'Выполнен аварийный останов',
          SET_VALUE: 'Значение применено',
          SET_SPEED: 'Скорость изменена',
        };
        notify(labels[actionType] ?? 'Команда выполнена');
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    },
    [applyTelemetry, notify],
  );

  const onUpdateSchemeParam = useCallback(
    (nodeId: string, key: string, value: unknown) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? {
                ...n,
                data: {
                  ...n.data,
                  schemeParams: { ...(n.data as EquipmentNodeData).schemeParams, [key]: value },
                },
              }
            : n,
        ),
      );
    },
    [setNodes],
  );

  const selectedNode = selectedId ? (nodes.find((n) => n.id === selectedId) ?? null) : null;
  const selectedTelemetry = selectedNode?.data.telemetry ?? null;

  return (
    <div className="scada-scheme">
      <div className="body">
        <div className="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            edgesFocusable={false}
            edgesReconnectable={false}
            deleteKeyCode={null}
            minZoom={0.15}
            maxZoom={3}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} color="var(--mn-line)" />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => {
                const t = (n.data as EquipmentNodeData).telemetry;
                return t?.failed ? '#f87171' : t?.running ? '#35d399' : '#334155';
              }}
              style={{ background: 'var(--panel)' }}
            />
            <Panel position="top-center">
              <div className="hmi-banner">
                ОРБИТА · МНЕМОСХЕМА УСТАНОВКИ{user ? ` · ${user}` : ''}
              </div>
              <div className="hmi-chips" style={{ marginTop: 6, justifyContent: 'center' }}>
                <span className="chip chip-info">t = {(live?.simulation_time ?? 0).toFixed(0)} с</span>
                <label className="chip chip-info speed-chip">
                  ⏩ <select
                    className="speed-select"
                    value={live?.speed ?? 1}
                    onChange={(e) => { void api.setSimulationSpeed(Number(e.target.value)); }}
                    title="Скорость симуляции"
                  >
                    <option value={1}>1×</option>
                    <option value={2}>2×</option>
                    <option value={5}>5×</option>
                    <option value={10}>10×</option>
                    <option value={30}>30×</option>
                  </select>
                </label>
              </div>
            </Panel>
            <Panel position="bottom-center">
              <div className="flow-legend">
                {PHASE_TYPES.map((p) => (
                  <span key={p.id}><span className="legend-line" style={{ background: p.color }} />{p.label}</span>
                ))}
              </div>
            </Panel>
          </ReactFlow>
        </div>

        <aside className="inspector">
          <div className="panel-title">ИНСПЕКТОР</div>
          <Inspector
            nodeId={selectedId ?? ''}
            nodeName={selectedNode?.data.name ?? ''}
            nodeType={selectedNode?.data.nodeType ?? ''}
            schemeParams={selectedNode?.data.schemeParams ?? {}}
            telemetry={selectedTelemetry}
            disp={selectedNode?.data.disp ?? []}
            onUpdateDisp={onUpdateDisp}
            onAction={onAction}
            onFailure={async () => {}}
            onRename={() => {}}
            onDelete={() => {}}
            onUpdateParams={async () => {}}
            onUpdateSchemeParam={onUpdateSchemeParam}
            canEditScheme={false}
            canManageTwin={false}
          />
          {err && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 8 }}>{err}</div>}

          <div className="panel-title trend-title">ТРЕНД ПАРАМЕТРА</div>
          <select
            className="scenario-select full"
            value={trendParam}
            onChange={(e) => setTrendParam(e.target.value)}
          >
            {Object.entries(SERIES_META).map(([k, m]) => (
              <option key={k} value={k}>{m.label} ({m.unit})</option>
            ))}
          </select>
          <TrendChart history={history} param={trendParam} />
        </aside>
      </div>

      {(live?.alarms?.length ?? 0) > 0 && (
        <div className="mnemo-bottom scada-alarms">
          <div className="mnemo-alarms">
            <div className="panel-title">АВАРИИ · {live?.alarms?.length ?? 0}</div>
            <div className="alarm-table-wrap">
              <table className="alarm-table">
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>Параметр</th>
                    <th>Значение</th>
                    <th>Уставка</th>
                    <th>Описание</th>
                  </tr>
                </thead>
                <tbody>
                  {(live?.alarms ?? []).map((a) => (
                    <tr key={a.id} className={`alarm-row sev-${String(a.severity).toLowerCase()}`}>
                      <td>{fmtSimTime(a.timestamp)}</td>
                      <td>{a.parameter}</td>
                      <td>{a.actual_value.toFixed(2)}</td>
                      <td>{a.threshold.toFixed(2)}</td>
                      <td className="alarm-desc">{a.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {msg && <div className="toast">{msg}</div>}
    </div>
  );
}

export default function ScadaScheme(props: Props) {
  return (
    <ReactFlowProvider>
      <ScadaInner {...props} />
    </ReactFlowProvider>
  );
}
