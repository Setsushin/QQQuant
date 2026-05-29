import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Findings } from "./Findings";

// Rendered without a LangProvider → useLang() falls back to the "en" context default.
test("renders the verdict, the metrics table, and the ranked top-3", () => {
  render(<Findings />);
  expect(screen.getByText(/honest negative result/i)).toBeInTheDocument();
  expect(screen.getByText("Core · default")).toBeInTheDocument();
  expect(screen.getByText("Risk-first bucket")).toBeInTheDocument();
  // B0 appears in both the table and the top-3 cards
  expect(screen.getAllByText("B0 QQQ-DCA").length).toBeGreaterThanOrEqual(2);
});
