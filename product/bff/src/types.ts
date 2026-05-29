// Contract shared across the seam (mirrors jp_quant.serving.api models).
export interface CurrentSignal {
  strategy: string;
  as_of: string;
  target_symbol: string;
  target_weight: number;
  allocation: string;
  qqq_drawdown_52w: number;
  qqq_above_200dma: boolean;
}

// Metric tables are wide and evolve (§9); kept open until the SPA pins columns (P2).
export type MetricRow = Record<string, number | string | boolean | null>;
