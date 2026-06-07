import type {
  BacktestRequest,
  BacktestResult,
  BootstrapPoint,
  CrisisRow,
  CurrentSignal,
  EquityRow,
  FactorsResponse,
  StrategyMetric,
} from "./types";

// Empty in dev (Vite proxies /api to the Hono BFF). For the Tauri online client and
// production web, set VITE_API_BASE to the deployed BFF origin at build time.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// Static demo build (GitHub Pages): no BFF/DB — reads come from committed JSON snapshots
// under public/data, exported by jp_quant.serving.export_static. The JSON shapes match the
// live API exactly (same jsonable_encoder), so only the read URL changes.
const STATIC = import.meta.env.VITE_STATIC === "1";
const DATA = `${import.meta.env.BASE_URL}data`;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export const getSignals = (): Promise<CurrentSignal[]> =>
  getJson(STATIC ? `${DATA}/signals.json` : "/api/signals");
export const getMetrics = (): Promise<StrategyMetric[]> =>
  getJson(STATIC ? `${DATA}/metrics.json` : "/api/metrics");
export const getCrisis = (): Promise<CrisisRow[]> =>
  getJson(STATIC ? `${DATA}/crisis.json` : "/api/crisis");

// In static mode the combined files are fetched once and filtered client-side; memoize the
// in-flight promise so concurrent callers (e.g. several Comparison drill-downs) share one fetch.
let bootstrapAll: Promise<BootstrapPoint[]> | null = null;
let equityByStrategy: Promise<Record<string, EquityRow[]>> | null = null;

export const getBootstrap = (strategy?: string): Promise<BootstrapPoint[]> => {
  if (!STATIC)
    return getJson(`/api/bootstrap${strategy ? `?strategy=${encodeURIComponent(strategy)}` : ""}`);
  bootstrapAll ??= getJson<BootstrapPoint[]>(`${DATA}/bootstrap.json`);
  return bootstrapAll.then((rows) =>
    strategy ? rows.filter((r) => r.strategy === strategy) : rows,
  );
};

export const getEquity = (strategy: string): Promise<EquityRow[]> => {
  if (!STATIC) return getJson(`/api/equity?strategy=${encodeURIComponent(strategy)}`);
  equityByStrategy ??= getJson<Record<string, EquityRow[]>>(`${DATA}/equity.json`);
  return equityByStrategy.then((map) => {
    const rows = map[strategy];
    if (!rows) throw new Error(`unknown strategy: ${strategy}`);
    return rows;
  });
};

export const getFactors = (): Promise<FactorsResponse> => getJson("/api/factors");

export async function runBacktest(req: BacktestRequest): Promise<BacktestResult> {
  if (STATIC) throw new Error("Backtest lab runs locally only (no compute in the static demo).");
  const res = await fetch(`${API_BASE}/api/backtest`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`backtest failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as BacktestResult;
}
