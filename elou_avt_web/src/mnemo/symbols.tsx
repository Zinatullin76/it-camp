import type { CSSProperties, ReactElement } from 'react';
import type { MnemoItem } from './mnemoTypes';
import type { MnemoLive } from './sources';
import { fmtVal } from './sources';

const ST: CSSProperties = {
  fill: 'var(--mn-fill)',
  stroke: 'var(--mn-stroke)',
  strokeWidth: 1.5,
};

function chW(ch: string, size: number): number {
  if (ch === ' ') return size * 0.34;
  if (ch === '|') return size * 0.3;
  if (/[0-9]/.test(ch)) return size * 0.62;
  if (/[A-Z]/.test(ch)) return size * 0.68;
  if (/[a-z]/.test(ch)) return size * 0.55;
  if (',.:;/-'.indexOf(ch) >= 0) return size * 0.35;
  if (ch === '(' || ch === ')') return size * 0.45;
  return size * 0.62;
}

function textW(s: string, size: number): number {
  let w = 0;
  for (const c of s) w += chW(c, size);
  return w;
}

/** Wrap a label into lines that fit within maxW (in symbol units). */
export function wrapLines(s: string, size: number, maxW: number): string[] {
  const words = s.split(' ');
  const lines: string[] = [];
  let cur = '';
  for (const wd of words) {
    const cand = cur ? `${cur} ${wd}` : wd;
    if (textW(cand, size) <= maxW || !cur) {
      cur = cand;
    } else {
      lines.push(cur);
      cur = wd;
    }
  }
  if (cur) lines.push(cur);
  return lines.length ? lines : [''];
}

function labelLines(s: string | undefined, size: number, maxW: number): number {
  return s ? wrapLines(s, size, maxW).length : 0;
}

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
      style={{ fill: props.fill }}
      fontFamily="Segoe UI, Arial"
      pointerEvents="none"
    >
      {props.s}
    </text>
  );
}

/** Multi-line (wrapped) label. Lines stack downward, or upward when `up`. */
function Txt(props: {
  x: number;
  y: number;
  s: string;
  size: number;
  fill: string;
  maxW?: number;
  up?: boolean;
  anchor?: 'middle' | 'start' | 'end';
}) {
  const lines = props.maxW ? wrapLines(props.s, props.size, props.maxW) : [props.s];
  const lh = props.size * 1.18;
  return (
    <g pointerEvents="none">
      {lines.map((l, i) => (
        <text
          key={i}
          x={props.x}
          y={props.up ? props.y - i * lh : props.y + i * lh}
          textAnchor={props.anchor ?? 'middle'}
          fontSize={props.size}
          style={{ fill: props.fill }}
          fontFamily="Segoe UI, Arial"
        >
          {l}
        </text>
      ))}
    </g>
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
          style={ST}
        />,
      ];
      if (sump > 0) {
        cols.push(
          <rect key="sump" x={x + 1} y={tBot} width={w - 2} height={y + h - tBot - 1} style={{ fill: 'var(--mn-fill)' }} opacity={0.85} />,
        );
        cols.push(
          <LvlRect key="lv" x={x + 2} w={w - 4} y0={tBot} hh={y + h - tBot} v={live.lvl(e.lv || '')} opacity={0.6} />,
        );
        cols.push(
          <line key="sline" x1={x + 1} y1={tBot} x2={x + w - 1} y2={tBot} style={{ stroke: 'var(--mn-stroke)', strokeWidth: 1.3, strokeDasharray: '5 4' }} />,
        );
        cols.push(<Tx key="kub" x={x + w / 2} y={tBot + 13} s="КУБ" size={8} fill="var(--mn-text-dim)" />);
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
            <line key={`t${i}`} x1={x + 1} y1={yy} x2={x + w - 1} y2={yy} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 2.4 }} />,
          );
          cols.push(
            <LvlRect key={`tb${i}`} x={x + 3} w={w - 6} y0={yy - 16} hh={16} v={live.lvl(e.lvb || '')} opacity={0.65} />,
          );
        } else {
          const off = i % 2 ? 4 : 9;
          cols.push(
            <line key={`t${i}`} x1={x + off} y1={yy} x2={x + w - off} y2={yy} style={{ stroke: 'var(--mn-line)', strokeWidth: 1 }} />,
          );
        }
        if (marks.indexOf(i) >= 0) {
          cols.push(<Tx key={`m${i}`} x={x + w - 3} y={yy - 3} s={String(i)} size={7.5} fill="var(--mn-text-dim)" anchor="end" />);
        }
      }
      cols.push(
        <Txt key="n" x={x + w / 2} y={y + h + 16} s={e.n || ''} size={11} fill="var(--mn-text)" maxW={w + 8} />,
      );
      if (e.s) {
        cols.push(
          <Txt key="s" x={x + w / 2} y={y - 10} up s={e.s} size={9.5} fill="var(--mn-text-dim)" maxW={w + 30} />,
        );
      }
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
            style={ST}
          />
          <rect x={x + 3} y={yT} width={w - 6} height={Math.max(1, yW - yT)} fill={tot < 20 ? '#e2483c' : tot > 88 ? '#e8b93a' : '#d2833c'} opacity={0.55} />
          <rect x={x + 3} y={yW} width={w - 6} height={Math.max(1, b - yW)} fill={wl > 80 ? '#e2483c' : wl < 20 ? '#e8b93a' : '#2f6feb'} opacity={0.7} />
          <line x1={x - 10} y1={yW} x2={x + w + 10} y2={yW} stroke="#4fc3f7" strokeWidth={1.5} strokeDasharray="6 4" />
          <Tx x={x + w + 14} y={yW - 4} s="раздел фаз" size={8} fill="#4fc3f7" anchor="start" />
          <Txt x={x + w / 2} y={y + h + 16} s={e.n || ''} size={11} fill="var(--mn-text)" maxW={w + 8} />
          {e.s ? <Txt x={x + w / 2} y={y - 8} up s={e.s} size={9} fill="var(--mn-text-dim)" maxW={w + 30} /> : null}
        </g>
      );
    }

    case 'note': {
      const lines = (e.n || '').split('|');
      const ww = e.w || 270;
      return (
        <g>
          <rect x={x} y={y} width={ww} height={15 + lines.length * 13} rx={3} style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-line)' }} />
          {lines.map((l, i) => (
            <Tx key={i} x={x + 8} y={y + 18 + i * 13} s={l} size={9} fill={i ? 'var(--mn-text-dim)' : 'var(--mn-text)'} anchor="start" />
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
          style={ST}
        />,
      );
      if (e.t === 'sett') {
        el.push(
          <line key="phase" x1={x + 4} y1={y + h * 0.62} x2={x + w - 4} y2={y + h * 0.62} stroke="#2f6feb" strokeWidth={1.3} strokeDasharray="5 3" />,
        );
      }
      if (e.t === 'ed') {
        el.push(
          <line key="e1" x1={x + 16} y1={y + h * 0.3} x2={x + w - 16} y2={y + h * 0.3} style={{ stroke: 'var(--mn-amber)', strokeWidth: 2 }} />,
          <line key="e2" x1={x + 16} y1={y + h * 0.5} x2={x + w - 16} y2={y + h * 0.5} style={{ stroke: 'var(--mn-amber)', strokeWidth: 2 }} />,
          <path
            key="hv"
            className="mn-hv"
            opacity={live.edVolt ? 1 : 0.15}
            d={`M${x + w / 2 - 6} ${y - 14} l6 8 l-4 1 l6 8`}
            fill="none"
            style={{ stroke: 'var(--mn-amber)', strokeWidth: 1.6 }}
          />,
        );
      }
      if (e.lv) {
        el.push(<LvlRect key="lv" x={x + 3} w={w - 6} y0={y} hh={h} v={live.lvl(e.lv)} opacity={0.55} />);
      }
      el.push(
        <Txt key="n" x={x + w / 2} y={y + h + 16} s={e.n || ''} size={11} fill="var(--mn-text)" maxW={w - 4} />,
      );
      if (e.s) {
        el.push(
          <Txt key="s" x={x + w / 2} y={y - (e.t === 'ed' ? 22 : 8)} up s={e.s} size={9} fill="var(--mn-text-dim)" maxW={w - 4} />,
        );
      }
      return <g>{el}</g>;
    }

    case 'mix':
      return (
        <g>
          <circle cx={x} cy={y} r={13} style={ST} />
          <path d={`M${x - 8} ${y - 8} L${x + 8} ${y + 8} M${x - 8} ${y + 8} L${x + 8} ${y - 8}`} style={{ stroke: 'var(--mn-stroke)', strokeWidth: 1.4 }} />
          <Txt x={x} y={y + 27} s={e.n || ''} size={9} fill="var(--mn-text-dim)" maxW={40} />
        </g>
      );

    case 'hx':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx={h / 2} style={ST} />
          <line x1={x + 8} y1={y + h / 2} x2={x + w - 8} y2={y + h / 2} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.6 }} />
          <line x1={x + 10} y1={y + 4} x2={x + 10} y2={y + h - 4} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.3 }} />
          <line x1={x + w - 10} y1={y + 4} x2={x + w - 10} y2={y + h - 4} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.3 }} />
          <line x1={x + w * 0.34} y1={y} x2={x + w * 0.34} y2={y - 6} style={{ stroke: 'var(--mn-stroke)', strokeWidth: 1.4 }} />
          <line x1={x + w * 0.66} y1={y + h} x2={x + w * 0.66} y2={y + h + 6} style={{ stroke: 'var(--mn-stroke)', strokeWidth: 1.4 }} />
          <Txt x={x + w / 2} y={y + h + 16} s={e.n || ''} size={10} fill="var(--mn-text)" maxW={w} />
          {e.s ? (
            <Txt x={x + w / 2} y={y + h + 16 + labelLines(e.n, 10, w) * 11.8 + 7} s={e.s} size={8.5} fill="var(--mn-text-dim)" maxW={w} />
          ) : null}
        </g>
      );

    case 'air': {
      const cx = x + w / 2;
      const cy = y + h + 14;
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx={2} style={ST} />
          <line x1={x + 5} y1={y + h / 2} x2={x + w - 5} y2={y + h / 2} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.4 }} />
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
          <Txt x={x + w / 2} y={y - 7} up s={e.n || ''} size={9.5} fill="var(--mn-text-dim)" maxW={w} />
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
          <rect x={x} y={y} width={w} height={h} rx={3} style={{ fill: 'var(--mn-fill)', stroke: '#96604c', strokeWidth: 1.6 }} />
          <rect x={x + w / 2 - 7} y={y - 16} width={14} height={16} style={{ fill: 'var(--mn-fill)', stroke: '#96604c', strokeWidth: 1.4 }} />
          <path d={d} fill="none" stroke="#c9866a" strokeWidth={1.3} opacity={0.75} />
          <rect
            className={live.fireOn ? 'mn-fire on' : 'mn-fire'}
            x={x + 6}
            y={y + h - 14}
            width={w - 12}
            height={9}
            fill="#e05252"
          />
          <Txt x={x + w / 2} y={y + h + 16} s={e.n || ''} size={12} fill="var(--mn-text)" maxW={w} />
        </g>
      );
    }

    case 'pump': {
      const st = live.run(e.n || '');
      const col = st === 'fail' ? '#f87171' : st === 'run' ? '#35d399' : '#3d5261';
      const run = st === 'run';
      const cx = x + 14;
      const cy = y + 14;
      return (
        <g className={st === 'fail' ? 'mn-alarm-flash' : undefined}>
          <circle
            cx={cx}
            cy={cy}
            r={13}
            style={{ fill: run ? 'rgba(53,211,153,0.16)' : 'var(--mn-fill-2)', stroke: col, strokeWidth: 1.8 }}
          />
          <path d={`M${cx - 5} ${cy - 7.5} L${cx + 8} ${cy} L${cx - 5} ${cy + 7.5} Z`} style={{ fill: run ? '#35d399' : col }} />
          <line x1={x + 2} y1={y + 30} x2={x + 26} y2={y + 30} style={{ stroke: 'var(--mn-line-2)', strokeWidth: 2 }} />
          <Txt x={cx} y={y + 40} s={e.n || ''} size={10} fill="var(--mn-text-2)" maxW={44} />
          {e.s ? (
            <Txt
              x={cx}
              y={y + 40 + labelLines(e.n, 10, 44) * 11.8 + 7}
              s={e.s}
              size={8.5}
              fill="var(--mn-text-dim-2)"
              maxW={44}
            />
          ) : null}
        </g>
      );
    }

    case 'valve': {
      const rot = e.r ? `rotate(${e.r} ${x} ${y})` : undefined;
      const c = e.ctrl ? live.ctrl(e.ctrl) : undefined;
      const open = e.vt === 'check';
      const body: ReactElement[] = [
        <path
          key="l"
          d={`M${x - 12} ${y - 9} L${x} ${y} L${x - 12} ${y + 9} Z`}
          style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-line-3)', strokeWidth: 1.5 }}
        />,
        <path
          key="r"
          d={`M${x + 12} ${y - 9} L${x} ${y} L${x + 12} ${y + 9} Z`}
          style={{ fill: open ? 'var(--mn-line-3)' : 'var(--mn-fill)', stroke: 'var(--mn-line-3)', strokeWidth: 1.5 }}
        />,
      ];
      if (e.vt === 'cv') {
        body.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 18} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.5 }} />,
          <path key="cap" d={`M${x - 11} ${y - 18} A11 8 0 0 1 ${x + 11} ${y - 18} Z`} style={{ fill: 'var(--mn-fill-3)', stroke: 'var(--mn-accent)', strokeWidth: 1.5 }} />,
          <rect key="flow" x={x - 11} y={y - 19.5} width={c ? 22 * c.out / 100 : 0} height={3.4} style={{ fill: 'var(--mn-accent)' }} />,
        );
      } else if (e.vt === 'psv') {
        body.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 15} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.5 }} />,
          <path key="cap" d={`M${x - 5} ${y - 15} l10 -3 l-10 -3 l10 -3`} fill="none" style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.4 }} />,
        );
      } else {
        body.push(
          <line key="stem" x1={x} y1={y} x2={x} y2={y - 14} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 1.5 }} />,
          <line key="cap" x1={x - 9} y1={y - 14} x2={x + 9} y2={y - 14} style={{ stroke: 'var(--mn-line-3)', strokeWidth: 2.4 }} />,
        );
      }
      return (
        <g>
          <g transform={rot}>{body}</g>
          {e.st ? <Tx x={x} y={y + 24} s={e.st} size={9} fill="var(--mn-amber)" /> : null}
          {c ? (
            <text
              x={x}
              y={y + 25}
              textAnchor="middle"
              fontSize={9.5}
              fontFamily="Consolas"
              style={{ fill: 'var(--mn-accent)' }}
              pointerEvents="none"
            >
              {c.out.toFixed(0)} %
            </text>
          ) : null}
          {e.n ? (
            <Txt x={x} y={e.st || c ? y + 36 : y + 24} s={e.n} size={8} fill="var(--mn-text-dim)" maxW={44} />
          ) : null}
        </g>
      );
    }

    case 'ins': {
      const tag = e.ctrl || e.tag || '';
      const c = e.ctrl ? live.ctrl(e.ctrl) : undefined;
      const ww = e.w || 72;
      const hh = 24;
      const col = c ? 'var(--mn-accent)' : 'var(--mn-line-2)';
      let v: number | null = null;
      if (e.ctrl) v = c ? c.pv : null;
      else if (e.src) v = live.sval(e.src);
      const vStr = fmtVal(v);
      const ivFill =
        v != null && e.hi != null && v >= e.hi
          ? '#f87171'
          : v != null && e.hi != null && v >= e.hi * 0.9
            ? '#fbbf24'
            : c && c.mode === 'РУЧ'
              ? 'var(--mn-amber)'
              : 'var(--mn-text)';
      const inAlarm = v != null && e.hi != null && v >= e.hi;
      return (
        <g>
          <rect x={x} y={y} width={ww} height={hh} rx={2} style={{ fill: c ? 'var(--mn-fill-3)' : 'var(--mn-fill-2)', stroke: col, strokeWidth: 1.1 }} />
          <Tx x={x + 4} y={y + 9.5} s={tag} size={8} fill={c ? 'var(--mn-accent)' : 'var(--mn-text-dim)'} anchor="start" />
          {e.u ? <Tx x={x + 4} y={y + 20} s={e.u} size={7.5} fill="var(--mn-text-dim-2)" anchor="start" /> : null}
          <text
            x={x + ww - 4}
            y={y + 20}
            textAnchor="end"
            fontSize={11.5}
            fontFamily="Consolas"
            style={{ fill: ivFill }}
            className={inAlarm ? 'mn-alarm-flash' : undefined}
            pointerEvents="none"
          >
            {vStr}
          </text>
        </g>
      );
    }

    case 'ovpump': {
      const w = e.w || 70;
      const h = e.h || 70;
      const cx = x + w / 2;
      const cy = y + h / 2;
      const st = live.run(e.n || '');
      const col = st === 'fail' ? '#f87171' : st === 'run' ? '#36d36a' : '#7d97a8';
      return (
        <g className={st === 'fail' ? 'mn-alarm-flash' : undefined}>
          <circle cx={cx} cy={cy} r={w / 2 - 4} style={{ fill: st === 'run' ? 'rgba(54,211,106,0.12)' : 'var(--mn-fill)', stroke: col, strokeWidth: 3 }} />
          <path d={`M${x + w - 2} ${cy} L${x + w + 18} ${cy - 7} L${x + w + 18} ${cy + 7} Z`} fill={col} />
          <Txt x={cx} y={y + h + 16} s={e.n || ''} size={12} fill="var(--mn-text-2)" maxW={w} />
        </g>
      );
    }

    case 'ovhex': {
      const w = e.w || 80;
      const h = e.h || 80;
      const cx = x + w / 2;
      const cy = y + h / 2;
      return (
        <g>
          <polygon points={`${cx},${y} ${x + w},${cy} ${cx},${y + h} ${x},${cy}`} style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-line-3)', strokeWidth: 3, strokeLinejoin: 'round' }} />
          <Tx x={cx} y={cy + 6} s="≈" size={30} fill="var(--mn-text-2)" />
          <Txt x={cx} y={y + h + 16} s={e.n || ''} size={12} fill="var(--mn-text-2)" maxW={w} />
        </g>
      );
    }

    case 'ovfur': {
      const w = e.w || 90;
      const h = e.h || 120;
      const cx = x + w / 2;
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-line-3)', strokeWidth: 3 }} />
          <text x={cx} y={y + h / 2 + 8} textAnchor="middle" fontSize={26} pointerEvents="none">🔥</text>
          <Txt x={cx} y={y + h + 16} s={e.n || ''} size={12} fill="var(--mn-text-2)" maxW={w} />
        </g>
      );
    }

    case 'ovtag': {
      const w = e.w || 105;
      const h = 40;
      const tag = e.tag || e.ctrl || '';
      const v = e.ctrl ? (live.ctrl(e.ctrl)?.pv ?? null) : e.src ? live.sval(e.src) : null;
      const sc = e.sc && v != null ? v * e.sc : v;
      const vStr = v == null ? '--' : fmtVal(sc) + (e.u || '');
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-line-2)', strokeWidth: 1.4 }} />
          <Txt x={x + w / 2} y={y + 15} s={tag} size={12} fill="var(--mn-text)" maxW={w - 8} />
          <text x={x + w / 2} y={y + 31} textAnchor="middle" fontSize={12} fontFamily="Consolas" style={{ fill: 'var(--mn-accent)' }} pointerEvents="none">
            {vStr}
          </text>
        </g>
      );
    }

    case 'box': {
      const col = e.fl ? live.flowColor(e.fl) : 'var(--mn-line-2)';
      const inner: ReactElement[] = [
        <rect key="b" x={x} y={y} width={w} height={h} rx={2} style={{ fill: 'var(--mn-fill)', stroke: col, strokeWidth: 1.4 }} />,
        <Txt key="n" x={x + w / 2} y={y + (e.s ? 16 : h / 2 + 4)} s={e.n || ''} size={10} fill="var(--mn-text)" maxW={w - 8} />,
      ];
      if (e.s) {
        inner.push(
          <Txt key="s" x={x + w / 2} y={y + 16 + labelLines(e.n, 10, w - 8) * 11.8 + 7} s={e.s} size={8.6} fill="var(--mn-text-dim)" maxW={w - 8} />,
        );
      }
      return <g>{inner}</g>;
    }

    case 'text':
      return <Tx x={x} y={y} s={e.n || ''} size={e.fs || 9.5} fill={e.fc || 'var(--mn-text-dim)'} anchor="start" />;

    default:
      return <g />;
  }
}

export function itemBBox(e: MnemoItem): [number, number, number, number] {
  if (e.t === 'pump') {
    const nL = labelLines(e.n, 10, 44);
    const sL = labelLines(e.s, 8.5, 44);
    const bot = 40 + nL * 11.8 + (sL ? 7 + sL * 10.03 : 0) + 4;
    return [e.x - 2, e.y - 4, 32, Math.max(60, 4 + bot)];
  }
  if (e.t === 'valve') {
    const hasLbl = !!e.st || !!e.ctrl;
    const nY = hasLbl ? 36 : 24;
    const nL = labelLines(e.n, 8, 44);
    const bot = nY + nL * 9.44 + 4;
    return [e.x - 16, e.y - 22, 32, Math.max(64, 22 + bot)];
  }
  if (e.t === 'ovpump') {
    const w = e.w || 70;
    const h = e.h || 70;
    const nL = labelLines(e.n, 12, w);
    return [e.x - 4, e.y - 4, w + 26, h + 24 + nL * 14.16];
  }
  if (e.t === 'ovhex') {
    const w = e.w || 80;
    const h = e.h || 80;
    const nL = labelLines(e.n, 12, w);
    return [e.x - 4, e.y - 4, w + 8, h + 24 + nL * 14.16];
  }
  if (e.t === 'ovfur') {
    const w = e.w || 90;
    const h = e.h || 120;
    const nL = labelLines(e.n, 12, w);
    return [e.x - 4, e.y - 4, w + 8, h + 24 + nL * 14.16];
  }
  if (e.t === 'ovtag') return [e.x - 2, e.y - 2, (e.w || 105) + 4, 44];
  if (e.t === 'mix') {
    const nL = labelLines(e.n, 9, 40);
    return [e.x - 15, e.y - 15, 30, 15 + 27 + nL * 10.62 + 4];
  }
  if (e.t === 'hx') {
    const nL = labelLines(e.n, 10, e.w || 60);
    const sL = labelLines(e.s, 8.5, e.w || 60);
    const bot = 16 + nL * 11.8 + (sL ? 7 + sL * 10.03 : 0) + 4;
    return [e.x - 3, e.y - 14, (e.w || 60) + 6, 14 + bot];
  }
  if (e.t === 'col') {
    const w = e.w || 60;
    const nL = labelLines(e.n, 11, w + 8);
    const sL = labelLines(e.s, 9.5, w + 30);
    const top = 10 + (sL ? (sL - 1) * 11.21 : 0);
    const bot = (e.h || 30) + 16 + nL * 12.98 + 4;
    return [e.x - 3, e.y - top, w + 6, top + bot];
  }
  if (e.t === 'vves') {
    const w = e.w || 60;
    const nL = labelLines(e.n, 11, w + 8);
    const sL = labelLines(e.s, 9, w + 30);
    const top = 8 + (sL ? (sL - 1) * 10.62 : 0);
    const bot = (e.h || 30) + 16 + nL * 12.98 + 4;
    return [e.x - 3, e.y - top, w + 6, top + bot];
  }
  if (e.t === 'ves' || e.t === 'sett' || e.t === 'ed') {
    const w = e.w || 60;
    const nL = labelLines(e.n, 11, w - 4);
    const sL = labelLines(e.s, 9, w - 4);
    const tp = e.t === 'ed' ? 22 : 8;
    const top = tp + (sL ? (sL - 1) * 10.62 : 0);
    const bot = 16 + nL * 12.98 + 4;
    return [e.x - 3, e.y - top, w + 6, top + bot];
  }
  if (e.t === 'fur') {
    const w = e.w || 60;
    const nL = labelLines(e.n, 12, w);
    return [e.x - 4, e.y - 20, w + 8, 20 + (e.h || 30) + 16 + nL * 14.16 + 4];
  }
  if (e.t === 'air') {
    const w = e.w || 60;
    const nL = labelLines(e.n, 9.5, w);
    const top = 7 + (nL ? (nL - 1) * 11.21 : 0);
    return [e.x - 3, e.y - top, w + 6, top + (e.h || 30) + 28];
  }
  if (e.t === 'box') {
    const w = e.w || 60;
    const h = e.h || 30;
    const nL = labelLines(e.n, 10, w - 8);
    const sL = labelLines(e.s, 8.6, w - 8);
    const bot = e.s ? 16 + nL * 11.8 + 7 + sL * 10.15 : h / 2 + 4 + nL * 11.8;
    return [e.x - 3, e.y - 3, w + 6, Math.max(h + 6, bot + 6)];
  }
  if (e.t === 'ins') return [e.x - 2, e.y - 2, (e.w || 72) + 4, 28];
  if (e.t === 'text') return [e.x - 2, e.y - 11, 200, 15];
  if (e.t === 'note') return [e.x - 2, e.y - 2, (e.w || 270) + 4, 19 + String(e.n || '').split('|').length * 13];
  return [e.x - 3, e.y - 14, (e.w || 60) + 6, (e.h || 30) + 28];
}
