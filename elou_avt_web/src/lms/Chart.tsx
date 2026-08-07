import { useEffect, useRef } from 'react';
import { echarts } from './echarts';
import { useTheme } from './theme';

interface Props {
  option: echarts.EChartsCoreOption;
  height?: number;
  className?: string;
}

export function Chart({ option, height = 260, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!ref.current) return;
    inst.current = echarts.init(ref.current);
    const ro = new ResizeObserver(() => inst.current?.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      inst.current?.dispose();
      inst.current = null;
    };
  }, []);

  useEffect(() => {
    inst.current?.setOption(option, true);
  }, [option]);

  useEffect(() => {
    inst.current?.resize();
  }, [theme]);

  return <div ref={ref} className={className} style={{ height, width: '100%' }} />;
}

export function axisColors(theme: 'dark' | 'light') {
  const axis = theme === 'light' ? '#94a3b8' : '#64748b';
  const split = theme === 'light' ? '#e2e8f0' : '#223042';
  const label = theme === 'light' ? '#475569' : '#cbd5e1';
  return { axis, split, label };
}
