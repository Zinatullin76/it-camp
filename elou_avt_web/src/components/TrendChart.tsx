import { useEffect, useRef } from 'react';
import { echarts } from '../lms/echarts';
import type { HistoryResponse } from '../types';

export const SERIES_META: Record<string, { label: string; unit: string }> = {
  feed_flow: { label: 'Расход сырья', unit: 'кг/с' },
  column_pressure_bar: { label: 'Давление колонны', unit: 'бар' },
  column_temp_c: { label: 'Температура колонны', unit: '°C' },
  furnace_temp_c: { label: 'Температура печи', unit: '°C' },
  preheat_temp_c: { label: 'Температура предподогрева', unit: '°C' },
  elou_level: { label: 'Уровень ЭЛОУ', unit: 'м' },
  column_level: { label: 'Уровень колонны', unit: 'м' },
  valve_fv101_position: { label: 'Открытие FV-101', unit: '%' },
};

interface Props {
  history: HistoryResponse | null;
  param: string;
  height?: number;
  label?: string;
  unit?: string;
}

export default function TrendChart({ history, param, height = 190, label, unit }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: 'canvas' });
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const meta = label !== undefined ? { label, unit: unit ?? '' } : (SERIES_META[param] ?? { label: param, unit: '' });
    const values = history?.series[param] ?? [];
    const times = history?.times ?? [];
    chart.setOption(
      {
        backgroundColor: 'transparent',
        grid: { left: 44, right: 12, top: 28, bottom: 24 },
        tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => `${Number(v).toFixed(2)} ${meta.unit}` },
        legend: { show: false },
        xAxis: {
          type: 'category',
          data: times.map((t) => t.toFixed(0)),
          axisLine: { lineStyle: { color: '#2b3a4a' } },
          axisLabel: { color: '#64748b', fontSize: 10 },
        },
        yAxis: {
          type: 'value',
          name: meta.unit,
          nameTextStyle: { color: '#64748b' },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: '#1c2834' } },
        },
        series: [
          {
            type: 'line',
            data: values,
            showSymbol: false,
            lineStyle: { width: 2, color: '#38bdf8' },
            itemStyle: { color: '#38bdf8' },
            areaStyle: { color: 'rgba(56,189,248,0.12)' },
            animation: false,
          },
        ],
      },
      true,
    );
  }, [history, param]);

  return (
    <div
      ref={ref}
      style={{ width: '100%', height }}
      data-param={param}
    />
  );
}
