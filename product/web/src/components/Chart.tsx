import {
  createChart,
  type IChartApi,
  LineSeries,
  type LineData,
  PriceScaleMode,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { LinePoint } from "../format";

export interface ChartSeries {
  data: LinePoint[];
  color: string;
  lineWidth?: 1 | 2 | 3 | 4;
  title?: string;
}

type Scale = "log" | "linear";

interface Props {
  series: ChartSeries[];
  height?: number;
  scale?: Scale;
}

// Log mode silently NaNs the canvas on a single ≤0 value. Bootstrap p5 can dip
// arbitrarily low; clamp instead of dropping points so the x-axis stays consistent
// across percentile lines.
const LOG_FLOOR = 1e-6;

function sanitize(data: LinePoint[], scale: Scale): LineData<Time>[] {
  if (scale === "linear") return data as unknown as LineData<Time>[];
  return data.map((p) => ({
    time: p.time as Time,
    value: p.value > LOG_FLOOR ? p.value : LOG_FLOOR,
  }));
}

/**
 * TradingView Lightweight-Charts (v5) wrapper.
 *
 * Single-effect lifecycle: chart is built, populated, and torn down inside one
 * useEffect. Earlier we split this into three effects (create / scale / series)
 * for hot patches; that introduced implicit ordering between refs and made one
 * panel's crash whitebox the whole tab. The simpler shape relies on the caller
 * memoizing `series` to keep the rebuild cost off the render path, which all
 * three call sites (Distribution fan, BacktestLab result, future curves) already
 * do via useMemo.
 *
 * Log default: wealth curves span orders of magnitude over decades — linear
 * collapses the early period and visually flattens drawdowns. Errors inside the
 * chart library are caught so a future API drift can't blank the tab; an
 * ErrorBoundary higher up catches anything we miss here.
 */
export function Chart({ series, height = 320, scale = "log" }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let chart: IChartApi | null = null;
    try {
      chart = createChart(el, {
        autoSize: true,
        layout: {
          background: { color: "transparent" },
          textColor: "#444",
          attributionLogo: false,
        },
        grid: {
          horzLines: { color: "#eee" },
          vertLines: { color: "#f5f5f5" },
        },
        rightPriceScale: {
          borderColor: "#ddd",
          mode: scale === "log" ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
        },
        timeScale: { borderColor: "#ddd" },
      });

      for (const s of series) {
        const line = chart.addSeries(LineSeries, {
          color: s.color,
          lineWidth: s.lineWidth ?? 2,
          title: s.title,
          priceLineVisible: false,
        });
        line.setData(sanitize(s.data, scale));
      }
      chart.timeScale().fitContent();
    } catch (err) {
      console.error("Chart render failed", err);
      chart?.remove();
      chart = null;
      // Surface a visible marker so the user sees a failure instead of empty space.
      if (el) {
        el.dataset.chartError = err instanceof Error ? err.message : String(err);
      }
      return;
    }

    const created = chart;
    return () => {
      try {
        created.remove();
      } catch (err) {
        console.error("Chart dispose failed", err);
      }
    };
  }, [series, height, scale]);

  return <div ref={ref} data-testid="chart" style={{ height, width: "100%" }} />;
}
