import type { BootstrapPoint, EquityPoint } from "./types";

export const pct = (x: number, digits = 1): string => `${(x * 100).toFixed(digits)}%`;
export const num = (x: number, digits = 2): string => x.toFixed(digits);

// Lightweight-Charts line data. Monthly equity dates are ISO 'YYYY-MM-DD' (BusinessDay).
export interface LinePoint {
  time: string;
  value: number;
}

export const equityToLine = (curve: EquityPoint[]): LinePoint[] =>
  curve.map((p) => ({ time: p.date, value: p.value }));

// Bootstrap is indexed by integer step (no calendar date); chart it on a synthetic
// monthly axis from a fixed epoch so the percentile lines share an x-axis.
const EPOCH = Date.UTC(2000, 0, 1);

function stepToDate(step: number): string {
  const d = new Date(EPOCH);
  d.setUTCMonth(d.getUTCMonth() + step);
  return d.toISOString().slice(0, 10);
}

export interface FanSeries {
  p5: LinePoint[];
  p50: LinePoint[];
  p95: LinePoint[];
}

export function bootstrapFan(points: BootstrapPoint[]): FanSeries {
  const sorted = [...points].sort((a, b) => a.step - b.step);
  return {
    p5: sorted.map((p) => ({ time: stepToDate(p.step), value: p.p5 })),
    p50: sorted.map((p) => ({ time: stepToDate(p.step), value: p.p50 })),
    p95: sorted.map((p) => ({ time: stepToDate(p.step), value: p.p95 })),
  };
}

export function uniqueStrategies<T extends { strategy: string }>(rows: T[]): string[] {
  return [...new Set(rows.map((r) => r.strategy))];
}

export type SortDir = "asc" | "desc";

export function sortBy<T>(rows: T[], key: keyof T, dir: SortDir): T[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = a[key];
    const y = b[key];
    if (typeof x === "number" && typeof y === "number") return (x - y) * sign;
    return String(x).localeCompare(String(y)) * sign;
  });
}
