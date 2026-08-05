import type { MouseEvent } from 'react';
import type { MnemoItem, MnemoScreenData } from './mnemoTypes';
import type { MnemoLive } from './sources';
import { itemBBox, renderItem } from './symbols';

interface Props {
  data: MnemoScreenData;
  live: MnemoLive;
  selected: number | null;
  onSelect: (idx: number, item: MnemoItem) => void;
  onDeselect: () => void;
}

function pipePath(pts: number[][]): string {
  return pts.map((q, j) => `${j ? 'L' : 'M'}${q[0]} ${q[1]}`).join(' ');
}

export function MnemoScreen({ data, live, selected, onSelect, onDeselect }: Props) {
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
                  <circle cx={p.pts[0][0]} cy={p.pts[0][1]} r={3.6} fill={col} stroke="#0e1317" strokeWidth={1.1} pointerEvents="none" />
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
          const clickable = !!e.ctrl;
          const bb = itemBBox(e);
          return (
            <g
              key={`i${i}`}
              className={clickable ? 'mn-it mn-it-ctr' : 'mn-it'}
              onClick={clickable ? () => onSelect(i, e) : undefined}
            >
              {renderItem(e, live)}
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
