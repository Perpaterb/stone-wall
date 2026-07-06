// Shoelace area of a polygon [[x, y], ...] in cm, returns cm^2.
export function polygonAreaCm2(points: number[][]): number {
  const n = points.length;
  if (n < 3) return 0;
  let s = 0;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % n];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

// Snap `next` to be horizontal or vertical relative to `prev` (whichever axis is closer).
export function orthoSnap(prev: number[], next: number[]): number[] {
  const dx = Math.abs(next[0] - prev[0]);
  const dy = Math.abs(next[1] - prev[1]);
  return dx >= dy ? [next[0], prev[1]] : [prev[0], next[1]];
}

// Snap a point to a grid (default 1 cm = 10 mm).
export function snapGrid(p: number[], step = 1): number[] {
  return [Math.round(p[0] / step) * step, Math.round(p[1] / step) * step];
}

// Snap a new segment from `prev` to `raw`: angle to `angStep` degrees, length to
// `lenStep` cm.
export function snapSegment(prev: number[], raw: number[], angStep = 5, lenStep = 1): number[] {
  const dx = raw[0] - prev[0];
  const dy = raw[1] - prev[1];
  const len = Math.round(Math.hypot(dx, dy) / lenStep) * lenStep;
  if (len === 0) return [prev[0], prev[1]];
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  const a = (Math.round(deg / angStep) * angStep * Math.PI) / 180;
  return [prev[0] + Math.cos(a) * len, prev[1] + Math.sin(a) * len];
}
