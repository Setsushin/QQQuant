import { expect, test } from "vitest";
import { bootstrapFan, equityToLine, num, pct, sortBy, uniqueStrategies } from "./format";
import type { BootstrapPoint } from "./types";

test("pct and num format with fixed precision", () => {
  expect(pct(0.1234)).toBe("12.3%");
  expect(pct(0.1234, 2)).toBe("12.34%");
  expect(num(1.2345)).toBe("1.23");
});

test("equityToLine maps dates to chart time", () => {
  expect(equityToLine([{ date: "2024-01-31", value: 100 }])).toEqual([
    { time: "2024-01-31", value: 100 },
  ]);
});

test("bootstrapFan sorts by step and builds three series on a shared axis", () => {
  const pts: BootstrapPoint[] = [
    { strategy: "B0", step: 1, p5: 0.9, p50: 1.0, p95: 1.1 },
    { strategy: "B0", step: 0, p5: 1.0, p50: 1.0, p95: 1.0 },
  ];
  const fan = bootstrapFan(pts);
  expect(fan.p50).toHaveLength(2);
  expect(fan.p5[0]?.value).toBe(1.0); // step 0 first after sort
  expect(fan.p95[1]?.value).toBe(1.1);
  // shared, increasing time axis
  expect(fan.p50[0]!.time < fan.p50[1]!.time).toBe(true);
});

test("sortBy handles numbers and strings in both directions", () => {
  const rows = [
    { name: "b", v: 2 },
    { name: "a", v: 1 },
    { name: "c", v: 3 },
  ];
  expect(sortBy(rows, "v", "desc").map((r) => r.v)).toEqual([3, 2, 1]);
  expect(sortBy(rows, "name", "asc").map((r) => r.name)).toEqual(["a", "b", "c"]);
});

test("uniqueStrategies dedupes preserving order", () => {
  expect(uniqueStrategies([{ strategy: "x" }, { strategy: "y" }, { strategy: "x" }])).toEqual([
    "x",
    "y",
  ]);
});
