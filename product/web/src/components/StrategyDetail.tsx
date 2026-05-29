import { useMemo } from "react";
import { getEquity } from "../api";
import { type Lang, useLang } from "../i18n";
import type { StrategyMetric } from "../types";
import { Loadable, useFetch } from "../useFetch";
import { Chart, type ChartSeries } from "./Chart";

const BASELINE_COLOR = "#9ca3af";
const STRATEGY_COLOR = "#08519c";
const DRAWDOWN_COLOR = "#b91c1c";

interface Pair {
  strategy: { time: string; value: number }[];
  baseline: { time: string; value: number }[];
  drawdownStrategy: { time: string; value: number }[];
  drawdownBaseline: { time: string; value: number }[];
}

function toLines(
  rows: { date: string; equity: number; drawdown: number }[],
): { eq: { time: string; value: number }[]; dd: { time: string; value: number }[] } {
  const eq: { time: string; value: number }[] = [];
  const dd: { time: string; value: number }[] = [];
  for (const r of rows) {
    const time = r.date.slice(0, 10);
    eq.push({ time, value: r.equity });
    dd.push({ time, value: r.drawdown });
  }
  return { eq, dd };
}

/**
 * Two-chart drill-down for a single strategy: log equity curve (with B0 baseline
 * overlaid) and a linear drawdown ribbon. Narrative is mechanically derived from
 * the metrics — no marketing language; both sides of the trade-off show up.
 */
export function StrategyDetail({
  strategy,
  baseline,
}: {
  strategy: StrategyMetric;
  baseline: StrategyMetric;
}) {
  const sameAsBaseline = strategy.name === baseline.name;
  const state = useFetch<Pair>(
    async () => {
      const [s, b] = sameAsBaseline
        ? await Promise.all([getEquity(strategy.name), Promise.resolve(null)])
        : await Promise.all([getEquity(strategy.name), getEquity(baseline.name)]);
      const sl = toLines(s);
      const bl = b ? toLines(b) : { eq: [], dd: [] };
      return {
        strategy: sl.eq,
        baseline: bl.eq,
        drawdownStrategy: sl.dd,
        drawdownBaseline: bl.dd,
      };
    },
    [strategy.name, baseline.name],
  );

  const lines = narrative(strategy, baseline, useLang().lang);

  return (
    <div className="strategy-detail">
      <p className="strategy-narrative">
        {lines.map((line, i) => (
          <span key={i}>
            {line}
            {i < lines.length - 1 && <br />}
          </span>
        ))}
      </p>
      <Loadable state={state}>
        {(data) => <Charts data={data} sameAsBaseline={sameAsBaseline} baselineName={baseline.name} strategyName={strategy.name} />}
      </Loadable>
    </div>
  );
}

function Charts({
  data,
  sameAsBaseline,
  baselineName,
  strategyName,
}: {
  data: Pair;
  sameAsBaseline: boolean;
  baselineName: string;
  strategyName: string;
}) {
  const equity = useMemo<ChartSeries[]>(() => {
    const series: ChartSeries[] = [];
    if (!sameAsBaseline) {
      series.push({ data: data.baseline, color: BASELINE_COLOR, lineWidth: 1, title: baselineName });
    }
    series.push({ data: data.strategy, color: STRATEGY_COLOR, lineWidth: 2, title: strategyName });
    return series;
  }, [data, sameAsBaseline, baselineName, strategyName]);

  const drawdown = useMemo<ChartSeries[]>(() => {
    const series: ChartSeries[] = [];
    if (!sameAsBaseline) {
      series.push({
        data: data.drawdownBaseline,
        color: BASELINE_COLOR,
        lineWidth: 1,
        title: baselineName,
      });
    }
    series.push({
      data: data.drawdownStrategy,
      color: DRAWDOWN_COLOR,
      lineWidth: 2,
      title: strategyName,
    });
    return series;
  }, [data, sameAsBaseline, baselineName, strategyName]);

  const t = CHART_COPY[useLang().lang];
  return (
    <div className="strategy-detail-charts">
      <div>
        <h4>{t.equity}</h4>
        <Chart series={equity} height={260} scale="log" />
      </div>
      <div>
        <h4>{t.drawdown}</h4>
        <Chart series={drawdown} height={140} scale="linear" />
      </div>
    </div>
  );
}

const CHART_COPY: Record<Lang, { equity: string; drawdown: string }> = {
  en: { equity: "Equity (log)", drawdown: "Drawdown" },
  zh: { equity: "净值（对数）", drawdown: "回撤" },
};

const pp = (x: number): string => {
  const v = x * 100;
  return v >= 0 ? `+${v.toFixed(1)}pp` : `${v.toFixed(1)}pp`;
};

/**
 * Mechanically derived 1–3 sentences comparing the strategy to the baseline.
 * No editorializing — gains and costs both surface so a viewer can decide
 * whether the trade-off matches their preference.
 */
export function narrative(s: StrategyMetric, b: StrategyMetric, lang: Lang = "en"): string[] {
  const dAfterTax = s.cagr_after_tax - b.cagr_after_tax;
  const dMaxDD = s.max_drawdown - b.max_drawdown; // both negative; more negative = deeper
  const deeper = s.max_drawdown < b.max_drawdown;
  const events = s.taxable_events_per_year.toFixed(2);
  const baseEvents = b.taxable_events_per_year.toFixed(2);
  const drag = (s.tax_drag * 100).toFixed(2);
  const offMix = (s.pct_months_deviation * 100).toFixed(0);
  if (lang === "zh") {
    if (s.name === b.name) return ["基准。其他所有策略都以此行为参照。"];
    return [
      `税后 CAGR ${pp(dAfterTax)}（vs ${b.name}）；最大回撤 ${pp(dMaxDD)}（${deeper ? "更深" : "更浅"}）。`,
      `每年 ${events} 次应税事件（基准 ${baseEvents}）；税收拖累为 CAGR 的 ${drag}%。`,
      `${offMix}% 的月份偏离默认配置。`,
    ];
  }
  if (s.name === b.name) {
    return ["Baseline. Every other strategy is compared against this row."];
  }
  return [
    `After-tax CAGR ${pp(dAfterTax)} vs ${b.name}; max drawdown ${pp(dMaxDD)} (${deeper ? "deeper" : "shallower"}).`,
    `${events} taxable events / yr (baseline ${baseEvents}); tax drag ${drag}% of CAGR.`,
    `Off the default mix ${offMix}% of months.`,
  ];
}
