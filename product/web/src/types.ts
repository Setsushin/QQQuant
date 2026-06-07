// Contract mirrored across the seam (jp_quant.serving.api / serving tables).

export interface CurrentSignal {
  strategy: string;
  as_of: string;
  target_symbol: string;
  target_weight: number;
  allocation: string;
  qqq_drawdown_52w: number;
  qqq_above_200dma: boolean;
}

// Full §9 metric block per strategy (serving.strategy_metrics).
export interface StrategyMetric {
  name: string;
  cagr: number;
  cagr_after_tax: number;
  total_return: number;
  twr: number;
  mwr: number;
  mwr_after_tax: number;
  ann_vol: number;
  max_drawdown: number;
  max_dd_duration_months: number;
  longest_underwater_months: number;
  worst_rolling_12m: number;
  worst_rolling_36m: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  tax_drag: number;
  taxable_events_per_year: number;
  pct_months_deviation: number;
}

// serving.crisis_case_studies: one row per (episode, strategy).
export interface CrisisRow {
  episode: string;
  start: string;
  end: string;
  qqq_drawdown: number;
  synthesized: boolean;
  strategy: string;
  cagr: number;
  cagr_after_tax: number;
  max_drawdown: number;
  taxable_events_per_year: number;
  pct_months_deviation: number;
}

// serving.bootstrap_percentiles: p5/p50/p95 wealth curve per strategy.
export interface BootstrapPoint {
  strategy: string;
  step: number;
  p5: number;
  p50: number;
  p95: number;
}

export interface BacktestRequest {
  kind?: "fixed" | "sma_switch" | "drawdown_tilt";
  name?: string;
  monthly_amount?: number;
  weights?: Record<string, number>;
  leveraged?: string;
  cash?: string;
  sma_window?: number;
  tiers?: [number, string][];
  recover_within?: number;
  trend_guard?: boolean;
  factors?: FactorSpec;
}

// Factor matrix (serving.api /factors, backtest.factor_matrix). Scope is derived from trigger.
export interface FactorSpec {
  trigger: string;
  ladder: string;
  gate: string;
  exit: string;
}

export interface FactorCell extends FactorSpec {
  scope: string;
  valid: boolean;
  reason: string | null;
  requires: string[];
}

export interface FactorsResponse {
  axes: Record<string, string[]>;
  cells: FactorCell[];
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface BacktestResult {
  metrics: StrategyMetric;
  equity_curve: EquityPoint[];
}

// Per-strategy monthly equity + drawdown curve published from the data plane.
export interface EquityRow {
  date: string;
  equity: number;
  drawdown: number;
}

export interface MarketContext {
  asOf: string;
  drawdownPct: number;
  trend: "above 200DMA" | "below 200DMA";
}

// Market context describes QQQ (identical across rows), so derive once for the header.
export function marketContext(signals: CurrentSignal[]): MarketContext | null {
  const first = signals[0];
  if (!first) return null;
  return {
    asOf: first.as_of.slice(0, 10),
    drawdownPct: first.qqq_drawdown_52w * 100,
    trend: first.qqq_above_200dma ? "above 200DMA" : "below 200DMA",
  };
}
