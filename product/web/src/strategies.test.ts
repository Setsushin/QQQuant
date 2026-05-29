import { expect, test } from "vitest";
import { shortCode, strategyMeta } from "./strategies";

test("known codes resolve to a plain-language description", () => {
  const meta = strategyMeta("D3 Tiered");
  expect(meta.family).toBe("Drawdown tilt");
  expect(meta.description).toMatch(/QLD/);
  expect(meta.description).toMatch(/TQQQ/);
});

test("unknown codes fall back to the raw name with an empty description", () => {
  const meta = strategyMeta("Custom-Lab-Run");
  expect(meta.code).toBe("Custom-Lab-Run");
  expect(meta.description).toBe("");
});

test("shortCode returns the leading token", () => {
  expect(shortCode("B0 QQQ-DCA")).toBe("B0");
  expect(shortCode("D4 Tiered+200WMA")).toBe("D4");
});
