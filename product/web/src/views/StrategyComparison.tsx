import { useMemo, useState } from "react";
import { getMetrics } from "../api";
import { StrategyCell } from "../components/StrategyCell";
import { StrategyDetail } from "../components/StrategyDetail";
import { num, pct, type SortDir, sortBy } from "../format";
import { type Lang, useLang } from "../i18n";
import type { StrategyMetric } from "../types";
import { Loadable, useFetch } from "../useFetch";

const BASELINE_NAME = "B0 QQQ-DCA";

type ColKey =
  | "cagr"
  | "cagr_after_tax"
  | "ann_vol"
  | "max_drawdown"
  | "sharpe"
  | "sortino"
  | "calmar"
  | "tax_drag"
  | "taxable_events_per_year"
  | "pct_months_deviation";

interface ColumnDef {
  key: ColKey;
  fmt: (m: StrategyMetric) => string;
  advanced?: boolean;
}

// Default 5 cover what a reader needs to compare strategies; the rest are
// risk-adjusted/tax detail kept behind a toggle so the table isn't a wall of
// numbers on first view. Labels/tips live in COPY, keyed by column.
const COLUMNS: ColumnDef[] = [
  { key: "cagr", fmt: (m) => pct(m.cagr) },
  { key: "cagr_after_tax", fmt: (m) => pct(m.cagr_after_tax) },
  { key: "ann_vol", fmt: (m) => pct(m.ann_vol) },
  { key: "max_drawdown", fmt: (m) => pct(m.max_drawdown) },
  { key: "sharpe", fmt: (m) => num(m.sharpe) },
  { key: "sortino", fmt: (m) => num(m.sortino), advanced: true },
  { key: "calmar", fmt: (m) => num(m.calmar), advanced: true },
  { key: "tax_drag", fmt: (m) => pct(m.tax_drag, 2), advanced: true },
  { key: "taxable_events_per_year", fmt: (m) => num(m.taxable_events_per_year), advanced: true },
  { key: "pct_months_deviation", fmt: (m) => pct(m.pct_months_deviation, 0), advanced: true },
];

interface Copy {
  title: string;
  intro: string;
  showAdvanced: string;
  strategy: string;
  taxImpactTitle: string;
  taxImpactNote: string;
  columns: Record<ColKey, { label: string; tip: string }>;
}

const COPY: Record<Lang, Copy> = {
  en: {
    title: "Strategy comparison",
    intro:
      "Every strategy receives the same monthly contribution schedule. After-tax figures assume a Japan 特定口座 terminal liquidation at 20.315%. Click a row to see its equity curve against the baseline.",
    showAdvanced: "Show advanced metrics",
    strategy: "Strategy",
    taxImpactTitle: "Pre- vs after-tax CAGR",
    taxImpactNote:
      "The gap is the 特定口座 tax (20.315%) on a single terminal liquidation — wider simply where there's more gain to tax (intra-period switches aren't taxed in this model). The leverage premium has to clear it before it shows up as wealth.",
    columns: {
      cagr: { label: "CAGR", tip: "Compound annual growth rate, pre-tax (time-weighted)." },
      cagr_after_tax: {
        label: "After-tax CAGR",
        tip: "CAGR net of Japan 特定口座 tax on terminal liquidation (20.315%).",
      },
      ann_vol: { label: "Volatility", tip: "Annualized standard deviation of monthly returns." },
      max_drawdown: {
        label: "Max drawdown",
        tip: "Worst peak-to-trough equity loss over the full backtest.",
      },
      sharpe: { label: "Sharpe", tip: "Excess return per unit of total volatility (annualized)." },
      sortino: {
        label: "Sortino",
        tip: "Excess return per unit of downside volatility (annualized).",
      },
      calmar: { label: "Calmar", tip: "CAGR divided by max drawdown." },
      tax_drag: {
        label: "Tax drag",
        tip: "CAGR lost to the 特定口座 tax on a single terminal liquidation (20.315%).",
      },
      taxable_events_per_year: {
        label: "Taxable events / yr",
        tip: "Average number of realized-gain events per year.",
      },
      pct_months_deviation: {
        label: "Months off-allocation",
        tip: "Share of months the strategy held a non-default mix (trend or tilt active).",
      },
    },
  },
  zh: {
    title: "策略对比",
    intro:
      "每个策略都接受相同的月度供款计划。税后数字假设以日本特定口座在 20.315% 清算。点击某行可查看其相对基准的净值曲线。",
    showAdvanced: "显示进阶指标",
    strategy: "策略",
    taxImpactTitle: "税前 vs 税后 CAGR",
    taxImpactNote:
      "这道差距是按期末一次性清算计的特定口座税（20.315%）——收益越多、差距越大（本模型不对中途换仓计税）。杠杆溢价必须先盖过它，才会体现为财富。",
    columns: {
      cagr: { label: "CAGR", tip: "复合年增长率（税前，时间加权）。" },
      cagr_after_tax: {
        label: "税后 CAGR",
        tip: "扣除日本特定口座清算税（20.315%）后的 CAGR。",
      },
      ann_vol: { label: "波动率", tip: "月度收益的年化标准差。" },
      max_drawdown: { label: "最大回撤", tip: "整个回测期内最严重的峰谷净值损失。" },
      sharpe: { label: "Sharpe", tip: "每单位总波动率的超额收益（年化）。" },
      sortino: { label: "Sortino", tip: "每单位下行波动率的超额收益（年化）。" },
      calmar: { label: "Calmar", tip: "CAGR 除以最大回撤。" },
      tax_drag: { label: "税收拖累", tip: "因期末一次性清算缴特定口座税（20.315%）而损失的 CAGR。" },
      taxable_events_per_year: {
        label: "应税事件 / 年",
        tip: "每年已实现收益事件的平均数。",
      },
      pct_months_deviation: {
        label: "偏离配置月份",
        tip: "策略持有非默认组合（趋势或加仓生效）的月份占比。",
      },
    },
  },
};

export function StrategyComparison() {
  const t = COPY[useLang().lang];
  const state = useFetch(getMetrics);
  const [sortKey, setSortKey] = useState<keyof StrategyMetric>("cagr_after_tax");
  const [dir, setDir] = useState<SortDir>("desc");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  function toggle(key: keyof StrategyMetric) {
    if (key === sortKey) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setDir("desc");
    }
  }

  const visible = showAdvanced ? COLUMNS : COLUMNS.filter((c) => !c.advanced);

  return (
    <section>
      <h2>{t.title}</h2>
      <p className="muted">{t.intro}</p>
      <div className="toolbar">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={showAdvanced}
            onChange={(e) => setShowAdvanced(e.target.checked)}
          />{" "}
          {t.showAdvanced}
        </label>
      </div>
      <Loadable state={state}>
        {(metrics) => (
          <ComparisonTable
            metrics={metrics}
            visible={visible}
            sortKey={sortKey}
            dir={dir}
            onSort={toggle}
            expanded={expanded}
            onExpand={(name) => setExpanded((cur) => (cur === name ? null : name))}
          />
        )}
      </Loadable>
    </section>
  );
}

function ComparisonTable({
  metrics,
  visible,
  sortKey,
  dir,
  onSort,
  expanded,
  onExpand,
}: {
  metrics: StrategyMetric[];
  visible: ColumnDef[];
  sortKey: keyof StrategyMetric;
  dir: SortDir;
  onSort: (k: keyof StrategyMetric) => void;
  expanded: string | null;
  onExpand: (name: string) => void;
}) {
  const t = COPY[useLang().lang];
  const rows = sortBy(metrics, sortKey, dir);
  const baseline = useMemo(
    () => metrics.find((m) => m.name === BASELINE_NAME) ?? metrics[0],
    [metrics],
  );
  const colspan = visible.length + 1;
  return (
    <>
      <table>
        <thead>
          <tr>
            <th>{t.strategy}</th>
            {visible.map((c) => (
              <th
                key={c.key}
                className="num sortable"
                title={t.columns[c.key].tip}
                aria-sort={
                  sortKey === c.key ? (dir === "asc" ? "ascending" : "descending") : "none"
                }
                onClick={() => onSort(c.key)}
              >
                {t.columns[c.key].label}
                {sortKey === c.key ? (dir === "asc" ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => {
            const isOpen = expanded === m.name;
            return (
              <Row
                key={m.name}
                metric={m}
                baseline={baseline}
                visible={visible}
                isOpen={isOpen}
                colspan={colspan}
                onExpand={onExpand}
              />
            );
          })}
        </tbody>
      </table>
      <TaxImpact metrics={rows} />
    </>
  );
}

function Row({
  metric,
  baseline,
  visible,
  isOpen,
  colspan,
  onExpand,
}: {
  metric: StrategyMetric;
  baseline: StrategyMetric | undefined;
  visible: ColumnDef[];
  isOpen: boolean;
  colspan: number;
  onExpand: (name: string) => void;
}) {
  return (
    <>
      <tr
        className={`strategy-row ${isOpen ? "open" : ""}`}
        onClick={() => onExpand(metric.name)}
        aria-expanded={isOpen}
      >
        <td>
          <span className="chevron" aria-hidden="true">
            {isOpen ? "▾" : "▸"}
          </span>{" "}
          <StrategyCell name={metric.name} />
        </td>
        {visible.map((c) => (
          <td key={c.key} className="num">
            {c.fmt(metric)}
          </td>
        ))}
      </tr>
      {isOpen && baseline && (
        <tr className="strategy-detail-row">
          <td colSpan={colspan}>
            <StrategyDetail strategy={metric} baseline={baseline} />
          </td>
        </tr>
      )}
    </>
  );
}

// Pre- vs after-tax CAGR — the gap is the tax drag the leverage thesis must clear.
function TaxImpact({ metrics }: { metrics: StrategyMetric[] }) {
  const t = COPY[useLang().lang];
  const max = Math.max(...metrics.map((m) => Math.max(m.cagr, 0)), 0.0001);
  return (
    <div className="tax-impact" data-testid="tax-impact">
      <h3>{t.taxImpactTitle}</h3>
      <p className="muted">{t.taxImpactNote}</p>
      {metrics.map((m) => (
        <div className="bar-row" key={m.name}>
          <span className="bar-label">{m.name}</span>
          <span className="bar-track">
            <span className="bar pre" style={{ width: `${(Math.max(m.cagr, 0) / max) * 100}%` }} />
            <span
              className="bar post"
              style={{ width: `${(Math.max(m.cagr_after_tax, 0) / max) * 100}%` }}
            />
          </span>
          <span className="bar-value mono">
            {pct(m.cagr)} → {pct(m.cagr_after_tax)}
          </span>
        </div>
      ))}
    </div>
  );
}
