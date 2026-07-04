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
