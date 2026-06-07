import { Hono } from "hono";
import { cors } from "hono/cors";

// The Python read API (serving store seam, §10). Override per environment.
const API_URL = process.env.JP_QUANT_API_URL ?? "http://127.0.0.1:8000";

// Pass the upstream JSON + status through verbatim — the BFF adds typed routes and
// CORS for the SPA, not transformation (no quant logic crosses the seam).
async function proxy(path: string, init?: RequestInit): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}${path}`, init);
  } catch {
    return Response.json({ detail: "serving API unreachable" }, { status: 502 });
  }
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export const app = new Hono();

app.use("/*", cors());
app.get("/health", (c) => c.json({ status: "ok" }));
app.get("/api/factors", () => proxy("/factors"));
app.get("/api/signals", () => proxy("/signals"));
app.get("/api/metrics", () => proxy("/metrics"));
app.get("/api/walk-forward", () => proxy("/walk-forward"));
app.get("/api/crisis", () => proxy("/crisis"));
app.get("/api/bootstrap", (c) => {
  const strategy = c.req.query("strategy");
  const qs = strategy ? `?strategy=${encodeURIComponent(strategy)}` : "";
  return proxy(`/bootstrap${qs}`);
});
app.get("/api/equity", (c) => {
  const strategy = c.req.query("strategy");
  if (!strategy) return c.json({ detail: "strategy required" }, 400);
  return proxy(`/equity?strategy=${encodeURIComponent(strategy)}`);
});
app.post("/api/backtest", async (c) =>
  proxy("/backtest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: await c.req.text(),
  }),
);

export default { port: Number(process.env.PORT ?? 8787), fetch: app.fetch };
