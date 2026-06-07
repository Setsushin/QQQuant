import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import type { BacktestResult, FactorCell, FactorsResponse } from "../types";
import { FactorMatrix } from "./FactorMatrix";

vi.mock("../api", () => ({ getFactors: vi.fn(), runBacktest: vi.fn() }));
vi.mock("../components/Chart", () => ({ Chart: () => <div data-testid="chart-stub" /> }));

// A tiny matrix: a valid VIX tilt cell, and the same with exit=none which is invalid.
const cells: FactorCell[] = [
  { scope: "tilt", trigger: "vix", ladder: "tiered", gate: "200d", exit: "vixcalm", valid: true, reason: null, requires: ["VIX"] },
  { scope: "tilt", trigger: "vix", ladder: "tiered", gate: "200d", exit: "never", valid: true, reason: null, requires: ["VIX"] },
  { scope: "fixed", trigger: "vix", ladder: "tiered", gate: "200d", exit: "none", valid: false, reason: "a tilt needs an exit rule", requires: ["VIX"] },
];
const factors: FactorsResponse = {
  axes: { trigger: ["vix"], ladder: ["tiered"], gate: ["200d"], exit: ["vixcalm", "never", "none"] },
  cells,
};

beforeEach(() => {
  vi.mocked(api.getFactors).mockResolvedValue(factors);
  vi.mocked(api.runBacktest).mockResolvedValue({
    metrics: { name: "matrix", cagr: 0.1, cagr_after_tax: 0.08, ann_vol: 0.2, max_drawdown: -0.3, sharpe: 0.5 },
    equity_curve: [{ date: "2020-01-31", value: 100 }],
  } as unknown as BacktestResult);
});

test("keeps a trigger selectable even when the current axes are invalid for it", async () => {
  // Initial selection is a VIX tilt (vix/tiered/200d/vixcalm). Switching to the `none` trigger
  // snaps to its default (none/tiered/none/none), which is valid — so the button must stay enabled
  // even though a bare trigger swap (none/tiered/200d/vixcalm) would be invalid.
  const richCells: FactorCell[] = [
    { scope: "tilt", trigger: "vix", ladder: "tiered", gate: "200d", exit: "vixcalm", valid: true, reason: null, requires: ["VIX"] },
    { scope: "fixed", trigger: "none", ladder: "tiered", gate: "none", exit: "none", valid: true, reason: null, requires: [] },
  ];
  vi.mocked(api.getFactors).mockResolvedValue({
    axes: { trigger: ["none", "vix"], ladder: ["tiered"], gate: ["200d"], exit: ["vixcalm"] },
    cells: richCells,
  });
  render(<FactorMatrix />);
  await waitFor(() => expect(api.getFactors).toHaveBeenCalled());
  expect(screen.getByRole("button", { name: /buy & hold QQQ/i })).toBeEnabled();
});

test("greys out the invalid exit option and runs the selected valid cell", async () => {
  render(<FactorMatrix />);
  await waitFor(() => expect(api.getFactors).toHaveBeenCalled());

  // exit=none would make the combo invalid → its button is disabled.
  const noneOption = screen.getByRole("button", { name: /none/i });
  expect(noneOption).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: /run/i }));
  await waitFor(() => expect(screen.getByTestId("result")).toBeInTheDocument());
  expect(api.runBacktest).toHaveBeenCalledWith({
    name: "matrix",
    factors: { trigger: "vix", ladder: "tiered", gate: "200d", exit: "vixcalm" },
  });
});
