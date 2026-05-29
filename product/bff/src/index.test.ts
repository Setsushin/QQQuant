import { afterEach, expect, mock, test } from "bun:test";
import { app } from "./index";
import type { CurrentSignal } from "./types";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function stubUpstream(body: unknown, status = 200): void {
  globalThis.fetch = mock(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

test("health is local, no upstream call", async () => {
  const res = await app.request("/health");
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});

test("proxies signals from the upstream read API", async () => {
  const signal: CurrentSignal = {
    strategy: "B0 QQQ-DCA",
    as_of: "2024-01-31T00:00:00",
    target_symbol: "QQQ",
    target_weight: 1,
    allocation: '{"QQQ": 1.0}',
    qqq_drawdown_52w: 0,
    qqq_above_200dma: true,
  };
  stubUpstream([signal]);
  const res = await app.request("/api/signals");
  expect(res.status).toBe(200);
  const rows = (await res.json()) as CurrentSignal[];
  expect(rows[0]?.target_symbol).toBe("QQQ");
});

test("forwards upstream error status (503 when store unpublished)", async () => {
  stubUpstream({ detail: "serving store not published yet" }, 503);
  const res = await app.request("/api/metrics");
  expect(res.status).toBe(503);
});

test("returns 502 when the serving API is unreachable", async () => {
  globalThis.fetch = mock(async () => {
    throw new Error("ECONNREFUSED");
  }) as unknown as typeof fetch;
  const res = await app.request("/api/signals");
  expect(res.status).toBe(502);
});

test("backtest forwards a POST body to the compute endpoint", async () => {
  let seen: { url: string; method?: string; body?: string } = { url: "" };
  globalThis.fetch = mock(async (url: string | URL | Request, init?: RequestInit) => {
    seen = { url: String(url), method: init?.method, body: init?.body as string };
    return new Response(JSON.stringify({ metrics: { name: "spike" }, equity_curve: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
  const res = await app.request("/api/backtest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "sma_switch", leveraged: "TQQQ" }),
  });
  expect(res.status).toBe(200);
  expect(seen.url).toContain("/backtest");
  expect(seen.method).toBe("POST");
  expect(seen.body).toContain("sma_switch");
});

test("bootstrap forwards the strategy filter as a query param", async () => {
  let seen = "";
  globalThis.fetch = mock(async (url: string | URL | Request) => {
    seen = String(url);
    return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
  }) as unknown as typeof fetch;
  await app.request("/api/bootstrap?strategy=D3%20Tiered");
  expect(seen).toContain("/bootstrap?strategy=D3%20Tiered");
});
