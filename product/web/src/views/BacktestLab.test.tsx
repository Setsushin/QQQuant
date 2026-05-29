import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import type { BacktestResult } from "../types";
import { BacktestLab } from "./BacktestLab";

vi.mock("../api", () => ({ runBacktest: vi.fn() }));
vi.mock("../components/Chart", () => ({ Chart: () => <div data-testid="chart-stub" /> }));

const RESULT: BacktestResult = {
  metrics: {
    name: "DD tiered",
    cagr: 0.17,
    cagr_after_tax: 0.16,
    total_return: 1,
    twr: 1,
    mwr: 0.1,
    mwr_after_tax: 0.09,
    ann_vol: 0.23,
    max_drawdown: -0.56,
    max_dd_duration_months: 18,
    longest_underwater_months: 20,
    worst_rolling_12m: -0.3,
    worst_rolling_36m: -0.1,
    sharpe: 0.8,
    sortino: 1,
    calmar: 0.3,
    tax_drag: 0.01,
    taxable_events_per_year: 0.3,
    pct_months_deviation: 0.13,
  },
  equity_curve: [{ date: "2024-01-31", value: 100 }],
};

beforeEach(() => {
  vi.mocked(api.runBacktest).mockResolvedValue(RESULT);
});

test("running a backtest posts the built request and shows metrics + chart", async () => {
  render(<BacktestLab />);
  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  expect(await screen.findByTestId("result")).toBeInTheDocument();
  expect(screen.getByTestId("chart-stub")).toBeInTheDocument();
  // default kind is drawdown_tilt with the tiered preset
  const req = vi.mocked(api.runBacktest).mock.calls[0]![0];
  expect(req.kind).toBe("drawdown_tilt");
  expect(req.tiers).toEqual([
    [0.15, "QLD"],
    [0.25, "TQQQ"],
  ]);
});

test("surfaces an error when the compute endpoint fails", async () => {
  vi.mocked(api.runBacktest).mockRejectedValue(new Error("boom"));
  render(<BacktestLab />);
  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("boom");
});
