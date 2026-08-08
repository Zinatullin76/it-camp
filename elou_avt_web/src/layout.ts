import type { SchemeNodeData, SchemeEdgeData } from './types';
import type { MnemoItem } from './mnemo/mnemoTypes';
import { mnemoPlacement } from './mnemo/mnemoMap';

export interface LayoutPos {
  x: number;
  y: number;
}

export interface NodePlacement {
  pos: LayoutPos;
  size: { w: number; h: number };
  mnemo?: Partial<MnemoItem>;
}

type Sizes = (n: SchemeNodeData) => { w: number; h: number };

const FALLBACK_GAP = 18;

function boxesOverlap(
  a: LayoutPos, aw: number, ah: number,
  b: LayoutPos, bw: number, bh: number,
): boolean {
  const m = 4;
  return (
    a.x < b.x + bw + m && b.x < a.x + aw + m &&
    a.y < b.y + bh + m && b.y < a.y + ah + m
  );
}

/** Search a small spiral around (cx, cy) for a spot that does not overlap placed boxes. */
function findFreeSlot(
  cx: number, cy: number, w: number, h: number,
  placed: Map<string, NodePlacement>,
): LayoutPos {
  for (let ring = 0; ring < 30; ring++) {
    const step = ring * (FALLBACK_GAP + 12);
    const cands: LayoutPos[] = [
      { x: cx, y: cy },
      { x: cx + step, y: cy },
      { x: cx - step, y: cy },
      { x: cx, y: cy + step },
      { x: cx, y: cy - step },
    ];
    for (const c of cands) {
      let ok = true;
      for (const p of placed.values()) {
        if (boxesOverlap(c, w, h, p.pos, p.size.w, p.size.h)) {
          ok = false;
          break;
        }
      }
      if (ok) return c;
    }
  }
  return { x: cx, y: cy };
}

/**
 * Layout the scheme using the hand-crafted mnemo "overview" positions for the
 * main apparatus; every node not present on the overview is placed near the
 * centre of its already-placed neighbours (valves end up on their pipe, tanks
 * near their feed, extra condensers near their column, products near the
 * apparatus they leave).
 */
export function mnemoLayout(
  nodes: SchemeNodeData[],
  edges: SchemeEdgeData[],
  sizes: Sizes,
): Map<string, NodePlacement> {
  const placed = new Map<string, NodePlacement>();

  for (const n of nodes) {
    const m = mnemoPlacement(n.id);
    if (m) {
      const [bx, by, bw, bh] = m.bb;
      const item: Partial<MnemoItem> = { ...m.item };
      delete (item as { x?: number }).x;
      delete (item as { y?: number }).y;
      placed.set(n.id, {
        pos: { x: bx, y: by },
        size: { w: bw, h: bh },
        mnemo: item,
      });
    }
  }

  const adj = new Map<string, string[]>();
  for (const n of nodes) adj.set(n.id, []);
  for (const e of edges) {
    if (e.source === e.target) continue;
    adj.get(e.source)?.push(e.target);
    adj.get(e.target)?.push(e.source);
  }

  let remaining = nodes.filter((n) => !placed.has(n.id));
  for (let guard = 0; guard < nodes.length && remaining.length; guard++) {
    const next: SchemeNodeData[] = [];
    for (const n of remaining) {
      const nb = (adj.get(n.id) ?? []).filter((p) => placed.has(p));
      if (!nb.length) {
        next.push(n);
        continue;
      }
      let cx = 0;
      let cy = 0;
      for (const p of nb) {
        const pn = placed.get(p)!;
        cx += pn.pos.x + pn.size.w / 2;
        cy += pn.pos.y + pn.size.h / 2;
      }
      cx /= nb.length;
      cy /= nb.length;
      const size = sizes(n);
      const pos = findFreeSlot(cx - size.w / 2, cy - size.h / 2, size.w, size.h, placed);
      placed.set(n.id, { pos, size });
    }
    remaining = next;
  }

  // Anything still unplaced (isolated subgraph) goes below the existing block.
  if (remaining.length) {
    let minY = 0;
    for (const p of placed.values()) minY = Math.max(minY, p.pos.y + p.size.h);
    let x = 0;
    let rowH = 0;
    for (const n of remaining) {
      const size = sizes(n);
      if (x + size.w > 1600) {
        x = 0;
        minY += rowH + FALLBACK_GAP;
        rowH = 0;
      }
      placed.set(n.id, { pos: { x, y: minY }, size });
      x += size.w + FALLBACK_GAP;
      rowH = Math.max(rowH, size.h);
    }
  }

  return placed;
}
