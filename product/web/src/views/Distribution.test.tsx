import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import type { BootstrapPoint, StrategyMetric } from "../types";
import { Distribution } from "./Distribution";

vi.mock("../api", () => ({ getMetrics: vi.fn(), getBootstrap: vi.fn() }));
vi.mock("../components/Chart", () => ({ Chart: () => <div data-testid="chart-stub" /> }));

const metricNames = ["B0 QQQ-DCA", "D3 Tiered"];

beforeEach(() => {
  vi.mocked(api.getMetrics).mockResolvedValue(
    metricNames.map((name) => ({ name }) as StrategyMetric),
  );
  const pts: BootstrapPoint[] = [{ strategy: "B0 QQQ-DCA", step: 0, p5: 1, p50: 1, p95: 1 }];
  vi.mocked(api.getBootstrap).mockResolvedValue(pts);
});

test("loads bootstrap for the first strategy and renders the fan chart", async () => {
  render(<Distribution />);
  await waitFor(() => expect(screen.getByTestId("chart-stub")).toBeInTheDocument());
  expect(api.getBootstrap).toHaveBeenCalledWith("B0 QQQ-DCA");
});
