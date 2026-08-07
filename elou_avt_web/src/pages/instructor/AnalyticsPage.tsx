import { useMemo } from 'react';
import type { EChartsCoreOption } from '../../lms/echarts';
import { api } from '../../api';
import type { LmsAnalytics } from '../../types';
import { useTheme } from '../../lms/theme';
import { Chart, axisColors } from '../../lms/Chart';
import { Card, Empty, Err, Grid, Loader, Page, Stat, useAsync } from '../../lms/ui';

export default function AnalyticsPage() {
  const { data, error, loading, reload } = useAsync<LmsAnalytics>(() => api.lmsAnalytics(), []);
  const { theme } = useTheme();
  const c = useMemo(() => axisColors(theme), [theme]);

  const baseAxis = {
    axisLine: { lineStyle: { color: c.axis } },
    axisLabel: { color: c.label },
    splitLine: { lineStyle: { color: c.split } },
  };

  const barCommon: EChartsCoreOption = useMemo(() => ({
    textStyle: { color: c.label },
    tooltip: { trigger: 'axis', backgroundColor: 'var(--panel-2)', borderColor: 'var(--border)', textStyle: { color: 'var(--text)' } },
    grid: { left: 10, right: 16, top: 24, bottom: 6, containLabel: true },
  }), [c]);

  if (loading && !data) return <Loader />;
  if (error && !data) return <Err text={error} />;
  if (!data) return <Empty />;

  const a = data;

  const groupRating: EChartsCoreOption = {
    ...barCommon,
    xAxis: { type: 'value', ...baseAxis },
    yAxis: { type: 'category', data: a.group_rating.map((g) => g.group_name), ...baseAxis },
    series: [
      {
        type: 'bar',
        data: a.group_rating.map((g) => g.avg_score),
        itemStyle: { color: 'var(--accent)', borderRadius: [0, 6, 6, 0] },
        barMaxWidth: 22,
        label: { show: true, position: 'right', color: c.label, formatter: '{c}' },
      },
    ],
  };

  const frequentErrors: EChartsCoreOption = {
    ...barCommon,
    xAxis: { type: 'category', data: a.frequent_errors.map((e) => e.rule_error_type), ...baseAxis, axisLabel: { ...baseAxis.axisLabel, rotate: 24, interval: 0, fontSize: 9 } },
    yAxis: { type: 'value', ...baseAxis },
    series: [
      {
        type: 'bar',
        data: a.frequent_errors.map((e) => e.count),
        itemStyle: { color: 'var(--danger)', borderRadius: [6, 6, 0, 0] },
        barMaxWidth: 26,
      },
    ],
  };

  const competencyDistribution: EChartsCoreOption = {
    ...barCommon,
    xAxis: { type: 'category', data: a.competency_distribution.map((x) => x.title), ...baseAxis, axisLabel: { ...baseAxis.axisLabel, rotate: 20, interval: 0, fontSize: 9 } },
    yAxis: { type: 'value', max: 100, ...baseAxis },
    series: [
      {
        type: 'bar',
        data: a.competency_distribution.map((x) => x.avg_level),
        itemStyle: { color: 'var(--ok)', borderRadius: [6, 6, 0, 0] },
        barMaxWidth: 30,
      },
    ],
  };

  const dynamics: EChartsCoreOption = {
    ...barCommon,
    xAxis: { type: 'category', data: a.learning_dynamics.map((d) => d.date), ...baseAxis },
    yAxis: { type: 'value', min: 0, max: 100, ...baseAxis },
    series: [
      {
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: a.learning_dynamics.map((d) => d.avg_score),
        lineStyle: { color: 'var(--accent)', width: 3 },
        itemStyle: { color: 'var(--accent)' },
        areaStyle: { color: 'rgba(56,189,248,0.15)' },
        label: { show: true, color: c.label, fontSize: 9 },
      },
    ],
  };

  const statusPie: EChartsCoreOption = {
    textStyle: { color: c.label },
    tooltip: { trigger: 'item', backgroundColor: 'var(--panel-2)', borderColor: 'var(--border)', textStyle: { color: 'var(--text)' } },
    legend: { bottom: 0, textStyle: { color: c.label }, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['38%', '68%'],
        center: ['50%', '44%'],
        data: a.status_distribution.map((s) => ({ name: s.status, value: s.count })),
        label: { color: c.label },
        itemStyle: { borderColor: 'var(--panel)', borderWidth: 2 },
      },
    ],
  };

  return (
    <Page
      title="Аналитика"
      subtitle="Статистика обучения и распределение компетенций"
      actions={<button className="btn" onClick={() => void reload()}>Обновить</button>}
    >
      <Grid min={180}>
        <Stat label="Средний балл" value={a.avg_score.toFixed(1)} tone="accent" hint="завершённые сессии" />
        <Stat label="Сессий всего" value={a.total_sessions} hint={`завершено ${a.completed_sessions}`} />
        <Stat label="Средняя длительность" value={`${(a.avg_duration_s / 60).toFixed(1)} мин`} hint="по завершённым" />
        <Stat label="Групп в рейтинге" value={a.group_rating.length} hint="участвуют в статистике" />
      </Grid>

      <div className="hero-row">
        <div className="hero-main">
          <Card title="Динамика обучения" subtitle="Средний балл по дням">
            <Chart option={dynamics} height={220} />
          </Card>
          <Card title="Наиболее частые ошибки" subtitle="Типы ошибок в сессиях">
            <Chart option={frequentErrors} height={240} />
          </Card>
        </div>
        <div className="hero-side">
          <Card title="Рейтинг групп" subtitle="Средний балл по группам">
            <Chart option={groupRating} height={Math.max(180, a.group_rating.length * 44 + 30)} />
          </Card>
          <Card title="Статусы сессий" subtitle="Распределение">
            <Chart option={statusPie} height={200} />
          </Card>
        </div>
      </div>

      <Card title="Распределение компетенций" subtitle="Средний уровень по группе">
        <Chart option={competencyDistribution} height={240} />
      </Card>
    </Page>
  );
}
