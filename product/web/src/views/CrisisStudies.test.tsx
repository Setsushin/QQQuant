import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import * as api from "../api";
import type { CrisisRow } from "../types";
import { CrisisStudies, groupByEpisode } from "./CrisisStudies";

vi.mock("../api", () => ({ getCrisis: vi.fn() }));

function row(episode: string, strategy: string, start: string, synth: boolean): CrisisRow {
  return {
    episode,
    start,
    end: "2009-06-30T00:00:00",
    qqq_drawdown: -0.5,
    synthesized: synth,
    strategy,
    cagr: 0.1,
    cagr_after_tax: 0.09,
    max_drawdown: -0.6,
    taxable_events_per_year: 0.3,
    pct_months_deviation: 0.1,
  };
}

test("groupByEpisode collates strategies and orders by start date", () => {
  const groups = groupByEpisode([
    row("covid", "B0", "2020-02-01T00:00:00", false),
    row("gfc", "B0", "2007-10-01T00:00:00", true),
    row("gfc", "D3", "2007-10-01T00:00:00", true),
  ]);
  expect(groups.map((g) => g.name)).toEqual(["gfc", "covid"]);
  expect(groups[0]!.rows).toHaveLength(2);
  expect(groups[0]!.synthesized).toBe(true);
});

beforeEach(() => {
  vi.mocked(api.getCrisis).mockResolvedValue([row("gfc", "B0", "2007-10-01T00:00:00", true)]);
});

test("renders the small-sample caveat and a synthesized badge", async () => {
  render(<CrisisStudies />);
  expect(await screen.findByRole("note")).toHaveTextContent("the sample is tiny");
  expect(screen.getByText("synthesized")).toBeInTheDocument();
});
