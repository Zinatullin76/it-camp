import type { ApiState, NodeTelemetry } from '../types';
import { TYPE_COLORS, fmtValue } from '../schemeConfig';

interface Props {
  live: ApiState | null;
}

// Curated live parameters shown per equipment type in the summary table.
const ROWS: Record<string, string[]> = {
  pump: ['flow_kg_s', 'power_w', 'pressure_bar'],
  valve: ['position', 'flow_kg_s', 'pressure_in_bar', 'pressure_out_bar'],
  heater: ['outlet_temp_c', 'duty_w'],
  heat_exchanger: ['duty_w', 't_cold_out_c', 't_hot_out_c'],
  column: ['flow_kg_s', 'top_temp_c', 'bottom_temp_c'],
  elou: ['flow_kg_s', 'power_w', 'level_m'],
  separator: ['level_m', 'in_flow', 'out_flow'],
  tank: ['level_m', 'in_flow', 'out_flow'],
  source: ['flow_kg_s', 'temperature_c'],
  sink: ['flow_kg_s'],
};

const PARAM_META: Record<string, { label: string; unit: string }> = {
  flow_kg_s: { label: 'Расход', unit: 'кг/с' },
  power_w: { label: 'Мощность', unit: 'кВт' },
  pressure_bar: { label: 'Давление', unit: 'бар' },
  position: { label: 'Открытие', unit: '%' },
  pressure_in_bar: { label: 'P вход', unit: 'бар' },
  pressure_out_bar: { label: 'P выход', unit: 'бар' },
  outlet_temp_c: { label: 'T выхода', unit: '°C' },
  duty_w: { label: 'Нагрузка', unit: 'МВт' },
  t_cold_out_c: { label: 'Хол. выход', unit: '°C' },
  t_hot_out_c: { label: 'Горяч. выход', unit: '°C' },
  top_temp_c: { label: 'T верха', unit: '°C' },
  bottom_temp_c: { label: 'T низа', unit: '°C' },
  level_m: { label: 'Уровень', unit: 'м' },
  in_flow: { label: 'Вход', unit: 'кг/с' },
  out_flow: { label: 'Выход', unit: 'кг/с' },
  temperature_c: { label: 'Температура', unit: '°C' },
};

const TYPE_LABELS: Record<string, string> = {
  pump: 'Насосы',
  valve: 'Регулирующие клапаны',
  heater: 'Печи',
  heat_exchanger: 'Теплообменники',
  column: 'Колонны',
  elou: 'ЭЛОУ',
  separator: 'Сепараторы',
  tank: 'Ёмкости',
  source: 'Границы (источник)',
  sink: 'Границы (продукт)',
};

function kpi(label: string, value: string, hint?: string) {
  return (
    <div className="dash-kpi" key={label}>
      <div className="dash-kpi-label">{label}</div>
      <div className="dash-kpi-value">{value}</div>
      {hint && <div className="dash-kpi-hint">{hint}</div>}
    </div>
  );
}

function eqStatusDot(t: NodeTelemetry) {
  const color = t.failed ? '#f87171' : t.running === null ? '#64748b' : t.running ? '#35d399' : '#fbbf24';
  return <span className="dash-dot" style={{ background: color }} />;
}

export default function Dashboard({ live }: Props) {
  if (!live) {
    return <div className="dash-empty">Данные модели ещё не получены…</div>;
  }

  const equip = live.equipment ?? {};
  const feed = live.feed;
  const feedFlow = live.feed_flow_kg_s ?? 0;
  const prodFlow = live.product_flow ?? 0;
  const recovery = feedFlow > 0 ? (prodFlow / feedFlow) * 100 : 0;

  const heatDutyMw = Object.values(live.heat_duty ?? {}).reduce((a, b) => a + (Number(b) || 0), 0) / 1e6;
  const pumpPowerKw = Object.values(equip)
    .filter((t) => t.type === 'pump')
    .reduce((a, t) => a + (Number(t.params.power_w) || 0), 0);
  const elouPowerKw = Object.values(equip)
    .filter((t) => t.type === 'elou')
    .reduce((a, t) => a + (Number(t.params.power_w) || 0), 0);

  const alarmCounts = {
    CRITICAL: live.alarms.filter((a) => a.severity === 'CRITICAL').length,
    HIGH: live.alarms.filter((a) => a.severity === 'HIGH').length,
    MEDIUM: live.alarms.filter((a) => a.severity === 'MEDIUM').length,
    LOW: live.alarms.filter((a) => a.severity === 'LOW').length,
  };

  // Group equipment by type preserving scheme order.
  const grouped = new Map<string, { id: string; t: NodeTelemetry }[]>();
  for (const [id, t] of Object.entries(equip)) {
    const arr = grouped.get(t.type) ?? [];
    arr.push({ id, t });
    grouped.set(t.type, arr);
  }
  const typeOrder = [...grouped.keys()].sort((a, b) => {
    const la = TYPE_LABELS[a] ?? a;
    const lb = TYPE_LABELS[b] ?? b;
    return la.localeCompare(lb, 'ru');
  });

  return (
    <div className="dash">
      <div className="dash-hero">
        <div className="dash-hero-title">СВОДНЫЙ ДАШБОРД МОДЕЛИ</div>
        <div className="dash-hero-meta">
          <span className="chip chip-info">t = {(live.simulation_time ?? 0).toFixed(0)} с</span>
          <span className="chip chip-info">Статус: {live.status}</span>
          <span className={`chip ${live.alarms.length > 0 ? 'chip-alarm' : 'chip-ok'}`}>⚠ {live.alarms.length} аварий</span>
        </div>
      </div>

      {/* Boundary conditions + KPIs */}
      <div className="dash-grid">
        {kpi('Расход сырья', fmtValue(feedFlow, ' кг/с'), `≈ ${fmtValue(live.feed_flow_m3_h ?? 0, ' м³/ч')}`)}
        {kpi('Температура сырья', fmtValue(feed?.temperature_c, ' °C'))}
        {kpi('Давление сырья', fmtValue(feed?.pressure_bar, ' бар'))}
        {kpi('Продукт (сумма)', fmtValue(prodFlow, ' кг/с'))}
        {kpi('Извлечение продукта', `${recovery.toFixed(1)} %`)}
        {kpi('Тепловая нагрузка (всего)', fmtValue(heatDutyMw, ' МВт'))}
        {kpi('Мощность насосов', fmtValue(pumpPowerKw, ' кВт'))}
        {kpi('Мощность ЭЛОУ', fmtValue(elouPowerKw, ' кВт'))}
      </div>

      {/* Equipment summary */}
      <div className="dash-card">
        <div className="dash-card-title">ОБОРУДОВАНИЕ — {Object.keys(equip).length} объектов</div>
        {typeOrder.map((type) => (
          <div key={type} className="dash-group">
            <div className="dash-group-title" style={{ borderLeftColor: TYPE_COLORS[type] ?? '#38bdf8' }}>
              {TYPE_LABELS[type] ?? type}
              <span className="dash-count">{grouped.get(type)!.length}</span>
            </div>
            <table className="dash-table">
              <tbody>
                {grouped.get(type)!.map(({ id, t }) => (
                  <tr key={id}>
                    <td className="dash-id">
                      {eqStatusDot(t)} {t.name || id}
                      <div className="dash-id-sub">{id} · {t.failed ? 'АВАРИЯ' : t.running === null ? 'граница' : t.running ? 'работает' : 'остановлен'}</div>
                    </td>
                    {((ROWS[type] ?? []).map((k) => {
                      const v = t.params[k];
                      const meta = PARAM_META[k];
                      return (
                        <td key={k} className="dash-cell">
                          <div className="dash-cell-label">{meta?.label ?? k}</div>
                          <div className="dash-cell-value">{fmtValue(Number(v), meta?.unit ?? '')}</div>
                        </td>
                      );
                    }))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* Alarms */}
      <div className="dash-card">
        <div className="dash-card-title">
          АВАРИИ — {live.alarms.length}
          {live.alarms.length > 0 && (
            <span className="dash-alarm-chips">
              <span className="chip chip-bad">CRITICAL {alarmCounts.CRITICAL}</span>
              <span className="chip chip-alarm">HIGH {alarmCounts.HIGH}</span>
              <span className="chip chip-info">MEDIUM {alarmCounts.MEDIUM}</span>
              <span className="chip chip-info">LOW {alarmCounts.LOW}</span>
            </span>
          )}
        </div>
        {live.alarms.length === 0 ? (
          <div className="dash-empty">Активных аварий нет.</div>
        ) : (
          <table className="dash-table">
            <tbody>
              {live.alarms.map((a, i) => (
                <tr key={`${a.id}-${i}`}>
                  <td className="dash-id">
                    <span className="dash-dot" style={{ background: a.severity === 'CRITICAL' ? '#f87171' : a.severity === 'HIGH' ? '#fbbf24' : '#38bdf8' }} />
                    {a.description || a.parameter}
                    <div className="dash-id-sub">{a.id} · {a.severity}</div>
                  </td>
                  <td className="dash-cell">
                    <div className="dash-cell-label">факт / предел</div>
                    <div className="dash-cell-value">{fmtValue(a.actual_value)} / {fmtValue(a.threshold)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Errors */}
      <div className="dash-card">
        <div className="dash-card-title">СОБЫТИЯ / ОШИБКИ — {live.errors.length}</div>
        {live.errors.length === 0 ? (
          <div className="dash-empty">Ошибок оператора нет.</div>
        ) : (
          <ul className="dash-errors">
            {live.errors.slice().reverse().map((e, i) => (
              <li key={i}>{JSON.stringify(e)}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
