import { useEffect, useRef, useState } from 'react';
import type { NodeTelemetry, EquipmentSpec } from '../types';
import { TYPE_COLORS, fmtValue, PARAM_LABELS } from '../schemeConfig';
import { api } from '../api';

interface Props {
  nodeId: string;
  nodeName: string;
  nodeType: string;
  schemeParams: Record<string, unknown>;
  telemetry: NodeTelemetry | null;
  disp?: string[];
  onUpdateDisp?: (nodeId: string, keys: string[]) => void;
  onAction: (equipmentId: string, actionType: string, value?: number | null) => Promise<void>;
  onFailure: (equipmentId: string) => Promise<void>;
  onRename: (nodeId: string, name: string) => void;
  onDelete: (nodeId: string) => void;
  onUpdateParams: (equipmentId: string, params: Record<string, number>) => Promise<void>;
  onUpdateSchemeParam?: (nodeId: string, key: string, value: unknown) => void;
  canEditScheme?: boolean;
  canManageTwin?: boolean;
}

export default function Inspector({ nodeId, nodeName, nodeType, schemeParams, telemetry, disp = [], onUpdateDisp, onAction, onFailure, onRename, onDelete, onUpdateParams, onUpdateSchemeParam, canEditScheme = true, canManageTwin = true }: Props) {
  const [valvePos, setValvePos] = useState(60);
  const [fuel, setFuel] = useState(0.8);
  const [reflux, setReflux] = useState(2.0);
  const [feedFlow, setFeedFlow] = useState(100);
  const [feedTemp, setFeedTemp] = useState(25);
  const [pumpSpeed, setPumpSpeed] = useState(1450);
  const [name, setName] = useState('');
  const [spec, setSpec] = useState<EquipmentSpec | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const hydratedNode = useRef<string | null>(null);
  const nameHydrated = useRef<string | null>(null);

  useEffect(() => {
    setSpec(null);
    setDraft({});
    if (!nodeId) return;
    api.getEquipmentSpec(nodeId)
      .then((s) => {
        setSpec(s);
        const d: Record<string, number> = {};
        s.params.forEach((p) => {
          if (p.value !== null) d[p.key] = p.value;
        });
        setDraft(d);
      })
      .catch(() => undefined);
  }, [nodeId]);

  useEffect(() => {
    if (!telemetry) return;
    if (hydratedNode.current === nodeId) return;
    hydratedNode.current = nodeId;
    const p = telemetry.params;
    if (typeof p.position === 'number') setValvePos(p.position);
    if (typeof p.fuel_flow === 'number') setFuel(p.fuel_flow);
    if (typeof p.flow_kg_s === 'number' && telemetry.type === 'source') setFeedFlow(p.flow_kg_s);
    if (typeof p.temperature_c === 'number' && telemetry.type === 'source') setFeedTemp(p.temperature_c);
    if (typeof p.speed_rpm === 'number' && telemetry.type === 'pump') setPumpSpeed(p.speed_rpm);
  }, [nodeId, telemetry]);

  useEffect(() => {
    if (nameHydrated.current === nodeId) return;
    nameHydrated.current = nodeId;
    setName(nodeName);
  }, [nodeId, nodeName]);

  const commitName = () => {
    const trimmed = name.trim();
    if (!trimmed || !nodeId) {
      setName(nodeName);
      return;
    }
    if (trimmed !== nodeName) onRename(nodeId, trimmed);
  };

  if (!nodeId) {
    return <div className="inspector-empty">Выберите объект на схеме, чтобы увидеть параметры и управление.</div>;
  }

  // Объект есть в схеме, но пока нет телеметрии с бэкенда (новая схема,
  // ещё не сохранена / не создана в движке). Показываем редактор по params схемы.
  if (!telemetry) {
    return (
      <div>
        <div className="inspector-header" style={{ borderLeft: `3px solid ${TYPE_COLORS[nodeType] ?? '#38bdf8'}` }}>
          {canEditScheme ? (
            <input
              className="rename-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={commitName}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
              }}
              spellCheck={false}
            />
          ) : (
            <div style={{ fontWeight: 700 }}>{nodeName || nodeId}</div>
          )}
          <div style={{ fontSize: 10, color: '#7f93a6' }}>{nodeId} • {nodeType}</div>
        </div>
        <div style={{ color: '#e8b93a', fontSize: 11, fontWeight: 700, margin: '4px 0 10px' }}>
          ● НА СХЕМЕ · ТЕЛЕМЕТРИИ НЕТ
        </div>
        <div className="param-list">
          {Object.entries(schemeParams)
            .filter(([k]) => k !== 'mnemo' && k !== 'preset')
            .map(([k, v]) => (
            <div className="param-row" key={k}>
              <span>{PARAM_LABELS[k]?.label ?? k}</span>
              <span>{typeof v === 'number' ? fmtValue(v, PARAM_LABELS[k]?.unit ?? '') : String(v)}</span>
            </div>
          ))}
        </div>
        <div className="inspector-hint">
          Объект ещё не создан в расчётном движке. Нажмите «Сохранить схему», чтобы запустить симуляцию и получить телеметрию.
        </div>
        {canEditScheme && (
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-danger" onClick={() => onDelete(nodeId)}>🗑 Удалить объект</button>
          </div>
        )}
      </div>
    );
  }

  const color = TYPE_COLORS[telemetry.type] ?? '#38bdf8';
  const statusText = telemetry.failed
    ? `АВАРИЯ: ${telemetry.failure_mode ?? '—'}`
    : telemetry.type === 'gate_valve'
      ? telemetry.params?.open
        ? 'ОТКРЫТА'
        : 'ЗАКРЫТА'
      : telemetry.running === null
        ? 'Граница'
        : telemetry.running
          ? 'РАБОТАЕТ'
          : 'ОСТАНОВЛЕН';

  const control = (() => {
    switch (telemetry.type) {
      case 'pump':
        return (
          <div className="ctrl-group">
            <button className="btn btn-start" onClick={() => onAction(nodeId, 'TURN_ON')}>▶ Запустить</button>
            <button className="btn btn-stop" onClick={() => onAction(nodeId, 'TURN_OFF')}>■ Остановить</button>
            <button className="btn btn-danger" onClick={() => onAction(nodeId, 'EMERGENCY_STOP')}>⛔ Эвакуационный стоп</button>
            {canManageTwin && (
              <button className="btn btn-warn" onClick={() => onFailure(nodeId)}>⚠ Смоделировать отказ</button>
            )}
            <label className="ctrl-label">
              Частота вращения: {pumpSpeed} об/мин
              <input
                type="range"
                min={0}
                max={2900}
                step={50}
                value={pumpSpeed}
                onChange={(e) => setPumpSpeed(Number(e.target.value))}
              />
            </label>
            <button className="btn btn-start" onClick={() => void onAction(nodeId, 'SET_SPEED', pumpSpeed)}>Применить частоту</button>
          </div>
        );
      case 'valve':
        return (
          <div className="ctrl-group">
            <label className="ctrl-label">
              Позиция клапана: {valvePos.toFixed(0)}%
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={valvePos}
                onChange={(e) => setValvePos(Number(e.target.value))}
              />
            </label>
            <button className="btn btn-start" onClick={() => void onAction(nodeId, 'SET_VALUE', valvePos)}>Применить открытие</button>
            {canManageTwin && (
              <button className="btn btn-warn" onClick={() => onFailure(nodeId)}>⚠ Отказ (заклинил)</button>
            )}
          </div>
        );
      case 'gate_valve':
        return (
          <div className="ctrl-group">
            <button className="btn btn-start" onClick={() => onAction(nodeId, 'TURN_ON')}>⭯ Открыть</button>
            <button className="btn btn-stop" onClick={() => onAction(nodeId, 'TURN_OFF')}>⏹ Закрыть</button>
            {canManageTwin && (
              <button className="btn btn-warn" onClick={() => onFailure(nodeId)}>⚠ Отказ (заклинила)</button>
            )}
          </div>
        );
      case 'heater':
        return (
          <div className="ctrl-group">
            <label className="ctrl-label">
              Расход топлива: {fuel.toFixed(2)} кг/с
              <input
                type="range"
                min={0}
                max={1.2}
                step={0.02}
                value={fuel}
                onChange={(e) => setFuel(Number(e.target.value))}
              />
            </label>
            <button className="btn btn-start" onClick={() => void onAction(nodeId, 'SET_VALUE', fuel)}>Применить расход</button>
            <button className="btn btn-danger" onClick={() => onAction(nodeId, 'EMERGENCY_STOP')}>⛔ Сброс топлива</button>
          </div>
        );
      case 'column':
        return (
          <div className="ctrl-group">
            <label className="ctrl-label">
              Флегмовое число: {reflux.toFixed(1)}
              <input
                type="range"
                min={0.5}
                max={5}
                step={0.1}
                value={reflux}
                onChange={(e) => setReflux(Number(e.target.value))}
              />
            </label>
            <button className="btn btn-start" onClick={() => void onAction(nodeId, 'SET_VALUE', reflux)}>Применить флегмовое число</button>
          </div>
        );
      case 'source': {
        const isFeed = nodeId === 'src_feed';
        return (
          <div className="ctrl-group">
            {!isFeed && (
              <label className="ctrl-label">
                Расход: {feedFlow} кг/с
                <input type="range" min={0} max={200} step={1} value={feedFlow} onChange={(e) => setFeedFlow(Number(e.target.value))} />
              </label>
            )}
            <label className="ctrl-label">
              Температура: {feedTemp} °C
              <input type="range" min={0} max={120} step={1} value={feedTemp} onChange={(e) => setFeedTemp(Number(e.target.value))} />
            </label>
            {isFeed && (
              <div className="inspector-hint">Расход сырья определяется открытием клапана FV-1/2/3 и частотой вращения насоса Н-1.</div>
            )}
            {canManageTwin && (
              <button className="btn btn-start" onClick={() => {
                const params: Record<string, number> = { temperature_c: feedTemp };
                if (!isFeed) params.flow_kg_s = feedFlow;
                onUpdateParams(nodeId, params);
              }}>
                Применить граничные условия
              </button>
            )}
          </div>
        );
      }
      case 'elou':
        return (
          <div className="ctrl-group">
            <button className="btn btn-start" onClick={() => onAction(nodeId, 'TURN_ON')}>▶ Включить</button>
            <button className="btn btn-stop" onClick={() => onAction(nodeId, 'TURN_OFF')}>■ Выключить</button>
          </div>
        );
      case 'separator': {
        // Настройка доступна только в редакторе схемы.
        if (!canEditScheme) return null;
        const lmode = schemeParams?.level_mode === 'water' ? 'water' : 'reflux';
        return (
          <div className="ctrl-group">
            <div className="panel-title" style={{ margin: 0 }}>ОБОЗНАЧЕНИЕ УРОВНЯ</div>
            <label className="param-check">
              <input
                type="radio"
                name={`lmode-${nodeId}`}
                checked={lmode === 'reflux'}
                onChange={() => onUpdateSchemeParam?.(nodeId, 'level_mode', 'reflux')}
              />
              <span>Флегма — тёмная жидкость, внизу вода, сверху пустота</span>
            </label>
            <label className="param-check">
              <input
                type="radio"
                name={`lmode-${nodeId}`}
                checked={lmode === 'water'}
                onChange={() => onUpdateSchemeParam?.(nodeId, 'level_mode', 'water')}
              />
              <span>Вода — только вода, сверху пустота</span>
            </label>
          </div>
        );
      }
      default:
        return null;
    }
  })();

  const paramRows = Object.entries(telemetry.params)
    .filter(([k, v]) => v !== null && v !== undefined)
    .map(([k, v]) => {
      const meta = PARAM_LABELS[k];
      const display =
        k === 'converged'
          ? String(v)
          : k === 'open'
            ? v
              ? 'Открыта'
              : 'Закрыта'
            : typeof v === 'number'
              ? fmtValue(v, meta?.unit ?? '')
              : String(v);
      return (
        <div className="param-row" key={k}>
          <span>{meta?.label ?? k}</span>
          <span>{display}</span>
        </div>
      );
    });

  return (
    <div>
      <div className="inspector-header" style={{ borderLeft: `3px solid ${color}` }}>
        {canEditScheme ? (
          <input
            className="rename-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={commitName}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
            spellCheck={false}
          />
        ) : (
          <div style={{ fontWeight: 700 }}>{name || nodeId}</div>
        )}
        <div style={{ fontSize: 10, color: '#7f93a6' }}>{nodeId} • {telemetry.type}</div>
      </div>
      <div style={{ color: telemetry.failed ? '#f87171' : '#35d399', fontSize: 11, fontWeight: 700, margin: '4px 0 10px' }}>
        ● {statusText}
      </div>
      <div className="param-list">{paramRows}</div>
      {canEditScheme && onUpdateDisp && (
        <div style={{ marginTop: 12 }}>
          <div className="panel-title">ПОКАЗЫВАТЬ НА СХЕМЕ</div>
          <div className="param-list">
            {Object.keys(telemetry.params)
              .filter((k) => telemetry.params[k] !== null && telemetry.params[k] !== undefined)
              .map((k) => {
                const on = disp.includes(k);
                return (
                  <label className="param-check" key={k}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => {
                        const next = on ? disp.filter((x) => x !== k) : [...disp, k];
                        onUpdateDisp(nodeId, next);
                      }}
                    />
                    <span>{PARAM_LABELS[k]?.label ?? k}</span>
                  </label>
                );
              })}
          </div>
          <div className="inspector-hint">Отмеченные параметры показываются квадратиком рядом с объектом на схеме.</div>
        </div>
      )}
      {control && <div style={{ marginTop: 12 }}>{control}</div>}
      {canEditScheme && canManageTwin && spec?.editable && spec.params.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="panel-title">ФИЗ. СВОЙСТВА</div>
          <div className="param-editor">
            {spec.params.map((p) => (
              <label className="ctrl-label" key={p.key}>
                {p.label}
                {p.unit ? ` (${p.unit})` : ''}
                <input
                  type="number"
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  value={draft[p.key] ?? p.value ?? 0}
                  onChange={(e) => setDraft((d) => ({ ...d, [p.key]: Number(e.target.value) }))}
                />
              </label>
            ))}
            <button className="btn btn-start" onClick={() => {
              const params: Record<string, number> = {};
              spec.params.forEach((p) => { params[p.key] = draft[p.key] ?? p.value ?? 0; });
              onUpdateParams(nodeId, params);
            }}>
              Применить свойства
            </button>
          </div>
        </div>
      )}
      {canEditScheme && (
        <div style={{ marginTop: 12 }}>
          <button className="btn btn-danger" onClick={() => onDelete(nodeId)}>🗑 Удалить объект</button>
          <div className="inspector-hint">Переименование — Enter. Удаление — кнопка или Delete/Backspace. Не забудьте «Сохранить схему».</div>
        </div>
      )}
    </div>
  );
}
