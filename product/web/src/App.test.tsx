import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "./api";
import { App } from "./App";
import type { CurrentSignal, StrategyMetric } from "./types";

vi.mock("./api", () => ({
  getSignals: vi.fn(),
  getMetrics: vi.fn(),
  getCrisis: vi.fn(),
  getBootstrap: vi.fn(),
  runBacktest: vi.fn(),
}));

const SIGNAL: CurrentSignal = {
  strategy: "B0 QQQ-DCA",
  as_of: "2026-05-27T00:00:00",
  target_symbol: "QQQ",
  target_weight: 1,
  allocation: '{"QQQ": 1.0}',
  qqq_drawdown_52w: -0.05,
  qqq_above_200dma: true,
};

const METRIC: StrategyMetric = {
  name: "B0 QQQ-DCA",
  cagr: 0.16,
  cagr_after_tax: 0.15,
  total_return: 1,
  twr: 1,
  mwr: 0.1,
  mwr_after_tax: 0.09,
  ann_vol: 0.22,
  max_drawdown: -0.53,
  max_dd_duration_months: 20,
  longest_underwater_months: 22,
  worst_rolling_12m: -0.3,
  worst_rolling_36m: -0.1,
  sharpe: 0.8,
  sortino: 1.1,
  calmar: 0.3,
  tax_drag: 0.01,
  taxable_events_per_year: 0,
  pct_months_deviation: 0,
};

beforeEach(() => {
  localStorage.clear(); // language choice persists in localStorage; start each test in the default
  vi.mocked(api.getSignals).mockResolvedValue([SIGNAL]);
  vi.mocked(api.getMetrics).mockResolvedValue([METRIC]);
});

test("defaults to the comparison tab", async () => {
  render(<App />);
  expect(await screen.findByText("Strategy comparison")).toBeInTheDocument();
  expect(api.getMetrics).toHaveBeenCalled();
});

test("switching tabs loads the signal view", async () => {
  render(<App />);
  await screen.findByText("Strategy comparison");
  fireEvent.click(screen.getByRole("button", { name: "Signal" }));
  expect(await screen.findByTestId("context")).toHaveTextContent("above 200DMA");
});

test("the header language toggle flips the whole UI to 中文", async () => {
  render(<App />);
  await screen.findByText("Strategy comparison");
  expect(screen.getByRole("heading", { name: "Strategy comparison" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "中文" }));
  expect(screen.getByRole("heading", { name: "策略对比" })).toBeInTheDocument();
  // tab labels switch too, and the toggle now offers the way back
  expect(screen.getByRole("button", { name: "信号" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
});
