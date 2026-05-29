import { useMemo, useState } from "react";
import { runBacktest } from "../api";
import { Chart, type ChartSeries } from "../components/Chart";
import { equityToLine, num, pct } from "../format";
import { type Lang, useLang } from "../i18n";
import type { BacktestRequest, BacktestResult } from "../types";

type Kind = BacktestRequest["kind"];

const TIER_PRESETS: Record<string, [number, string][]> = {
  "15→QLD": [[0.15, "QLD"]],
  "25→TQQQ": [[0.25, "TQQQ"]],
  "tiered (15→QLD, 25→TQQQ)": [
    [0.15, "QLD"],
    [0.25, "TQQQ"],
  ],
};

// Preset/allocation keys are request identifiers — never translated; only their
// display labels are localized below.
const COPY: Record<Lang, {
  title: string;
  intro: string;
  familyLabel: string;
  family: Record<Kind, string>;
  leveragedLabel: string;
  leveragedTip: string;
  smaLabel: string;
  smaTip: string;
  tiltLabel: string;
  tiltTip: string;
  tierLabels: Record<string, string>;
  cushionLabel: string;
  cushionTip: string;
  guardLabel: string;
  guardTip: string;
  allocLabel: string;
  allocLabels: Record<string, string>;
  runIdle: string;
  runBusy: string;
  stats: { cagr: string; afterTax: string; vol: string; maxDrawdown: string; sharpe: string };
  tips: { cagr: string; afterTax: string; vol: string; maxDrawdown: string; sharpe: string };
}> = {
  en: {
    title: "Backtest lab",
    intro: "Tweak a strategy's parameters and re-run it against the historical price panel.",
    familyLabel: "Strategy family",
    family: {
      drawdown_tilt: "Drawdown tilt",
      sma_switch: "200-day trend switch",
      fixed: "Fixed allocation",
    },
    leveragedLabel: "Leveraged sleeve",
    leveragedTip: "Which leveraged ETF to hold while the trend is up.",
    smaLabel: "SMA window (days)",
    smaTip: "Moving-average window, in trading days.",
    tiltLabel: "Tilt schedule",
    tiltTip: "Drawdown thresholds and the leveraged sleeve they tilt into.",
    tierLabels: {
      "15→QLD": "15→QLD",
      "25→TQQQ": "25→TQQQ",
      "tiered (15→QLD, 25→TQQQ)": "tiered (15→QLD, 25→TQQQ)",
    },
    cushionLabel: "Exit cushion (frac.)",
    cushionTip:
      "Recovery cushion: exit the tilt once drawdown is within this many percent of the high.",
    guardLabel: "200-week MA guard",
    guardTip: "Only tilt while QQQ is above its 200-week moving average.",
    allocLabel: "Allocation",
    allocLabels: { "QQQ 100%": "100% QQQ", "60/40": "60% QQQ / 40% IEF" },
    runIdle: "Run backtest",
    runBusy: "Running…",
    stats: {
      cagr: "CAGR",
      afterTax: "After-tax",
      vol: "Volatility",
      maxDrawdown: "Max drawdown",
      sharpe: "Sharpe",
    },
    tips: {
      cagr: "Compound annual growth rate, pre-tax.",
      afterTax: "CAGR after Japan 特定口座 tax on terminal liquidation.",
      vol: "Annualized standard deviation of monthly returns.",
      maxDrawdown: "Worst peak-to-trough equity loss.",
      sharpe: "Excess return per unit of volatility (annualized).",
    },
  },
  zh: {
    title: "回测台",
    intro: "调整策略参数，在历史价格面板上重新回测。",
    familyLabel: "策略族",
    family: {
      drawdown_tilt: "回撤加仓",
      sma_switch: "200 日趋势切换",
      fixed: "固定配置",
    },
    leveragedLabel: "杠杆仓位",
    leveragedTip: "趋势向上时持有哪只杠杆 ETF。",
    smaLabel: "均线窗口（交易日）",
    smaTip: "移动平均窗口，单位为交易日。",
    tiltLabel: "加仓档位",
    tiltTip: "回撤阈值，以及触发后转向的杠杆仓位。",
    tierLabels: {
      "15→QLD": "15→QLD",
      "25→TQQQ": "25→TQQQ",
      "tiered (15→QLD, 25→TQQQ)": "分档 (15→QLD, 25→TQQQ)",
    },
    cushionLabel: "退出缓冲（小数）",
    cushionTip: "恢复缓冲：当回撤回到距高点该比例以内时退出加仓。",
    guardLabel: "200 周均线闸门",
    guardTip: "仅当 QQQ 在其 200 周均线上方时才加仓。",
    allocLabel: "配置",
    allocLabels: { "QQQ 100%": "100% QQQ", "60/40": "60% QQQ / 40% IEF" },
    runIdle: "运行回测",
    runBusy: "运行中…",
    stats: {
      cagr: "CAGR",
      afterTax: "税后",
      vol: "波动率",
      maxDrawdown: "最大回撤",
      sharpe: "Sharpe",
    },
    tips: {
      cagr: "复合年增长率（税前）。",
      afterTax: "扣除日本特定口座清算税后的 CAGR。",
      vol: "月度收益的年化标准差。",
      maxDrawdown: "最严重的峰谷净值损失。",
      sharpe: "每单位波动率的超额收益（年化）。",
    },
  },
};

export function BacktestLab() {
  const t = COPY[useLang().lang];
  const [kind, setKind] = useState<Kind>("drawdown_tilt");
  const [leveraged, setLeveraged] = useState("TQQQ");
  const [smaWindow, setSmaWindow] = useState(200);
  const [tierPreset, setTierPreset] = useState("tiered (15→QLD, 25→TQQQ)");
  const [recoverWithin, setRecoverWithin] = useState(0.05);
  const [guard, setGuard] = useState(false);
  const [fixedPreset, setFixedPreset] = useState("QQQ 100%");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);

  function buildRequest(): BacktestRequest {
    if (kind === "sma_switch")
      return { kind, name: `SMA${smaWindow}-${leveraged}`, leveraged, sma_window: smaWindow };
    if (kind === "fixed")
      return {
        kind,
        name: fixedPreset,
        weights: fixedPreset === "QQQ 100%" ? { QQQ: 1 } : { QQQ: 0.6, IEF: 0.4 },
      };
    return {
      kind: "drawdown_tilt",
      name: `DD ${tierPreset}`,
      tiers: TIER_PRESETS[tierPreset],
      recover_within: recoverWithin,
      guard_200w: guard,
    };
  }

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await runBacktest(buildRequest()));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2>{t.title}</h2>
      <p className="muted">{t.intro}</p>

      <div className="form">
        <label>
          {t.familyLabel}{" "}
          <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            <option value="drawdown_tilt">{t.family.drawdown_tilt}</option>
            <option value="sma_switch">{t.family.sma_switch}</option>
            <option value="fixed">{t.family.fixed}</option>
          </select>
        </label>

        {kind === "sma_switch" && (
          <>
            <label title={t.leveragedTip}>
              {t.leveragedLabel}{" "}
              <select value={leveraged} onChange={(e) => setLeveraged(e.target.value)}>
                <option value="QLD">QLD (2×)</option>
                <option value="TQQQ">TQQQ (3×)</option>
              </select>
            </label>
            <label title={t.smaTip}>
              {t.smaLabel}{" "}
              <input
                type="number"
                value={smaWindow}
                onChange={(e) => setSmaWindow(Number(e.target.value))}
              />
            </label>
          </>
        )}

        {kind === "drawdown_tilt" && (
          <>
            <label title={t.tiltTip}>
              {t.tiltLabel}{" "}
              <select value={tierPreset} onChange={(e) => setTierPreset(e.target.value)}>
                {Object.keys(TIER_PRESETS).map((k) => (
                  <option key={k} value={k}>
                    {t.tierLabels[k] ?? k}
                  </option>
                ))}
              </select>
            </label>
            <label title={t.cushionTip}>
              {t.cushionLabel}{" "}
              <input
                type="number"
                step="0.01"
                value={recoverWithin}
                onChange={(e) => setRecoverWithin(Number(e.target.value))}
              />
            </label>
            <label className="checkbox" title={t.guardTip}>
              <input type="checkbox" checked={guard} onChange={(e) => setGuard(e.target.checked)} />{" "}
              {t.guardLabel}
            </label>
          </>
        )}

        {kind === "fixed" && (
          <label>
            {t.allocLabel}{" "}
            <select value={fixedPreset} onChange={(e) => setFixedPreset(e.target.value)}>
              <option value="QQQ 100%">{t.allocLabels["QQQ 100%"]}</option>
              <option value="60/40">{t.allocLabels["60/40"]}</option>
            </select>
          </label>
        )}

        <button type="button" onClick={run} disabled={busy}>
          {busy ? t.runBusy : t.runIdle}
        </button>
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && <Result result={result} />}
    </section>
  );
}

function Result({ result }: { result: BacktestResult }) {
  const t = COPY[useLang().lang];
  const m = result.metrics;
  const series = useMemo<ChartSeries[]>(
    () => [
      { data: equityToLine(result.equity_curve), color: "#08519c", lineWidth: 2, title: m.name },
    ],
    [result.equity_curve, m.name],
  );
  return (
    <div data-testid="result">
      <ul className="stats">
        <li title={t.tips.cagr}>
          {t.stats.cagr} <b>{pct(m.cagr)}</b>
        </li>
        <li title={t.tips.afterTax}>
          {t.stats.afterTax} <b>{pct(m.cagr_after_tax)}</b>
        </li>
        <li title={t.tips.vol}>
          {t.stats.vol} <b>{pct(m.ann_vol)}</b>
        </li>
        <li title={t.tips.maxDrawdown}>
          {t.stats.maxDrawdown} <b>{pct(m.max_drawdown)}</b>
        </li>
        <li title={t.tips.sharpe}>
          {t.stats.sharpe} <b>{num(m.sharpe)}</b>
        </li>
      </ul>
      <Chart series={series} />
    </div>
  );
}
