import type { ReactElement } from 'react';
import type { MnemoItem } from './mnemoTypes';
import type { MnemoLive } from './sources';
import { fmtVal } from './sources';

const ST = {
  fill: '#1b242c',
  stroke: '#7d97a8',
  strokeWidth: 1.5,
};

function Tx(props: {
  x: number;
  y: number;
  s: string;
  size: number;
  fill: string;
  anchor?: 'middle' | 'start' | 'end';
}) {
  return (
    <text
      x={props.x}
      y={props.y}
      textAnchor={props.anchor ?? 'middle'}
      fontSize={props.size}
      fill={props.fill}
      fontFamily="Segoe UI, Arial"
      pointerEvents="none"
    >
      {props.s}
    </text>
  );
}

/** Level-bar fill colour, replicating the HTML update() thresholds. */
function lvlColor(v: number): string {
  return v < 20 ? '#e2483c' : v > 88 ? '#e8b93a' : '#2f9e57';
}

function LvlRect(props: {
  x: number;
  w: number;
  y0: number;
  hh: number;
  v: number;
  opacity: number;
}) {
  const v = Math.max(0, Math.min(100, props.v));
  const hv = Math.max(2, (props.hh - 6) * v / 100);
  return (
    <rect
      x={props.x}
      y={props.y0 + props.hh - 3 - hv}
      width={props.w}
      height={hv}
      fill={lvlColor(v)}
      opacity={props.opacity}
    />
  );
}

export function renderItem(e: MnemoItem, live: MnemoLive): ReactElement {
  const x = e.x;
  const y = e.y;
  const w = e.w || 60;
  const h = e.h || 30;

  switch (e.t) {
    case 'col': {
      const r = w / 2;
      const hd = r * 0.55;
      const sump = e.sump || 0;
      const N = e.tr == null ? 10 : e.tr;
      const tBot = y + h - (sump > 0 ? sump : hd + 4);
      const pit = (tBot - (y + hd + 4)) / N;
      const cols: ReactElement[] = [
        <path
          key="shell"
          d={`M${x} ${y + hd} A${r} ${hd} 0 0 1 ${x + w} ${y + hd} L${x + w} ${y + h - hd} A${r} ${hd} 0 0 1 ${x} ${y + h - hd} Z`}
          {...ST}
        />,
      ];
      if (sump > 0) {
        cols.push(
          <rect key="sump" x={x + 1} y={tBot} width={w - 2} height={y + h - tBot - 1} fill="#16202a" opacity={0.85} />,
        );
        cols.push(
          <LvlRect key="lv" x={x + 2} w={w - 4} y0={tBot} hh={y + h - tBot} v={live.lvl(e.lv || '')} opacity={0.6} />,
        );
        cols.push(
          <line key="sline" x1={x + 1} y1={tBot} x2={x + w - 1} y2={tBot} stroke="#7d97a8" strokeWidth={1.3} strokeDasharray="5 4" />,
        );
        cols.push(<Tx key="kub" x={x + w / 2} y={tBot + 13} s="КУБ" size={8} fill="#8ba0ae" />);
      } else if (e.lv) {
        cols.push(
          <LvlRect key="lv" x={x + 2} w={w - 4} y0={y} hh={h} v={live.lvl(e.lv)} opacity={0.5} />,
        );
      }
      const marks = e.marks || [];
      for (let i = 1; i <= N; i++) {
        const yy = tBot - (i - 0.5) * pit;
        if (i === e.blind) {
          cols.push(
            <line key={`t${i}`} x1={x + 1} y1={yy} x2={x + w - 1} y2={yy} stroke="#c9d8e2" strokeWidth={2.4} />,
          );
          cols.push(
            <LvlRect key={`tb${i}`} x={x + 3} w={w - 6} y0={yy - 16} hh={16} v={live.lvl(e.lvb || '')} opacity={0.65} />,
          );
        } else {
          const off = i % 2 ? 4 : 9;
          cols.push(
            <line key={`t${i}`} x1={x + off} y1={yy} x2={x + w - off} y2={yy} stroke="#42596a" strokeWidth={1} />,
          );
        }
        if (marks.indexOf(i) >= 0) {
          cols.push(<Tx key={`m${i}`} x={x + w - 3} y={yy - 3} s={String(i)} size={7.5} fill="#9fc0d4" anchor="end" />);
        }
      }
      cols.push(<Tx key="n" x={x + w / 2} y={y + h / 2} s={e.n || ''} size={Math.min(15, w * 0.3)} fill="#eef6fa" />);
      if (e.s) cols.push(<Tx key="s" x={x + w / 2} y={y - 10} s={e.s} size={9.5} fill="#7d94a3" />);
      return <g>{cols}</g>;
    }

    case 'vves': {
      const r = w / 2;
      const hd = r * 0.5;
      const b = y + h - 4;
      const top = y + hd + 2;
      const hh = b - top;
      const tot = Math.max(0, Math.min(100, live.lvl(e.lv || '')));
      const wl = Math.max(0, Math.min(tot, live.lw(e.lvw || '')));
      const yT = b - (hh * tot) / 100;
      const yW = b - (hh * wl) / 100;
      return (
        <g>
          <path
            d={`M${x} ${y + hd} A${r} ${hd} 0 0 1 ${x + w} ${y + hd} L${x + w} ${y + h - hd} A${r} ${hd} 0 0 1 ${x} ${y + h - hd} Z`}
            {...ST}
          />
          <rect x={x + 3} y={yT} width={w - 6} height={Math.max(1, yW - yT)} fill={tot < 20 ? '#e2483c' : tot > 88 ? '#e8b93a' : '#d2833c'} opacity={0.55} />
          <rect x={x + 3} y={yW} width={w - 6} height={Math.max(1, b - yW)} fill={wl > 80 ? '#e2483c' : wl < 20 ? '#e8b93a' : '#2f6feb'} opacity={0.7} />
          <line x1={x - 10} y1={yW} x2={x + w + 10} y2={yW} stroke="#4fc3f7" strokeWidth={1.5} strokeDasharray="6 4" />
          <Tx x={x + w + 14} y={yW - 4} s="раздел фаз" size={8} fill="#4fc3f7" anchor="start" />
          <Tx x={x + w / 2} y={y + hd + 18} s={e.n || ''} size={12} fill="#eef6fa" />
          {e.s ? <Tx x={x + w / 2} y={y - 8} s={e.s} size={9} fill="#7d94a3" /> : null}
        </g>
      );
    }

    case 'note': {
      const lines = (e.n || '').split('|');
      const ww = e.w || 270;
      return (
        <g>
          <rect x={x} y={y} width={ww} height={15 + lines.length * 13} rx={3} fill="#111a20" stroke="#2b3843" />
          {lines.map((l, i) => (
            <Tx key={i} x={x + 8} y={y + 18 + i * 13} s={l} size={9} fill={i ? '#8ba0ae' : '#cfe0ea'} anchor="start" />
          ))}
        </g>
      );
    }

    case 'ves':
    case 'sett':
    case 'ed': {
      const r = h / 2;
      const el = [];
      el.push(
        <path
          key="shell"
          d={`M${x + r * 0.6} ${y} L${x + w - r * 0.6} ${y} A${r * 0.6} ${r} 0 0 1 ${x + w - r * 0.6} ${y + h} L${x + r * 0.6} ${y + h} A${r * 0.6} ${r} 0 0 1 ${x + r * 0.6} ${y} Z`}
          {...ST}
        />,
      );
      if (e.t === 'sett') {
        el.push(
          <line key="phase" x1={x + 4} y1={y + h * 0.62} x2={x + w - 4} y2={y + h * 0.62} stroke="#2f6feb" strokeWidth={1.3} strokeDasharray="5 3" />,
        );
      }
      if (e.t === 'ed') {
        el.push(
          <line key="e1" x1={x + 16} y1={y + h * 0.3} x2={x + w - 16} y2={y + h * 0.3} stroke="#e8b93a" strokeWidth={2} />,
          <line key="e2" x1={x + 16} y1={y + h * 0.5} x2={x + w - 16} y2={y + h * 0.5} stroke="#e8b93a" strokeWidth={2} />,
          <path
            key="hv"
            className="mn-hv"
            opacity={live.edVolt ? 1 : 0.15}
            d={`M${x + w / 2 - 6} ${y - 14} l6 8 l-4 1 l6 8`}
            fill="none"
            stroke="#e8b93a"
            strokeWidth={1.6}
          />,
        );
      }
      if (e.lv) {
        el.push(<LvlRect key="lv" x={x + 3} w={w - 6} y0={y} hh={h} v={live.lvl(e.lv)} opacity={0.55} />);
      }
      el.push(
        <Tx key="n" x={x + w / 2} y={e.t === 'ed' ? y + h - 7 : y + h / 2 + 4} s={e.n || ''} size={11} fill="#eef6fa" />,
      );
      if (e.s) {
        el.push(
          <Tx key="s" x={x + w / 2} y={y - (e.t === 'ed' ? 22 : 8)} s={e.s} size={9} fill="#7d94a3" />,
        );
      }
      return <g>{el}</g>;
    }

    case 'mix':
      return (
        <g>
          <circle cx={x} cy={y} r={13} {...ST} />
          <path d={`M${x - 8} ${y - 8} L${x + 8} ${y + 8} M${x - 8} ${y + 8} L${x + 8} ${y - 8}`} stroke="#7d97a8" strokeWidth={1.4} />
          <Tx x={x} y={y + 27} s={e.n || ''} size={9} fill="#9db3c0" />
        </g>
      );

    case 'hx':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx={h / 2} {...ST} />
          <line x1={x + 8} y1={y + h / 2} x2={x + w - 8} y2={y + h / 2} stroke="#9fb6c4" strokeWidth={1.6} />
          <line x1={x + 10} y1={y + 4} x2={x + 10} y2={y + h - 4} stroke="#9fb6c4" strokeWidth={1.3} />
          <line x1={x + w - 10} y1={y + 4} x2={x + w - 10} y2={y + h - 4} stroke="#9fb6c4" strokeWidth={1.3} />
          <line x1={x + w * 0.34} y1={y} x2={x + w * 0.34} y2={y - 6} stroke="#7d97a8" strokeWidth={1.4} />
          <line x1={x + w * 0.66} y1={y + h} x2={x + w * 0.66} y2={y + h + 6} stroke="#7d97a8" strokeWidth={1.4} />
          <Tx x={x + w / 2} y={y + h / 2 - 5} s={e.n || ''} size={10} fill="#e3eef4" />
          {e.s ? <Tx x={x + w / 2} y={y + h + 16} s={e.s} size={8.5} fill="#7d94a3" /> : null}
        </g>
      );

    case 'air': {
      const cx = x + w / 2;
      const cy = y + h + 14;
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx={2} {...ST} />
          <line x1={x + 5} y1={y + h / 2} x2={x + w - 5} y2={y + h / 2} stroke="#9fb6c4" strokeWidth={1.4} />
          <circle cx={cx} cy={cy} r={10} fill="none" stroke="#4fc3f7" strokeWidth={1.4} />
          <g className="mn-fanb" style={{ transformOrigin: `${cx}px ${cy}px` }}>
            {[0, 120, 240].map((a) => (
              <path
                key={a}
                d={`M${cx} ${cy} L${cx + 9 * Math.cos((a * Math.PI) / 180)} ${cy + 9 * Math.sin((a * Math.PI) / 180)}`}
                stroke="#4fc3f7"
                strokeWidth={2}
              />
            ))}
          </g>
          <Tx x={x + w / 2} y={y - 7} s={e.n || ''} size={9.5} fill="#9db3c0" />
        </g>
      );
    }

    case 'fur': {
      const n = Math.max(3, Math.floor(h / 28));
      let d = '';
      for (let i = 0; i < n; i++) {
        const y1 = y + 14 + (i * (h - 30)) / n;
        const y2 = y1 + (h - 30) / n / 2;
        d += `M${x + 8} ${y1} L${x + w - 8} ${y1} M${x + w - 8} ${y1} L${x + w - 8} ${y2} L${x + 8} ${y2} L${x + 8} ${y2 + (h - 30) / n / 2} `;
      }
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx={3} fill="#241b1b" stroke="#96604c" strokeWidth={1.6} />
          <rect x={x + w / 2 - 7} y={y - 16} width={14} height={16} fill="#241b1b" stroke="#96604c" strokeWidth={1.4} />
          <path d={d} fill="none" stroke="#c9866a" strokeWidth={1.3} opacity={0.75} />
          <rect
            className={live.fireOn ? 'mn-fire on' : 'mn-fire'}
            x={x + 6}
            y={y + h - 14}
            width={w - 12}
            height={9}
            fill="#e05252"
          />
          <Tx x={x + w / 2} y={y + h / 2} s={e.n || ''} size={15} fill="#f3ddd6" />
        </g>
      );
    }

    case 'pump':
      return (
        <g>
          <circle cx={x + 14} cy={y + 14} r={14} {...ST} />
          <path d={`M${x + 8} ${y + 7} L${x + 24} ${y + 14} L${x + 8} ${y + 21} Z`} fill="#4fd1c5" />
          <line x1={x + 2} y1={y + 30} x2={x + 26} y2={y + 30} stroke="#7d97a8" strokeWidth={2} />
          <Tx x={x + 14} y={y + 44} s={e.n || ''} size={10} fill="#b8ccd8" />
          {e.s ? <Tx x={x + 14} y={y + 54} s={e.s} size={8.5} fill="#6d8492" /> : null}
        </g>
      );

    case 'valve': {
      const rot = e.r ? `rotate(${e.r} ${x} ${y})` : undefined;
      const c = e.ctrl ? live.ctrl(e.ctrl) : undefined;
      const inner: ReactElement[] = [];
      inner.push(
        <path key="l" d={`M${x - 12} ${y - 9} L${x} ${y} L${x - 12} ${y + 9} Z`} fill="#1b242c" stroke="#c9d8e2" strokeWidth={1.5} />,
        <path
          key="r"
          d={`M${x + 12} ${y - 9} L${x} ${y} L${x + 12} ${y + 9} Z`}
          fill={e.vt === 'check' ? '#c9d8e2' : '#1b242c'}
          stroke="#c9d8e2"
          strokeWidth={1.5}
        />,
      );
      if (e.vt === 'cv') {
        inner.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 18} stroke="#c9d8e2" strokeWidth={1.5} />,
          <path key="cap" d={`M${x - 11} ${y - 18} A11 8 0 0 1 ${x + 11} ${y - 18} Z`} fill="#12252b" stroke="#4fd1c5" strokeWidth={1.5} />,
          <rect key="flow" x={x - 11} y={y - 19.5} width={c ? 22 * c.out / 100 : 0} height={3.4} fill="#4fd1c5" />,
        );
      } else if (e.vt === 'psv') {
        inner.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 15} stroke="#c9d8e2" strokeWidth={1.5} />,
          <path key="cap" d={`M${x - 5} ${y - 15} l10 -3 l-10 -3 l10 -3`} fill="none" stroke="#c9d8e2" strokeWidth={1.4} />,
        );
      } else if (e.vt !== 'check') {
        inner.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 14} stroke="#c9d8e2" strokeWidth={1.5} />,
          <line key="cap" x1={x - 9} y1={y - 14} x2={x + 9} y2={y - 14} stroke="#c9d8e2" strokeWidth={2.4} />,
        );
      }
      return (
        <g>
          <g transform={rot}>
            {inner}
          </g>
          {e.st ? <Tx x={x} y={y + 24} s={e.st} size={9} fill="#e8b93a" /> : null}
          {c ? (
            <text
              x={x}
              y={y + 25}
              textAnchor="middle"
              fontSize={9.5}
              fontFamily="Consolas"
              fill="#4fd1c5"
              pointerEvents="none"
            >
              {c.out.toFixed(0)} %
            </text>
          ) : null}
        </g>
      );
    }

    case 'ins': {
      const tag = e.ctrl || e.tag || '';
      const c = e.ctrl ? live.ctrl(e.ctrl) : undefined;
      const ww = e.w || 72;
      const hh = 24;
      const col = c ? '#4fd1c5' : '#3d5261';
      let v: number | null = null;
      if (e.ctrl) v = c ? c.pv : null;
      else if (e.src) v = live.sval(e.src);
      const vStr = fmtVal(v);
      const ivFill =
        v != null && e.hi != null && v >= e.hi
          ? '#e2483c'
          : c && c.mode === 'РУЧ'
            ? '#e8b93a'
            : '#e6f1f7';
      return (
        <g>
          <rect x={x} y={y} width={ww} height={hh} rx={2} fill={c ? '#12252b' : '#131a1f'} stroke={col} strokeWidth={1.1} />
          <Tx x={x + 4} y={y + 9.5} s={tag} size={8} fill={c ? '#4fd1c5' : '#7d94a3'} anchor="start" />
          {e.u ? <Tx x={x + 4} y={y + 20} s={e.u} size={7.5} fill="#6d8492" anchor="start" /> : null}
          <text
            x={x + ww - 4}
            y={y + 20}
            textAnchor="end"
            fontSize={11.5}
            fontFamily="Consolas"
            fill={ivFill}
            pointerEvents="none"
          >
            {vStr}
          </text>
        </g>
      );
    }

    case 'box': {
      const col = e.fl ? live.flowColor(e.fl) : '#5d7383';
      const inner: ReactElement[] = [
        <rect key="b" x={x} y={y} width={w} height={h} rx={2} fill="#111a20" stroke={col} strokeWidth={1.4} />,
        <Tx key="n" x={x + w / 2} y={y + (e.s ? 16 : h / 2 + 4)} s={e.n || ''} size={10} fill="#dce9f0" />,
      ];
      if (e.s) {
        const words = e.s.split(' ');
        let line = '';
        const lines: string[] = [];
        for (const wd of words) {
          if ((line + wd).length > 36) {
            lines.push(line);
            line = wd + ' ';
          } else {
            line += wd + ' ';
          }
        }
        lines.push(line);
        lines.forEach((l, i) => inner.push(
          <Tx key={`s${i}`} x={x + w / 2} y={y + 31 + i * 12} s={l.trim()} size={8.6} fill="#7d94a3" />,
        ));
      }
      return <g>{inner}</g>;
    }

    case 'text':
      return <Tx x={x} y={y} s={e.n || ''} size={9.5} fill="#7d94a3" anchor="start" />;

    default:
      return <g />;
  }
}

export function itemBBox(e: MnemoItem): [number, number, number, number] {
  if (e.t === 'pump') return [e.x - 2, e.y - 4, 32, 60];
  if (e.t === 'mix') return [e.x - 15, e.y - 15, 30, 45];
  if (e.t === 'valve') return [e.x - 16, e.y - 22, 32, 50];
  if (e.t === 'ins') return [e.x - 2, e.y - 2, (e.w || 72) + 4, 28];
  if (e.t === 'text') return [e.x - 2, e.y - 11, 200, 15];
  if (e.t === 'note') return [e.x - 2, e.y - 2, (e.w || 270) + 4, 19 + String(e.n || '').split('|').length * 13];
  return [e.x - 3, e.y - 14, (e.w || 60) + 6, (e.h || 30) + 28];
}
