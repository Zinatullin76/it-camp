import type { MouseEvent } from 'react';
import type { MnemoItem, MnemoScreenData } from './mnemoTypes';
import type { MnemoLive } from './sources';
import { fmtVal, PARAM_LABEL } from './sources';
import { itemBBox, renderItem } from './symbols';

interface Props {
  data: MnemoScreenData;
  live: MnemoLive;
  disp?: Record<string, string[]>;
  selected: number | null;
  onSelect: (idx: number, item: MnemoItem) => void;
  onDeselect: () => void;
}

function pipePath(pts: number[][]): string {
  return pts.map((q, j) => `${j ? 'L' : 'M'}${q[0]} ${q[1]}`).join(' ');
}

export function MnemoScreen({ data, live, disp, selected, onSelect, onDeselect }: Props) {
  const vb = data.vb.join(' ');

  return (
    <svg
      className="mnemo-svg"
      viewBox={vb}
      preserveAspectRatio="xMidYMid meet"
      onClick={(e: MouseEvent<SVGSVGElement>) => {
        if (e.target === e.currentTarget) onDeselect();
      }}
    >
      <g>
        {data.pipes.map((p, i) => {
          const col = live.flowColor(p.f);
          const sig = p.f === 'sig';
          return (
            <g key={`p${i}`}>
              <path
                d={pipePath(p.pts)}
                fill="none"
                stroke={col}
                strokeWidth={sig ? 1.4 : 3.2}
                strokeDasharray={sig ? '7 5' : undefined}
                strokeLinejoin="round"
                strokeLinecap="round"
                opacity={sig ? 0.85 : 0.9}
              />
              {sig && p.pts.length > 0 && (
                <>
                  <circle cx={p.pts[0][0]} cy={p.pts[0][1]} r={3.6} fill={col} stroke="var(--mn-fill)" strokeWidth={1.1} pointerEvents="none" />
                  {p.pts.length > 1 && (
                    <circle cx={p.pts[p.pts.length - 1][0]} cy={p.pts[p.pts.length - 1][1]} r={2.2} fill="none" stroke={col} strokeWidth={1.1} pointerEvents="none" />
                  )}
                </>
              )}
            </g>
          );
        })}
      </g>
      <g>
        {data.items.map((e, i) => {
          const clickable = !!e.ctrl || !!live.equip(e.n ?? '');
          const bb = itemBBox(e);
          return (
            <g
              key={`i${i}`}
              className={clickable ? 'mn-it mn-it-ctr' : 'mn-it'}
              onClick={clickable ? () => onSelect(i, e) : undefined}
            >
              {renderItem(e, live)}
              {disp && e.t === 'pump' && live.equip(e.n ?? '') && (disp[e.n ?? ''] ?? []).length > 0 && (
                <g pointerEvents="none">
                  {(disp[e.n ?? ''] ?? []).map((key, j) => (
                    <g key={key}>
                      <rect x={e.x + 34} y={e.y - 2 + j * 24} width={80} height={20} rx={2} style={{ fill: 'var(--mn-fill-3)', stroke: 'var(--mn-line-2)', strokeWidth: 1 }} />
                      <text x={e.x + 38} y={e.y + 8 + j * 24} fontSize={7} style={{ fill: 'var(--mn-text-dim)' }}>{PARAM_LABEL[key] ?? key}</text>
                      <text x={e.x + 110} y={e.y + 17 + j * 24} fontSize={11} textAnchor="end" fontFamily="Consolas" style={{ fill: 'var(--mn-accent)' }}>{fmtVal(live.param(e.n!, key))}</text>
                    </g>
                  ))}
                </g>
              )}
              <rect
                className="mn-bbox"
                x={bb[0]}
                y={bb[1]}
                width={bb[2]}
                height={bb[3]}
                fill="transparent"
                stroke={selected === i ? '#4fd1c5' : 'none'}
                strokeDasharray="4 3"
              />
            </g>
          );
        })}
      </g>
    </svg>
  );
}
