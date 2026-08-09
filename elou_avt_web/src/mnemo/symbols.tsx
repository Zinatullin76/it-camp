import type { CSSProperties, ReactElement } from 'react';
import type { MnemoItem, MnemoColDetail, MnemoFurDetail } from './mnemoTypes';
import type { MnemoLive, ValveState } from './sources';
import { fmtVal, pumpVisual, PUMP_COLORS } from './sources';

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

/* ---- Горизонтальная ёмкость / сепаратор ----
   Цвета — приказ № 251-П, приложение № 1, табл. 12–13
   (эталон визуала: visual/separator/hmi-vessel.html). */
const VES_GAS = '#d7d7d7';    // газовая подушка / корпус (--c-normal)
const VES_OIL = '#000000';    // нефть и нефтепродукты (--c-med-oil)
const VES_WATER = '#5b9bd4';  // неопасные жидкости (--c-blue)
const VES_STROKE = '#000000'; // контур оборудования
const VES_FRAME: Record<string, string> = {
  normal: '#000000',
  warning: '#ffff00',
  alarm: '#ff0000',
  fault: '#ff0000',
};
/** Мигание рамки шкалы уровня до квитирования: 1 Гц, цвет состояния ↔ чёрный. */
const VES_BLINK: Record<string, string> = {
  warning: 'vves-blink-warning',
  alarm: 'vves-blink-alarm',
  fault: 'vves-blink-alarm',
};
/** Полоса воды снизу во «флегме» (доля высоты шкалы). */
const VES_WATER_BAND = 0.25;

/* ---- Детализированная колонна (пресеты К-1..К-4) --------------------------
   УГО по эталонам visual/Колонны: корпус с заливкой, тарелки «N тар.»,
   штуцеры с фланцами, уровень в кубе, экспликация с выносками, ППК. */

const PPK_ATMOS_D = [
  'M 0,0 V -51',
  'M 70,-83 V -165 a 22,22 0 0 0 -44,0 v 36',
  'M 46,-83 h 24',
  'M 0,-83 -20,-49 H 20 Z',
  'M 0,-83 46,-22 v 44 z',
  'M 0,-83 -18,-93 -6,-99 -20,-107',
];

const PPK_FLARE_D = [
  'M 0,0 V -51',
  'M 46,-83 h 64',
  'M 0,-83 -20,-49 H 20 Z',
  'M 0,-83 46,-22 v 44 z',
  'M 0,-83 -18,-93 -6,-99 -20,-107',
];

const PPK_D: Record<string, string[]> = { atmos: PPK_ATMOS_D, flare: PPK_FLARE_D };

function colShellD(shell: string | string[]): string {
  return Array.isArray(shell) ? shell.join(' ') : shell;
}

/** Оценочная ширина текста (px) в шрифте Arial. */
function roughTextW(s: string, size: number): number {
  let w = 0;
  for (const c of s) w += chW(c, size);
  return w;
}

/** Точки стрелки направления потока на прямом штуцере (nozzle). */
function nozzleArrow(a: { x: number; y: number }, b: { x: number; y: number }, dir: 'in' | 'out'): string {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = (dir === 'out' ? dx : -dx) / len;
  const uy = (dir === 'out' ? dy : -dy) / len;
  const tip = dir === 'out'
    ? { x: b.x, y: b.y }
    : { x: a.x - ux * 9, y: a.y - uy * 9 };
  const back = { x: tip.x - ux * 6, y: tip.y - uy * 6 };
  const px = -uy * 3.5;
  const py = ux * 3.5;
  return `${tip.x} ${tip.y} ${back.x + px} ${back.y + py} ${back.x - px} ${back.y - py}`;
}

/** Габариты детального символа: viewBox + вылеты ППК и экспликации. */
export function colDetailBounds(d: MnemoColDetail): [number, number, number, number] {
  let x0 = 0;
  let y0 = 0;
  let x1 = d.vb.w;
  let y1 = d.vb.h;
  const grow = (a: number, b: number, c: number, dd: number) => {
    x0 = Math.min(x0, a);
    y0 = Math.min(y0, b);
    x1 = Math.max(x1, c);
    y1 = Math.max(y1, dd);
  };
  for (const pk of d.ppk ?? []) {
    const s = pk.scale ?? 0.5;
    const hx = pk.kind === 'flare' ? 110 : 70;
    const bot = pk.kind === 'flare' ? -83 : 0;
    grow(pk.x - 20 * s, pk.y - 165 * s, pk.x + hx * s, pk.y + bot * s);
  }
  for (const ex of d.expl ?? []) {
    let wMax = 0;
    for (const ln of ex.lines) wMax = Math.max(wMax, roughTextW(ln.s, ln.sub ? 10 : 12));
    const left = ex.anchor === 'end' ? ex.x - wMax : ex.anchor === 'middle' ? ex.x - wMax / 2 : ex.x;
    const right = ex.anchor === 'start' ? ex.x + wMax : ex.anchor === 'middle' ? ex.x + wMax / 2 : ex.x;
    grow(left, ex.y - 12, right, ex.y + ex.lines.length * 12 + 2);
  }
  return [x0, y0, x1 - x0, y1 - y0];
}

function renderColDetail(e: MnemoItem, live: MnemoLive): ReactElement {
  const d = e.detail as MnemoColDetail;
  const x = e.x;
  const y = e.y;
  const nodeW = e.w || d.nodeW || 130;
  const s = nodeW / d.vb.w;
  const [dx, dy, dw, dh] = colDetailBounds(d);
  const labelX = x + dx * s + (dw * s) / 2;
  const labelY = y + dy * s + dh * s + 16;
  const el: ReactElement[] = [];
  const clips: ReactElement[] = [];
  let si = 0;
  for (const sec of d.sections) {
    const secIdx = si++;
    const shellD = colShellD(sec.shell ?? '');
    el.push(
      <path
        key={`sh${secIdx}`}
        d={shellD}
        fill={sec.fill ?? '#d9d9d9'}
        stroke="#000"
        strokeWidth={sec.fill === 'none' ? 2 : 2.5}
        strokeLinejoin="miter"
      />,
    );
    if (sec.level) {
      const v = Math.max(0, Math.min(100, live.lvl(sec.level.lv)));
      const hh = sec.level.y0 - sec.level.y100;
      const top = sec.level.y0 - (hh * v) / 100;
      const cid = `col-clip-${nodeW}-${secIdx}`;
      clips.push(
        <clipPath key={cid} id={cid}>
          <path d={shellD} />
        </clipPath>,
      );
      el.push(
        <g key={`lv${secIdx}`} clipPath={`url(#${cid})`}>
          <rect
            x={(sec.leftX ?? 0) - 5}
            y={top}
            width={(sec.rightX ?? 0) - (sec.leftX ?? 0) + 10}
            height={sec.level.y0 - top}
            fill={sec.level.color ?? '#8b5e3c'}
          />
        </g>,
      );
    }
    let ti = 0;
    for (const t of sec.trays ?? []) {
      const k = `t${secIdx}-${ti++}`;
      el.push(
        <line key={k} x1={sec.leftX ?? 0} y1={t.y} x2={sec.rightX ?? 0} y2={t.y} stroke="#000" strokeWidth={t.blind ? 3 : 1.5} />,
      );
      if (t.label) {
        el.push(<Tx key={`${k}l`} x={(sec.leftX ?? 0) + 8} y={t.y - 4} s={t.label} size={11} fill="#000" anchor="start" />);
      }
    }
    if (sec.tag) {
      el.push(
        <text
          key={`tag${secIdx}`}
          x={sec.tag.x}
          y={sec.tag.y}
          textAnchor={sec.tag.anchor ?? 'middle'}
          fontSize={sec.tag.size ?? 26}
          fontFamily="Arial, sans-serif"
          style={{ fill: '#000' }}
          pointerEvents="none"
        >
          {sec.tag.s}
        </text>,
      );
      if (sec.tag.line) {
        el.push(
          <line key={`tagl${secIdx}`} x1={sec.tag.x} y1={sec.tag.y + 5} x2={sec.tag.line.x2} y2={sec.tag.line.y2} stroke="#000" strokeWidth={1} />,
        );
      }
    }
    let ni = 0;
    for (const nz of sec.nozzles ?? []) {
      const k = `nz${secIdx}-${ni++}`;
      const w = nz.width ?? 2.5;
      if (nz.pts) {
        const dd = nz.pts.map((p, pi) => `${pi ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ');
        el.push(<path key={k} d={dd} fill="none" stroke="#000" strokeWidth={w} strokeLinecap="butt" />);
        if (nz.dir && nz.pts.length >= 2) {
          const last = nz.pts[nz.pts.length - 1];
          const prev = nz.pts[nz.pts.length - 2];
          el.push(
            <polygon key={`${k}a`} points={nozzleArrow({ x: prev[0], y: prev[1] }, { x: last[0], y: last[1] }, nz.dir)} fill="#000" />,
          );
        }
      } else if (nz.from && nz.to) {
        el.push(
          <line key={k} x1={nz.from.x} y1={nz.from.y} x2={nz.to.x} y2={nz.to.y} stroke="#000" strokeWidth={w} strokeLinecap="butt" />,
        );
        if (nz.flange) {
          const horiz = Math.abs(nz.from.y - nz.to.y) < Math.abs(nz.from.x - nz.to.x);
          el.push(
            horiz ? (
              <line key={`${k}f`} x1={nz.to.x} y1={nz.to.y - 6} x2={nz.to.x} y2={nz.to.y + 6} stroke="#000" strokeWidth={3} />
            ) : (
              <line key={`${k}f`} x1={nz.to.x - 6} y1={nz.to.y} x2={nz.to.x + 6} y2={nz.to.y} stroke="#000" strokeWidth={3} />
            ),
          );
        }
        if (nz.dir) {
          el.push(
            <polygon key={`${k}a`} points={nozzleArrow(nz.from, nz.to, nz.dir)} fill="#000" />,
          );
        }
      }
    }
  }
  let si2 = 0;
  for (const sh of d.shell ?? []) {
    el.push(<path key={`dsh${si2++}`} d={sh} fill="none" stroke="#1a1a1a" strokeWidth={2} />);
  }
  let ei = 0;
  for (const ex of d.expl ?? []) {
    const eid = ei++;
    if (ex.lead) {
      el.push(
        <line key={`lead${eid}`} x1={ex.lead[0]} y1={ex.lead[1]} x2={ex.lead[2]} y2={ex.lead[3]} stroke="#000" strokeWidth={0.75} />,
      );
    }
    ex.lines.forEach((ln, li) => {
      el.push(
        <text
          key={`ex${eid}-${li}`}
          x={ex.x}
          y={ex.y + li * 12}
          textAnchor={ex.anchor ?? 'start'}
          fontSize={ln.sub ? 10 : 12}
          fontFamily="Arial, sans-serif"
          style={{ fill: ln.sub ? '#404040' : '#000' }}
          pointerEvents="none"
        >
          {ln.s}
        </text>,
      );
    });
  }
  let pi = 0;
  for (const pk of d.ppk ?? []) {
    const s = pk.scale ?? 0.5;
    const paths = PPK_D[pk.kind ?? 'atmos'];
    el.push(
      <g key={`ppk${pi++}`} transform={`translate(${pk.x},${pk.y}) scale(${s})`}>
        {paths.map((pd, pdi) => (
          <path
            key={pdi}
            d={pd}
            fill={pdi >= 3 && pdi < 5 ? '#d7d7d7' : 'none'}
            stroke="#000"
            strokeWidth={pdi >= 5 ? 2 : 2.5}
            strokeLinejoin="miter"
            strokeLinecap="butt"
          />
        ))}
      </g>,
    );
  }
  return (
    <g transform={`translate(${x},${y})`}>
      <g transform={`scale(${s})`}>
        {clips}
        {el}
      </g>
      <Txt x={labelX - x} y={labelY - y} s={e.n || ''} size={11} fill="var(--mn-text)" maxW={nodeW + 8} />
      {e.s ? <Txt x={labelX - x} y={dy * s - 10} up s={e.s} size={9.5} fill="var(--mn-text-dim)" maxW={nodeW + 30} /> : null}
    </g>
  );
}

/** Габариты детального символа печи: полотно vb + запас под линии потоков. */
export function furDetailBounds(d: MnemoFurDetail): [number, number, number, number] {
  let x0 = 0;
  let y0 = 0;
  let x1 = d.vb.w;
  let y1 = d.vb.h;
  for (const f of d.flows ?? []) {
    if (f.from) {
      x0 = Math.min(x0, f.from.x);
      y0 = Math.min(y0, f.from.y);
      x1 = Math.max(x1, f.from.x);
      y1 = Math.max(y1, f.from.y);
    }
    if (f.to) {
      x0 = Math.min(x0, f.to.x);
      y0 = Math.min(y0, f.to.y);
      x1 = Math.max(x1, f.to.x);
      y1 = Math.max(y1, f.to.y);
    }
  }
  return [x0, y0, x1 - x0, y1 - y0];
}

function renderFurDetail(e: MnemoItem, live: MnemoLive): ReactElement {
  const d = e.detail as MnemoFurDetail;
  const x = e.x;
  const y = e.y;
  const nodeW = e.w || d.nodeW || 200;
  const s = nodeW / d.vb.w;
  const [dx, dy, dw, dh] = furDetailBounds(d);
  const labelX = x + dx * s + (dw * s) / 2;
  const labelY = y + dy * s + dh * s + 16;
  const el: ReactElement[] = [];
  const push = (el2: ReactElement) => el.push(el2);
  const BODY = '#D7D7D7';

  // Линии потоков (рисуются до корпуса).
  for (const f of d.flows ?? []) {
    if (!f.from || !f.to) continue;
    push(<line key={`fl${el.length}`} x1={f.from.x} y1={f.from.y} x2={f.to.x} y2={f.to.y} stroke="#000" strokeWidth={2} />);
    push(<polygon key={`fla${el.length}`} points={nozzleArrow(f.from, f.to, f.dir ?? 'in')} fill="#000" />);
    if (f.label) {
      const isIn = f.dir === 'in';
      const tx = isIn ? f.from.x - 4 : f.from.x + 4;
      push(
        <text
          key={`fll${el.length}`}
          x={tx}
          y={f.from.y - 5}
          textAnchor={isIn ? 'end' : 'start'}
          fontSize={11}
          fontWeight="bold"
          fontFamily="Arial, sans-serif"
          style={{ fill: '#000' }}
          pointerEvents="none"
        >
          {f.label}
        </text>,
      );
    }
  }

  // Дымовая труба.
  for (const st of d.stack ?? []) {
    push(<rect key={`st${el.length}`} x={st.x} y={st.y} width={st.w} height={st.h} fill={BODY} stroke="#000" strokeWidth={1.5} />);
  }
  // Приборы на трубе (П-1 — QR 5001).
  for (const it of d.inst ?? []) {
    push(<line key={`il${el.length}`} x1={it.lead[0]} y1={it.lead[1]} x2={it.lead[2]} y2={it.lead[3]} stroke="#000" strokeWidth={1.2} />);
    push(<circle key={`ic${el.length}`} cx={it.cx} cy={it.cy} r={18} fill="#FFFFFF" stroke="#000" strokeWidth={1.5} />);
    push(<text key={`it0${el.length}`} x={it.cx} y={it.cy - 1} textAnchor="middle" fontSize={9} fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{it.lines[0]}</text>);
    push(<text key={`it1${el.length}`} x={it.cx} y={it.cy + 10} textAnchor="middle" fontSize={9} fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{it.lines[1]}</text>);
  }
  // Конвекционная камера.
  if (d.conv) {
    push(<rect key={`cv${el.length}`} x={d.conv.x} y={d.conv.y} width={d.conv.w} height={d.conv.h} fill={BODY} stroke="#000" strokeWidth={2} />);
  }
  // Камеры пароперегревателей.
  for (const p of d.pp ?? []) {
    push(<rect key={`pp${el.length}`} x={p.x} y={p.y} width={p.w} height={p.h} fill={BODY} stroke="#000" strokeWidth={1.5} />);
    if (p.s) {
      push(<text key={`pps${el.length}`} x={p.x + p.w / 2} y={p.y + p.h - 4.5} textAnchor="middle" fontSize={10} fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{p.s}</text>);
    }
  }
  // Свод (перевал).
  push(<path key={`ar${el.length}`} d={d.arch} fill={BODY} stroke="#000" strokeWidth={2} />);
  // Радиантная камера.
  push(<rect key={`rd${el.length}`} x={d.rad.x} y={d.rad.y} width={d.rad.w} height={d.rad.h} fill={BODY} stroke="#000" strokeWidth={2} />);
  // Вертикальные экраны-трубы (левый и правый ряды).
  for (const cx of [76, 284]) {
    for (let cy = 196; cy <= 261; cy += 13) {
      push(<circle key={`sc${cx}-${cy}`} cx={cx} cy={cy} r={4.5} fill={BODY} stroke="#000" strokeWidth={1} />);
    }
  }
  // Потолочный экран (П-3 — ПЭ).
  if (d.ceil) {
    for (const cx of d.ceil.xs) {
      push(<circle key={`ce${cx}`} cx={cx} cy={d.ceil.y} r={4.5} fill={BODY} stroke="#000" strokeWidth={1} />);
    }
    if (d.ceil.label) {
      push(<text key={`cel${el.length}`} x={d.ceil.label.x} y={d.ceil.label.y} textAnchor="start" fontSize={10} fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{d.ceil.label.s}</text>);
    }
  }
  // Обозначение печи на корпусе.
  push(<text key={`tg${el.length}`} x={d.tag.x} y={d.tag.y} textAnchor="middle" fontSize={d.tag.size ?? 26} fontWeight="bold" fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{d.tag.s}</text>);
  // Дополнительные надписи (КОНВ.).
  for (const cap of d.caps ?? []) {
    push(<text key={`cp${el.length}`} x={cap.x} y={cap.y} textAnchor={cap.anchor ?? 'start'} fontSize={cap.size ?? 10} fontFamily="Arial, sans-serif" style={{ fill: '#000' }} pointerEvents="none">{cap.s}</text>);
  }
  // Под и опоры.
  if (d.base) {
    push(<rect key={`fl${el.length}`} x={d.base.floor.x} y={d.base.floor.y} width={d.base.floor.w} height={d.base.floor.h} fill={BODY} stroke="#000" strokeWidth={2} />);
    for (const leg of d.base.legs) {
      push(<rect key={`lg${el.length}`} x={leg.x} y={leg.y} width={leg.w} height={leg.h} fill={BODY} stroke="#000" strokeWidth={1.5} />);
    }
  }
  // Форсунки с пламенем (6 шт, одинаковы для всех УГО).
  const fire = live.fireOn;
  for (const bx of [95, 127, 159, 191, 223, 255]) {
    push(<rect key={`br${bx}`} x={bx} y={280} width={10} height={14} fill={BODY} stroke="#000" strokeWidth={1.5} />);
    push(
      <g key={`flm${bx}`} transform={`translate(${bx - 5},248)`}>
        <path d="M10,0 C13,6 18,10 18,18 C18,25 14,30 10,30 C6,30 2,25 2,18 C2,13 5,11 6,7 C7,10 9,11 10,12 C11,8 10,4 10,0 Z" fill={fire ? '#FF7A00' : '#BEBEBE'} stroke="#000" strokeWidth={1} />
        <path d="M10,13 C12,16 14,18 14,21 C14,25 12,27.5 10,27.5 C8,27.5 6,25 6,21 C6,18 8,16 10,13 Z" fill={fire ? '#FFFF00' : BODY} />
      </g>,
    );
  }
  // Коллекторы топлива.
  push(<line key={`fu1${el.length}`} x1={20} y1={322} x2={176} y2={322} stroke="#000" strokeWidth={2} />);
  push(<line key={`fu2${el.length}`} x1={184} y1={322} x2={340} y2={322} stroke="#000" strokeWidth={2} />);
  for (const bx of [100, 132, 164, 196, 228, 260]) {
    push(<line key={`fuv${bx}`} x1={bx} y1={294} x2={bx} y2={322} stroke="#000" strokeWidth={1.5} />);
  }

  return (
    <g transform={`translate(${x},${y})`}>
      <g transform={`scale(${s})`}>
        {el}
      </g>
      <Txt x={labelX - x} y={labelY - y} s={e.n || ''} size={11} fill="var(--mn-text)" maxW={nodeW + 8} />
      {e.s ? <Txt x={labelX - x} y={dy * s - 10} up s={e.s} size={9.5} fill="var(--mn-text-dim)" maxW={nodeW + 30} /> : null}
    </g>
  );
}

export function renderItem(e: MnemoItem, live: MnemoLive): ReactElement {
  const x = e.x;
  const y = e.y;
  const w = e.w || 60;
  const h = e.h || 30;

  switch (e.t) {
    case 'col': {
      if (e.detail) return renderColDetail(e, live);
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
      // УГО горизонтальной ёмкости (п. 7.4.8.2 «г», «д»): обечайка +
      // два эллиптических днища, пропорционально реальному аппарату.
      // Внутри — шкала уровня (п. 7.4.2.6): газовая подушка сверху,
      // нефтепродукт, вода снизу; рамка кодирует состояние параметра и
      // мигает до квитирования.
      const st = e.state || 'normal';
      const frame = VES_FRAME[st] || VES_FRAME.normal;
      const blink = e.unacked ? (VES_BLINK[st] || '') : '';
      const rx = Math.min((h * 0.44) / 2, w * 0.25); // радиус днища
      const ry = h / 2;
      const gx = x + w * 0.22;                       // посадочное место шкалы
      const gw = Math.max(8, w * 0.085);
      const gh = h * 0.62;
      const gy = y + (h - gh) / 2;
      const ins = 2;
      const tot = Math.max(0, Math.min(100, live.lvl(e.lv || '')));
      // Флегма: тёмная жидкость в середине, внизу вода, сверху пустота.
      // Вода: только вода снизу до уровня, сверху пустота.
      const isWater = e.lmode === 'water';
      const waterTop = isWater ? tot : Math.min(VES_WATER_BAND * 100, tot);
      const oilH = isWater ? 0 : (gh - ins * 2) * tot / 100;
      const watH = (gh - ins * 2) * waterTop / 100;
      const bot = gy + gh - ins;
      return (
        <g>
          <path
            d={`M${x + w - rx} ${y} A${rx} ${ry} 0 0 1 ${x + w - rx} ${y + h} L${x + rx} ${y + h} A${rx} ${ry} 0 0 1 ${x + rx} ${y} Z`}
            fill={VES_GAS}
            stroke={VES_STROKE}
            strokeWidth={1.6}
          />
          <g>
            <rect x={gx} y={gy} width={gw} height={gh} fill={VES_GAS} stroke={frame} strokeWidth={1.5} className={blink} />
            <rect x={gx + ins} y={bot - oilH} width={gw - ins * 2} height={oilH} fill={VES_OIL} />
            <rect x={gx + ins} y={bot - watH} width={gw - ins * 2} height={watH} fill={VES_WATER} />
          </g>
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
      // УГО смесителя (эталон: visual/smesitel.html): ромб на нефтепроводе
      // с двумя S-образными лопастями внутри.
      return (
        <g>
          <line x1={x - 70} y1={y} x2={x + 70} y2={y} style={{ stroke: 'var(--mn-stroke)', strokeWidth: 3 }} />
          <polygon
            points={`${x},${y - 40} ${x + 40},${y} ${x},${y + 40} ${x - 40},${y}`}
            style={{ fill: 'var(--mn-fill)', stroke: 'var(--mn-stroke)', strokeWidth: 2 }}
          />
          <path
            d={`M${x - 20} ${y - 17} C${x - 6} ${y - 17} ${x + 6} ${y + 17} ${x + 20} ${y + 17}`}
            fill="none"
            style={{ stroke: 'var(--mn-stroke)', strokeWidth: 2.5 }}
          />
          <path
            d={`M${x - 20} ${y + 17} C${x - 6} ${y + 17} ${x + 6} ${y - 17} ${x + 20} ${y - 17}`}
            fill="none"
            style={{ stroke: 'var(--mn-stroke)', strokeWidth: 2.5 }}
          />
          <Txt x={x} y={y + 56} s={e.n || ''} size={9} fill="var(--mn-text-dim)" maxW={40} />
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
      if (e.detail) return renderFurDetail(e, live);
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
      const vis = pumpVisual(st);
      const blink = vis.blink ? `pump-blink-${vis.blink}` : undefined;
      const px = x + 2;
      const py = y + 4;
      const nL = labelLines(e.n, 10, 96);
      const nY = py + 67;
      const sY = nY + nL * 11.8 + 7;
      const stroke = '#000';
      return (
        <g>
          <rect x={px + 48} y={py + 9} width={38.5} height={17} fill={PUMP_COLORS.gray} stroke={stroke} strokeWidth={4} />
          <rect x={px + 39} y={py + 45} width={29.5} height={8} fill={vis.volute} stroke={stroke} strokeWidth={4} className={blink} />
          <circle cx={px + 53} cy={py + 29.5} r={21} fill={vis.volute} stroke={stroke} strokeWidth={4} className={blink} />
          <rect x={px + 36.5} y={py + 52} width={35} height={4.5} fill={vis.volute} stroke={stroke} strokeWidth={4} className={blink} />
          <rect x={px + 11} y={py + 18} width={6.5} height={23} fill={PUMP_COLORS.gray} stroke={stroke} strokeWidth={4} />
          <rect x={px + 18.5} y={py + 23} width={31} height={14} fill={PUMP_COLORS.gray} stroke={stroke} strokeWidth={4} />
          <rect x={px + 87} y={py + 6} width={6.5} height={22.5} fill={PUMP_COLORS.gray} stroke={stroke} strokeWidth={4} />
          <circle cx={px + 53} cy={py + 29.5} r={12.5} fill={PUMP_COLORS.gray} stroke={stroke} strokeWidth={3} />
          <path
            d={`M${px + 48.5} ${py + 23} L${px + 48.5} ${py + 36} L${px + 60.5} ${py + 29.5} Z`}
            fill={vis.center}
            stroke={stroke}
            strokeWidth={2}
            className={blink}
          />
          <Txt x={px + 53} y={nY} s={e.n || ''} size={10} fill="var(--mn-text-2)" maxW={96} />
          {e.s ? (
            <Txt x={px + 53} y={sY} s={e.s} size={8.5} fill="var(--mn-text-dim-2)" maxW={96} />
          ) : null}
        </g>
      );
    }

    case 'valve': {
      // УГО по референсу visual/ЗадвижкаКлапан: корпус из двух клиньев,
      // ступица, шток и круг-индикатор концевика. Задвижка (vt='gate')
      // отличается длинным штоком и малым высоким индикатором; клапан
      // (vt='cv') — коротким штоком и крупным индикатором ниже.
      const rot = e.r ? `rotate(${e.r} ${x} ${y})` : undefined;
      const c = e.ctrl ? live.ctrl(e.ctrl) : undefined;
      const isGate = e.vt === 'gate';
      let state: ValveState;
      if (c) {
        state = c.out >= 99 ? 'open' : c.out <= 1 ? 'closed' : 'mid';
      } else if (isGate) {
        state = e.gate
          ? live.valve(e.gate)
          : e.st === 'НЗ' ? 'closed' : 'open';
      } else if (e.gate) {
        state = live.valve(e.gate);
      } else if (e.src) {
        const v = live.sval(e.src);
        state = v == null ? 'mid' : v >= 99 ? 'open' : v <= 1 ? 'closed' : 'mid';
      } else {
        state = 'mid';
      }
      const col = state === 'fail' ? '#ff0000'
        : state === 'open' ? '#00af50'
          : state === 'mid' ? '#ffff00'
            : '#bebebe';
      const stemY = isGate ? -26 : -16;
      const stemH = isGate ? 46 : 18;
      const indCy = isGate ? -40 : -29.5;
      const indR = isGate ? 14 : 16;
      if (e.vt === 'angle') {
        // Угловой клапан (эталон: visual/klapan(1).html): подвод слева,
        // отвод вниз, шток с пружинным приводом вверх. Состояние — то же,
        // что у обычного клапана (цвет корпуса по открытию/закрытию).
        return (
          <g>
            <g transform={rot} className={state === 'fail' ? 'mn-alarm-flash' : undefined}>
              <line x1={x - 64} y1={y} x2={x - 30} y2={y} style={{ stroke: '#8c8c8c', strokeWidth: 2.4 }} />
              <line x1={x} y1={y + 28} x2={x} y2={y + 52} style={{ stroke: '#8c8c8c', strokeWidth: 2.4 }} />
              <line x1={x} y1={y - 22} x2={x} y2={y} style={{ stroke: '#8c8c8c', strokeWidth: 2.4 }} />
              <polygon
                points={`${x - 32},${y - 14} ${x - 32},${y + 14} ${x},${y}`}
                style={{ fill: col, stroke: '#8c8c8c', strokeWidth: 2.4, strokeLinejoin: 'round' }}
              />
              <polygon
                points={`${x - 18},${y + 30} ${x + 18},${y + 30} ${x},${y}`}
                style={{ fill: col, stroke: '#8c8c8c', strokeWidth: 2.4, strokeLinejoin: 'round' }}
              />
              <polyline
                points={`${x},${y - 22} ${x + 12},${y - 31} ${x - 2},${y - 37}`}
                fill="none"
                style={{ stroke: '#8c8c8c', strokeWidth: 2.4, strokeLinecap: 'round', strokeLinejoin: 'round' }}
              />
            </g>
            {e.st ? <Tx x={x} y={y + 62} s={e.st} size={9} fill="var(--mn-amber)" /> : null}
            {e.n ? (
              <Txt x={x} y={e.st ? y + 74 : y + 62} s={e.n} size={8} fill="var(--mn-text-dim)" maxW={44} />
            ) : null}
          </g>
        );
      }
      return (
        <g>
          <g transform={rot} className={state === 'fail' ? 'mn-alarm-flash' : undefined}>
            <polygon
              points={`${x - 26},${y - 20} ${x - 26},${y + 20} ${x},${y}`}
              style={{ fill: col, stroke: '#8c8c8c', strokeWidth: 2, strokeLinejoin: 'round' }}
            />
            <polygon
              points={`${x + 26},${y - 20} ${x + 26},${y + 20} ${x},${y}`}
              style={{ fill: col, stroke: '#8c8c8c', strokeWidth: 2, strokeLinejoin: 'round' }}
            />
            <circle cx={x} cy={y} r={6} style={{ fill: '#a6a6a6', stroke: '#8c8c8c', strokeWidth: 1.5 }} />
            <rect x={x - 2.5} y={y + stemY} width={5} height={stemH} style={{ fill: '#a6a6a6', stroke: '#8c8c8c', strokeWidth: 1.5 }} />
            <circle cx={x} cy={y + indCy} r={indR} style={{ fill: col, stroke: '#8c8c8c', strokeWidth: 2 }} />
          </g>
          {e.st ? <Tx x={x} y={y + 24} s={e.st} size={9} fill="var(--mn-amber)" /> : null}
          {e.vt === 'gate' && !c && e.gate ? (
            <Tx
              x={x}
              y={y + 24}
              s={state === 'fail' ? 'АВАР' : state === 'open' ? 'ОТКР' : state === 'closed' ? 'ЗАКР' : 'СРЕД'}
              size={9}
              fill={state === 'open' ? 'var(--mn-accent)' : 'var(--mn-amber)'}
            />
          ) : null}
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
            <Txt x={x} y={e.st || c || isGate ? y + 36 : y + 24} s={e.n} size={8} fill="var(--mn-text-dim)" maxW={44} />
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
    const nL = labelLines(e.n, 10, 96);
    const sL = labelLines(e.s, 8.5, 96);
    const h = 79 + nL * 11.8 + (sL ? 7 + sL * 10.03 : 0);
    return [e.x - 2, e.y - 4, 100, h];
  }
  if (e.t === 'valve') {
    if (e.vt === 'angle') {
      const hasLbl = !!e.st || !!e.ctrl;
      const nY = hasLbl ? 76 : 64;
      const nL = labelLines(e.n, 8, 44);
      const bot = nY + nL * 9.44 + 4;
      return [e.x - 66, e.y - 39, 84, Math.max(58, bot)];
    }
    const hasLbl = !!e.st || !!e.ctrl || e.vt === 'gate';
    const top = e.vt === 'gate' ? 54 : 45.5;
    const nY = hasLbl ? 58 : 46;
    const nL = labelLines(e.n, 8, 44);
    const bot = nY + nL * 9.44 + 4;
    return [e.x - 27, e.y - top - 2, 54, Math.max(top + 22, top + bot)];
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
    const bot = 56 + nL * 10.62 + 4;
    return [e.x - 72, e.y - 42, 144, 42 + bot];
  }
  if (e.t === 'hx') {
    const nL = labelLines(e.n, 10, e.w || 60);
    const sL = labelLines(e.s, 8.5, e.w || 60);
    const bot = 16 + nL * 11.8 + (sL ? 7 + sL * 10.03 : 0) + 4;
    return [e.x - 3, e.y - 14, (e.w || 60) + 6, 14 + bot];
  }
  if (e.t === 'col') {
    if (e.detail) {
      const col = e.detail as MnemoColDetail;
      const [dx, dy, dw, dh] = colDetailBounds(col);
      const s = (e.w || col.nodeW || 130) / col.vb.w;
      const nL = labelLines(e.n, 11, col.vb.w * s + 8);
      const sL = labelLines(e.s, 9.5, col.vb.w * s + 30);
      const top = 10 + (sL ? (sL - 1) * 11.21 : 0);
      const bot = dh * s + 16 + nL * 12.98 + 4;
      return [e.x + dx * s, e.y + dy * s - top, dw * s, top + bot];
    }
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
    if (e.detail) {
      const d = e.detail as MnemoFurDetail;
      const [dx, dy, dw, dh] = furDetailBounds(d);
      const s = (e.w || d.nodeW || 200) / d.vb.w;
      const nL = labelLines(e.n, 11, d.vb.w * s + 8);
      const sL = labelLines(e.s, 9.5, d.vb.w * s + 30);
      const top = 10 + (sL ? (sL - 1) * 11.21 : 0);
      const bot = dh * s + 16 + nL * 12.98 + 4;
      return [e.x + dx * s, e.y + dy * s - top, dw * s, top + bot];
    }
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
