import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import type { StrategyMetric } from "../types";
import { StrategyComparison } from "./StrategyComparison";

vi.mock("../api", () => ({ getMetrics: vi.fn(), getEquity: vi.fn() }));
vi.mock("../components/Chart", () => ({
  Chart: () => <div data-testid="chart-stub" />,
}));

function metric(name: string, cagr: number, afterTax: number): StrategyMetric {
  return {
    name,
    cagr,
    cagr_after_tax: afterTax,
    total_return: 1,
    twr: 1,
    mwr: 0.1,
    mwr_after_tax: 0.09,
    ann_vol: 0.2,
    max_drawdown: -0.5,
    max_dd_duration_months: 10,
    longest_underwater_months: 12,
    worst_rolling_12m: -0.2,
    worst_rolling_36m: -0.05,
    sharpe: 0.8,
    sortino: 1,
    calmar: 0.3,
    tax_drag: 0.01,
    taxable_events_per_year: 0,
    pct_months_deviation: 0,
  };
}

beforeEach(() => {
  vi.mocked(api.getMetrics).mockResolvedValue([
    metric("LOW", 0.1, 0.09),
    metric("HIGH", 0.3, 0.28),
  ]);
});

test("sorts by after-tax CAGR descending by default", async () => {
  render(<StrategyComparison />);
  await screen.findByText("Strategy comparison");
  const rows = screen.getAllByRole("row").slice(1, 3); // skip header
  expect(within(rows[0]!).getByText("HIGH")).toBeInTheDocument();
});

test("clicking a header toggles sort direction", async () => {
  render(<StrategyComparison />);
  await screen.findByText("Strategy comparison");
  fireEvent.click(screen.getByText(/After-tax CAGR/));
  const rows = screen.getAllByRole("row").slice(1, 3);
  expect(within(rows[0]!).getByText("LOW")).toBeInTheDocument(); // ascending now
});

test("renders the pre/after-tax impact section", async () => {
  render(<StrategyComparison />);
  expect(await screen.findByTestId("tax-impact")).toBeInTheDocument();
});

test("clicking a row expands a detail panel with charts; click again collapses", async () => {
  vi.mocked(api.getEquity).mockResolvedValue([
    { date: "2020-01-31T00:00:00", equity: 100, drawdown: 0 },
  ]);
  render(<StrategyComparison />);
  await screen.findByText("Strategy comparison");
  // "LOW" appears in the table cell and in the TaxImpact bar; take the table-row one.
  const lowRow = screen
    .getAllByText("LOW")
    .map((el) => el.closest("tr"))
    .find((tr): tr is HTMLTableRowElement => tr !== null && tr.classList.contains("strategy-row"));
  expect(lowRow).toBeDefined();
  expect(lowRow!.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(lowRow!);
  expect(lowRow!.getAttribute("aria-expanded")).toBe("true");
  // Two chart stubs render (equity + drawdown).
  await screen.findAllByTestId("chart-stub");
  expect(screen.getAllByTestId("chart-stub")).toHaveLength(2);
  fireEvent.click(lowRow!);
  expect(lowRow!.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryAllByTestId("chart-stub")).toHaveLength(0);
});
