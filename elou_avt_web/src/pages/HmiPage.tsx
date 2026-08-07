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
import type { Connection, Edge, NodeMouseHandler } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { api, connectWs } from '../api';
import type { ApiState, HistoryResponse, Scheme, SchemeNodeData, SchemeEdgeData, NodeTelemetry } from '../types';
import { useAuth } from '../auth';
import { PALETTE, createNode, nodeSize } from '../schemeConfig';
import { mnemoLayout } from '../layout';
import EquipmentNodeComponent from '../nodes/EquipmentNode';
import type { EquipmentNode, EquipmentNodeData } from '../nodes/EquipmentNode';
import Inspector from '../components/Inspector';
import TrendChart, { SERIES_META } from '../components/TrendChart';

const nodeTypes = { equipment: EquipmentNodeComponent };


const SCENARIOS = [
  { id: 'NORMAL_OPERATION', label: 'Нормальная работа' },
  { id: 'PUMP_FAILURE_001', label: 'Отказ насоса P-101' },
  { id: 'TEMPERATURE_DEVIATION_001', label: 'Отклонение температуры' },
  { id: 'PRESSURE_DEVIATION_001', label: 'Отклонение давления' },
  { id: 'COMBINED_EMERGENCY_001', label: 'Комбинированная авария' },
  { id: 'VALVE_FAILURE_001', label: 'Отказ клапана' },
  { id: 'FEED_LOSS_001', label: 'Потеря питания' },
  { id: 'STARTUP', label: 'Пуск установки' },
  { id: 'SHUTDOWN', label: 'Останов установки' },
];

const EDGE_KIND: Record<string, string> = {
  hot: '#fb923c',
  cooling: '#38bdf8',
  process: '#64748b',
};

function edgeMarker(kind: string) {
  const stroke = EDGE_KIND[kind] ?? '#64748b';
  return { type: MarkerType.ArrowClosed, width: 13, height: 13, color: stroke };
}

const DISP_KEY = 'hmi-disp-v1';

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
  const layout = mnemoLayout(scheme.nodes, scheme.edges, nodeSize);
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
        size: p?.size,
        mnemo: p?.mnemo,
      },
    };
  });
}

function toRfEdges(scheme: Scheme): Edge[] {
  return scheme.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.source_port,
    targetHandle: e.target_port,
    type: 'smoothstep',
    animated: false,
    markerEnd: edgeMarker(e.kind),
    style: { stroke: EDGE_KIND[e.kind] ?? '#64748b', strokeWidth: 1.5 },
  }));
}

function HmiInner() {
  const { user, hasPermission } = useAuth();
  const canEditScheme = hasPermission('manage_scheme');
  const [edit, setEdit] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<EquipmentNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [live, setLive] = useState<ApiState | null>(null);
  const [connected, setConnected] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [trendParam, setTrendParam] = useState('column_pressure_bar');
  const [schemes, setSchemes] = useState<string[]>([]);
  const [currentScheme, setCurrentScheme] = useState('default');
  const [scenario, setScenario] = useState('PUMP_FAILURE_001');
  const [msg, setMsg] = useState('');
  const [dispMap, setDispMap] = useState<Record<string, string[]>>(loadDisp);
  const { screenToFlowPosition, fitView } = useReactFlow();
  const msgTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const withDisp = useCallback(
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

  const notify = useCallback((text: string) => {
    setMsg(text);
    if (msgTimer.current) clearTimeout(msgTimer.current);
    msgTimer.current = setTimeout(() => setMsg(''), 3000);
  }, []);

  const applyTelemetry = useCallback((s: ApiState) => {
    setLive(s);
    setConnected(true);
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, telemetry: s.equipment?.[n.id] ?? null },
      })),
    );
    setEdges((eds) =>
      eds.map((e) => {
        const t = s.equipment?.[e.source];
        const flowing = !!t && (Number(t.params.flow_kg_s) ?? 0) > 0;
        return { ...e, animated: flowing };
      }),
    );
  }, [setNodes, setEdges]);

  // Initial load
  useEffect(() => {
    api.getScheme().then((scheme) => {
      setNodes(withDisp(toRfNodes(scheme)));
      setEdges(toRfEdges(scheme));
      setTimeout(() => fitView({ padding: 0.15, duration: 350 }), 80);
    }).catch(() => notify('Не удалось загрузить схему с бэкенда'));
    api.getHistory().then(setHistory).catch(() => undefined);
    api.listSchemes().then((r) => {
      setSchemes(r.schemes);
      setCurrentScheme(r.current);
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // WebSocket live telemetry
  useEffect(() => {
    const close = connectWs(applyTelemetry);
    return close;
  }, [applyTelemetry]);

  // History refresh
  useEffect(() => {
    const id = setInterval(() => {
      api.getHistory().then(setHistory).catch(() => undefined);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  const refresh = useCallback(async () => {
    try {
      applyTelemetry(await api.getState());
    } catch {
      setConnected(false);
    }
  }, [applyTelemetry]);

  const onDragStart = (e: React.DragEvent, type: string) => {
    e.dataTransfer.setData('application/elou-type', type);
    e.dataTransfer.effectAllowed = 'move';
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const type = e.dataTransfer.getData('application/elou-type');
      if (!type) return;
      const pos = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const node = createNode(type, pos.x, pos.y);
      setNodes((nds) => [
        ...nds,
        {
          id: node.id,
          type: 'equipment',
          position: { x: node.x, y: node.y },
          data: { nodeType: node.type, name: node.name, telemetry: null, schemeParams: node.params, disp: [] },
        },
      ]);
      setSelectedId(node.id);
      notify(`Добавлен объект «${node.name}»`);
    },
    [screenToFlowPosition, setNodes, notify],
  );

  const onConnect = useCallback(
    (c: Connection) => {
      const id = `${c.source}-${c.target}-${Date.now()}`;
      setEdges((eds) => [
        ...eds,
        {
          id,
          source: c.source!,
          target: c.target!,
          sourceHandle: c.sourceHandle ?? 'out',
          targetHandle: c.targetHandle ?? 'in',
          type: 'smoothstep',
          animated: false,
          markerEnd: edgeMarker('process'),
          style: { stroke: EDGE_KIND.process, strokeWidth: 1.5 },
        },
      ]);
    },
    [setEdges],
  );

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => setSelectedId(node.id), []);
  const onPaneClick = useCallback(() => setSelectedId(null), []);

  const onRename = useCallback(
    (nodeId: string, name: string) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, name } } : n)),
      );
    },
    [setNodes],
  );

  const onDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setSelectedId((cur) => (cur === nodeId ? null : cur));
    },
    [setNodes, setEdges],
  );

  const saveScheme = useCallback(async () => {
    const sn: SchemeNodeData[] = nodes.map((n) => ({
      id: n.id,
      type: (n.data as unknown as EquipmentNodeData).nodeType,
      name: (n.data as unknown as EquipmentNodeData).name,
      x: Math.round(n.position.x),
      y: Math.round(n.position.y),
      params: (n.data as unknown as EquipmentNodeData).schemeParams ?? {},
    }));
    const se: SchemeEdgeData[] = edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      source_port: e.sourceHandle ?? 'out',
      target_port: e.targetHandle ?? 'in',
      kind: 'process',
    }));
    try {
      const state = await api.saveScheme(sn, se);
      applyTelemetry(state);
      notify(`Схема сохранена (${sn.length} объектов, ${se.length} связей)`);
    } catch (err) {
      notify(`Ошибка сохранения: ${String(err)}`);
    }
  }, [nodes, edges, applyTelemetry, notify]);

  const loadDefault = useCallback(async () => {
    const scheme = await api.getScheme();
    setNodes(withDisp(toRfNodes(scheme)));
    setEdges(toRfEdges(scheme));
    setSelectedId(null);
    setTimeout(() => fitView({ padding: 0.15, duration: 350 }), 80);
    notify('Схема загружена с бэкенда');
  }, [withDisp, setNodes, setEdges, notify, fitView]);

  const runScenario = useCallback(async () => {
    const label = SCENARIOS.find((s) => s.id === scenario)?.label ?? scenario;
    try {
      const session = await api.startTrainingSession(scenario, user?.username ?? 'demo');
      const state = await api.startScenario(scenario);
      applyTelemetry(state);
      notify(`«${label}» запущен · сессия ${session.session_id}`);
    } catch (e) {
      notify(`Не удалось запустить сценарий: ${(e as Error).message}`);
    }
  }, [scenario, user, applyTelemetry, notify]);

  const finishScenario = useCallback(async () => {
    try {
      const s = await api.finishTrainingSession();
      notify(`Тренировка завершена · счёт ${s.performance_score ?? '—'}`);
    } catch (e) {
      notify(`Нет активной сессии: ${(e as Error).message}`);
    }
  }, [notify]);

  const reLayout = useCallback(() => {
    const layout = mnemoLayout(
      nodes.map((n) => ({
        id: n.id,
        type: (n.data as unknown as EquipmentNodeData).nodeType,
        name: (n.data as unknown as EquipmentNodeData).name,
        x: n.position.x,
        y: n.position.y,
        params: {},
      })),
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_port: e.sourceHandle ?? 'out',
        target_port: e.targetHandle ?? 'in',
        kind: 'process',
      })),
      nodeSize,
    );
    setNodes((nds) =>
      nds.map((n) => {
        const p = layout.get(n.id);
        return p
          ? { ...n, position: p.pos, data: { ...n.data, size: p.size, mnemo: p.mnemo } }
          : n;
      }),
    );
    setTimeout(() => fitView({ padding: 0.15, duration: 350 }), 80);
    notify('Раскладка по мнемосхеме применена');
  }, [nodes, edges, setNodes, notify, fitView]);

  const onSelectScheme = useCallback(
    async (name: string) => {
      if (name === currentScheme) return;
      try {
        const state = await api.loadScheme(name);
        applyTelemetry(state);
        const scheme = await api.getScheme();
        setNodes(withDisp(toRfNodes(scheme)));
        setEdges(toRfEdges(scheme));
        setSelectedId(null);
        setCurrentScheme(name);
        notify(`Схема «${name}» загружена`);
      } catch {
        notify('Ошибка загрузки схемы');
      }
    },
    [currentScheme, applyTelemetry, withDisp, setNodes, setEdges, notify],
  );

  const onCreateScheme = useCallback(async () => {
    const name = window.prompt('Имя новой схемы (латиница, цифры, _ или -):');
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      await api.createScheme(trimmed);
      const r = await api.listSchemes();
      setSchemes(r.schemes);
      setCurrentScheme(r.current);
      const scheme = await api.getScheme();
      setNodes(withDisp(toRfNodes(scheme)));
      setEdges(toRfEdges(scheme));
      setSelectedId(null);
      notify(`Схема «${trimmed}» создана`);
    } catch (err) {
      notify(`Ошибка создания схемы: ${String(err)}`);
    }
  }, [withDisp, setNodes, setEdges, notify]);

  const onAction = useCallback(
    async (equipmentId: string, actionType: string, value?: number | null) => {
      try {
        applyTelemetry(await api.action(equipmentId, actionType, value));
      } catch {
        notify('Ошибка действия');
      }
    },
    [applyTelemetry, notify],
  );

  const onFailure = useCallback(
    async (equipmentId: string) => {
      try {
        applyTelemetry(await api.injectFailure(equipmentId));
        notify(`Отказ внедрён: ${equipmentId}`);
      } catch {
        notify('Ошибка внедрения отказа');
      }
    },
    [applyTelemetry, notify],
  );

  const onUpdateParams = useCallback(
    async (equipmentId: string, params: Record<string, number>) => {
      try {
        applyTelemetry(await api.updateEquipmentParams(equipmentId, params));
        notify('Физические свойства обновлены');
      } catch {
        notify('Ошибка обновления свойств');
      }
    },
    [applyTelemetry, notify],
  );

  const selectedTelemetry = selectedId ? live?.equipment?.[selectedId] ?? null : null;
  const selectedNode = selectedId ? (nodes.find((n) => n.id === selectedId) ?? null) : null;

  return (
    <div className="hmi-page">
      <div className="hmi-toolbar">
        <select
          className="scenario-select"
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          title="Сценарий"
        >
          {SCENARIOS.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
        <button className="btn btn-start" onClick={runScenario}>▶ Запустить</button>
        <button className="btn btn-stop" onClick={finishScenario}>⏹ Завершить</button>
        <button className="btn btn-ghost" onClick={() => api.resetScenario().then(applyTelemetry)}>⏮ Сброс</button>
        <button className="btn btn-ghost" onClick={() => api.step().then(applyTelemetry)}>⏭ Шаг</button>

        {canEditScheme && (
          <>
            <span className="hmi-sep" />
            <button
              className={`btn ${edit ? 'btn-active' : 'btn-ghost'}`}
              onClick={() => {
                setEdit((v) => !v);
                setSelectedId(null);
              }}
              title={edit ? 'Выйти из режима редактирования' : 'Редактировать схему'}
            >
              {edit ? '✓ Готово' : '🖉 Редактировать схему'}
            </button>
          </>
        )}

        {canEditScheme && edit && (
          <>
            <button className="btn btn-ghost" onClick={saveScheme}>💾 Сохранить</button>
            <button className="btn btn-ghost" onClick={onCreateScheme}>＋ Новая схема</button>
            <button className="btn btn-ghost" onClick={loadDefault}>⟳ Загрузить</button>
            <button className="btn btn-ghost" onClick={reLayout}>🗜 Раскладка</button>
            <select
              className="scenario-select"
              value={currentScheme}
              onChange={(e) => onSelectScheme(e.target.value)}
              title="Схема"
            >
              {schemes.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </>
        )}

        <div className="hmi-chips">
          <span className={`chip ${connected ? 'chip-ok' : 'chip-bad'}`}>
            <span className="dot" /> {connected ? 'LIVE · СВЯЗЬ ЕСТЬ' : 'ОТКЛЮЧЕНО'}
          </span>
          <span className="chip chip-info">t = {(live?.simulation_time ?? 0).toFixed(0)} с</span>
          <span className={`chip ${(live?.alarms?.length ?? 0) > 0 ? 'chip-alarm' : 'chip-ok'}`}>
            ⚠ {(live?.alarms?.length ?? 0)} аварий
          </span>
        </div>
      </div>

      <div className="body">
        {canEditScheme && edit && (
          <aside className="palette">
            <div className="panel-title">ПАЛИТРА ОБЪЕКТОВ</div>
            <div className="palette-group">Границы</div>
            {PALETTE.filter((p) => p.category === 'boundary').map((p) => (
              <div
                key={p.type}
                className="palette-item"
                draggable
                onDragStart={(e) => onDragStart(e, p.type)}
              >
                <span className="palette-dot" style={{ background: p.color }} />
                {p.label}
              </div>
            ))}
            <div className="palette-group">Оборудование</div>
            {PALETTE.filter((p) => p.category === 'equipment').map((p) => (
              <div
                key={p.type}
                className="palette-item"
                draggable
                onDragStart={(e) => onDragStart(e, p.type)}
              >
                <span className="palette-dot" style={{ background: p.color }} />
                {p.label}
              </div>
            ))}
            <div className="hint">Перетащите объект на схему. Соединяйте объекты, потянув от порта к порту.</div>
          </aside>
        )}

        <div className="canvas" onDrop={canEditScheme && edit ? onDrop : undefined} onDragOver={(e) => canEditScheme && edit && e.preventDefault()}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={canEditScheme && edit ? onConnect : undefined}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable={canEditScheme && edit}
            nodesConnectable={canEditScheme && edit}
            deleteKeyCode={canEditScheme && edit ? ['Backspace', 'Delete'] : null}
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
            {!edit && (
              <Panel position="top-center">
                <div className="hmi-banner">ЭЛОУ-АВТ · МНЕМОСХЕМА УСТАНОВКИ</div>
              </Panel>
            )}
            <Panel position="bottom-center">
              <div className="flow-legend">
                <span><span className="legend-line" style={{ background: '#64748b' }} /> технологический поток</span>
                <span><span className="legend-line" style={{ background: '#fb923c' }} /> горячий теплоноситель</span>
                <span><span className="legend-line" style={{ background: '#38bdf8' }} /> охлаждение/вода</span>
                <span>🖱 колесо — масштаб · зажать — перемещение · клик по объекту — панель</span>
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
            onFailure={onFailure}
            onRename={onRename}
            onDelete={onDelete}
            onUpdateParams={onUpdateParams}
            canEditScheme={canEditScheme && edit}
          />
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

      {msg && <div className="toast">{msg}</div>}
    </div>
  );
}

export default function HmiPage() {
  return (
    <ReactFlowProvider>
      <HmiInner />
    </ReactFlowProvider>
  );
}
