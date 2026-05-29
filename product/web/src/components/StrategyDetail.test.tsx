import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import * as api from "../api";
import type { StrategyMetric } from "../types";
import { narrative, StrategyDetail } from "./StrategyDetail";

vi.mock("../api", () => ({ getEquity: vi.fn() }));
vi.mock("./Chart", () => ({ Chart: ({ series }: { series: unknown[] }) => (
  <div data-testid="chart-stub" data-series={String(series.length)} />
) }));

function metric(name: string, partial: Partial<StrategyMetric> = {}): StrategyMetric {
  return {
    name,
    cagr: 0.16,
    cagr_after_tax: 0.15,
    total_return: 1,
    twr: 1,
    mwr: 0.1,
    mwr_after_tax: 0.09,
    ann_vol: 0.22,
    max_drawdown: -0.5,
    max_dd_duration_months: 20,
    longest_underwater_months: 22,
    worst_rolling_12m: -0.3,
    worst_rolling_36m: -0.1,
    sharpe: 0.8,
    sortino: 1.1,
    calmar: 0.3,
    tax_drag: 0.01,
    taxable_events_per_year: 0.05,
    pct_months_deviation: 0,
    ...partial,
  };
}

test("narrative labels the baseline row distinctly", () => {
  const b = metric("B0 QQQ-DCA");
  expect(narrative(b, b)).toEqual([expect.stringMatching(/Baseline/)]);
});

test("narrative surfaces both gain and cost vs baseline", () => {
  const baseline = metric("B0 QQQ-DCA");
  const tilted = metric("D3 Tiered", {
    cagr_after_tax: 0.17,
    max_drawdown: -0.65, // deeper than baseline -0.5
    taxable_events_per_year: 1.8,
    tax_drag: 0.005,
    pct_months_deviation: 0.18,
  });
  const lines = narrative(tilted, baseline);
  expect(lines[0]).toMatch(/After-tax CAGR \+2\.0pp/);
  expect(lines[0]).toMatch(/deeper/);
  expect(lines[1]).toMatch(/1\.80 taxable events/);
  expect(lines[1]).toMatch(/baseline 0\.05/);
  expect(lines[2]).toMatch(/18% of months/);
});

test("renders two charts (equity + drawdown) for a non-baseline strategy", async () => {
  vi.mocked(api.getEquity).mockResolvedValue([
    { date: "2020-01-31T00:00:00", equity: 100, drawdown: 0 },
    { date: "2020-02-29T00:00:00", equity: 110, drawdown: 0 },
  ]);
  const b = metric("B0 QQQ-DCA");
  const s = metric("D3 Tiered", { cagr_after_tax: 0.17 });
  render(<StrategyDetail strategy={s} baseline={b} />);
  await waitFor(() => expect(screen.getAllByTestId("chart-stub")).toHaveLength(2));
  // Strategy + baseline overlay = 2 series per chart when distinct.
  expect(screen.getAllByTestId("chart-stub")[0]).toHaveAttribute("data-series", "2");
});

test("baseline row shows a single equity line, no overlay", async () => {
  vi.mocked(api.getEquity).mockResolvedValue([
    { date: "2020-01-31T00:00:00", equity: 100, drawdown: 0 },
  ]);
  const b = metric("B0 QQQ-DCA");
  render(<StrategyDetail strategy={b} baseline={b} />);
  await waitFor(() => expect(screen.getAllByTestId("chart-stub")).toHaveLength(2));
  expect(screen.getAllByTestId("chart-stub")[0]).toHaveAttribute("data-series", "1");
});
