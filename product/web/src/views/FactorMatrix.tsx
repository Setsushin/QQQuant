import { useEffect, useMemo, useState } from "react";
import { getFactors, runBacktest } from "../api";
import { Chart, type ChartSeries } from "../components/Chart";
import { equityToLine, num, pct } from "../format";
import { type Lang, useLang } from "../i18n";
import type { BacktestResult, FactorCell, FactorSpec } from "../types";

// Axis order shown top→bottom. Option ids are request identifiers (never translated); their
// display labels are localized below.
const AXIS_ORDER = ["trigger", "ladder", "gate", "exit"] as const;
type Axis = (typeof AXIS_ORDER)[number];

// When the trigger changes, snap the dependent axes to a valid default for that family so the
// user never lands on a dead-end combination.
const INITIAL_SEL: FactorSpec = { trigger: "vix", ladder: "tiered", gate: "200d", exit: "vixcalm" };
const TRIGGER_DEFAULTS: Record<string, FactorSpec> = {
  none: { trigger: "none", ladder: "tiered", gate: "none", exit: "none" },
  trend: { trigger: "trend", ladder: "QLD", gate: "none", exit: "none" },
  drawdown: { trigger: "drawdown", ladder: "tiered", gate: "none", exit: "recovery" },
  vix: INITIAL_SEL,
};

// Which axes apply per trigger; the rest are "not applicable" (a fixed allocation holds QQQ
// outright, a trend switch flips on its own signal — so neither has a gate/exit, and fixed has
// no ladder). Other triggers (drawdown/vix tilts) use all four axes.
const ACTIVE_AXES: Record<string, readonly Axis[]> = {
  none: ["trigger"],
  trend: ["trigger", "ladder"],
};
const activeFor = (trigger: string): readonly Axis[] => ACTIVE_AXES[trigger] ?? AXIS_ORDER;

const COPY: Record<Lang, {
  title: string;
  intro: string;
  axisLabel: Record<Axis, string>;
  option: Record<string, string>;
  desc: Record<string, string>;
  runIdle: string;
  runBusy: string;
  requires: string;
  na: string;
  stats: { cagr: string; afterTax: string; vol: string; maxDrawdown: string; sharpe: string };
}> = {
  en: {
    title: "Factor matrix",
    intro:
      "Compose a strategy from independent factors. Greyed options would make a meaningless combination; the result runs live against the historical panel. To tune continuous parameters (windows, bands, custom tiers), use the Backtest lab tab.",
    axisLabel: { trigger: "Leverage trigger", ladder: "Leverage ladder", gate: "Trend gate", exit: "Exit rule" },
    option: {
      none: "none (buy & hold QQQ)",
      drawdown: "drawdown tier",
      vix: "VIX tier",
      trend: "trend (200-day switch)",
      QQQ: "QQQ (1×, no leverage)",
      QLD: "QLD (2×)",
      TQQQ: "TQQQ (3×)",
      tiered: "tiered (QLD→TQQQ)",
      "200d": "QQQ > 200-day MA",
      recovery: "recovery band",
      time: "time (12 months)",
      never: "never sell",
      vixcalm: "VIX calms",
      trendbreach: "trend breach (de-risk)",
      "gate:none": "none (no gate)",
      "exit:none": "none",
    },
    desc: {
      "trigger:none": "Buy & hold QQQ — no timing, no leverage (the B0 baseline).",
      drawdown:
        "Tilt this month's contribution up the ladder as QQQ's drawdown from its 52-week high deepens (≥15% → QLD, ≥25% → TQQQ).",
      vix: "Tilt this month's contribution up the ladder as the VIX fear gauge rises (≥25 → QLD, ≥35 → TQQQ).",
      trend: "Hold the ladder sleeve while QQQ is above its 200-day MA, else switch the whole stack to cash (SGOV).",
      QQQ: "Unleveraged QQQ — only meaningful for a trend switch (= T3: hold QQQ above the MA, cash below).",
      QLD: "2× leveraged QQQ — the sleeve a cleared trigger buys.",
      TQQQ: "3× leveraged QQQ.",
      tiered: "Tiered: a shallow trigger buys QLD (2×); a deeper one escalates to TQQQ (3×).",
      "gate:none": "No trend gate — leverage is allowed in any regime.",
      "200d": "Allow leverage only while QQQ is above its 200-day MA — a trend safety rail, independent of the trigger.",
      "exit:none": "No explicit exit (implicit for a fixed allocation or a trend switch).",
      recovery: "Convert leverage back to QQQ once QQQ recovers to within 5% of its 52-week high.",
      time: "Convert each leveraged lot back to QQQ after it has been held 12 months, regardless of price.",
      never: "Never sell — stop adding leverage on recovery but let existing lots ride (zero exit turnover).",
      vixcalm: "Convert leverage back to QQQ once VIX falls below 25.",
      trendbreach: "Actively unwind leverage to QQQ when QQQ breaks below its 200-day MA (needs a trend gate).",
    },
    runIdle: "Run backtest",
    runBusy: "Running…",
    requires: "needs",
    na: "— not applicable",
    stats: { cagr: "CAGR", afterTax: "After-tax", vol: "Volatility", maxDrawdown: "Max drawdown", sharpe: "Sharpe" },
  },
  zh: {
    title: "因素矩阵",
    intro:
      "用独立因素组合出一个策略。置灰的选项会构成无意义的组合；结果在历史面板上实时回测。要调整连续参数（窗口、缓冲带、自定义档位），请用回测台页。",
    axisLabel: { trigger: "加杠杆触发", ladder: "杠杆梯", gate: "趋势闸门", exit: "退出规则" },
    option: {
      none: "无（买入持有 QQQ）",
      drawdown: "回撤档",
      vix: "VIX 档",
      trend: "趋势（200 日切换）",
      QQQ: "QQQ（1×，无杠杆）",
      QLD: "QLD（2×）",
      TQQQ: "TQQQ（3×）",
      tiered: "分档（QLD→TQQQ）",
      "200d": "QQQ > 200 日均线",
      recovery: "恢复带",
      time: "时间（12 个月）",
      never: "从不卖出",
      vixcalm: "VIX 回落",
      trendbreach: "破均线（减仓）",
      "gate:none": "无（不设闸门）",
      "exit:none": "无",
    },
    desc: {
      "trigger:none": "买入持有 QQQ，不择时、不加杠杆（基线 B0）。",
      drawdown: "QQQ 较 52 周高点回撤越深，当月供款转向越高的杠杆档（≥15% → QLD，≥25% → TQQQ）。",
      vix: "VIX 恐慌指数越高，当月供款转向越高的杠杆档（≥25 → QLD，≥35 → TQQQ）。",
      trend: "QQQ 在 200 日均线上方持有杠杆梯标的，下方把整仓转为现金（SGOV）。",
      QQQ: "无杠杆 QQQ；只对趋势切换有意义（= T3：均线上方持 QQQ、下方现金）。",
      QLD: "2× 杠杆 QQQ——触发后买入的标的。",
      TQQQ: "3× 杠杆 QQQ。",
      tiered: "分档：浅触发买 QLD（2×），深触发升级到 TQQQ（3×）。",
      "gate:none": "不设趋势闸门——任何市况都允许加杠杆。",
      "200d": "仅当 QQQ 在其 200 日均线上方才允许加杠杆——独立于触发信号的趋势安全栏。",
      "exit:none": "无显式退出（固定配置 / 趋势切换隐含，不单独设）。",
      recovery: "当 QQQ 回升到距 52 周高点 5% 以内时，把杠杆仓换回 QQQ。",
      time: "每笔杠杆仓持有满 12 个月后，无视价格换回 QQQ。",
      never: "从不卖出——恢复后停止加杠杆，但让已有杠杆仓继续跑（零退出换手）。",
      vixcalm: "当 VIX 跌回 25 以下时，把杠杆仓换回 QQQ。",
      trendbreach: "当 QQQ 跌破 200 日均线时，主动平掉杠杆、换回 QQQ（需先设趋势闸门）。",
    },
    runIdle: "运行回测",
    runBusy: "运行中…",
    requires: "需要",
    na: "— 不适用",
    stats: { cagr: "CAGR", afterTax: "税后", vol: "波动率", maxDrawdown: "最大回撤", sharpe: "Sharpe" },
  },
};

const key = (s: FactorSpec): string => `${s.trigger}|${s.ladder}|${s.gate}|${s.exit}`;

export function FactorMatrix() {
  const t = COPY[useLang().lang];
  const [axes, setAxes] = useState<Record<string, string[]> | null>(null);
  const [cellByKey, setCellByKey] = useState<Map<string, FactorCell>>(new Map());
  const [sel, setSel] = useState<FactorSpec>(INITIAL_SEL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);

  useEffect(() => {
    getFactors()
      .then((res) => {
        setAxes(res.axes);
        setCellByKey(new Map(res.cells.map((c) => [key(c), c])));
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const current = cellByKey.get(key(sel)) ?? null;

  // The selection a click on (axis, value) produces. Picking a trigger snaps the dependent axes
  // to a valid default for that family; every other axis is a single-axis swap.
  const nextSel = (axis: Axis, value: string): FactorSpec =>
    axis === "trigger" ? (TRIGGER_DEFAULTS[value] ?? { ...sel, trigger: value }) : { ...sel, [axis]: value };

  function pick(axis: Axis, value: string) {
    setSel(nextSel(axis, value));
  }

  // An option is offered only if the selection it would produce is valid — judged on the *same*
  // resolution pick() applies (so a trigger is judged by its snapped default, not a bare swap that
  // keeps incompatible axes). The current value stays selectable so the control never traps focus.
  const cellFor = (axis: Axis, value: string) => cellByKey.get(key(nextSel(axis, value)));

  // Labels/descriptions prefer an axis-qualified entry (e.g. `gate:none` ≠ `trigger:none`), then
  // fall back to the bare value — so a shared id like "none" reads correctly on each axis.
  const label = (axis: Axis, value: string) => t.option[`${axis}:${value}`] ?? t.option[value] ?? value;
  const optDesc = (axis: Axis, value: string) => t.desc[`${axis}:${value}`] ?? t.desc[value] ?? "";

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await runBacktest({ name: "matrix", factors: sel }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && !axes)
    return (
      <section>
        <h2>{t.title}</h2>
        <p role="alert" className="error">{error}</p>
      </section>
    );

  return (
    <section>
      <h2>{t.title}</h2>
      <p className="muted">{t.intro}</p>

      <div className="factor-matrix">
        {axes &&
          AXIS_ORDER.map((axis) => (
            <div className="factor-axis" key={axis}>
              <span className="factor-axis-label">{t.axisLabel[axis]}</span>
              {activeFor(sel.trigger).includes(axis) ? (
                <div className="factor-options" role="group" aria-label={t.axisLabel[axis]}>
                  {(axes[axis] ?? []).map((value) => {
                    const cell = cellFor(axis, value);
                    const selected = sel[axis] === value;
                    const disabled = !selected && (!cell || !cell.valid);
                    const reqSeries = cell?.requires ?? [];
                    const requires = reqSeries.length ? `${t.requires} ${reqSeries.join(", ")}` : "";
                    const tip = disabled
                      ? (cell?.reason ?? "")
                      : [optDesc(axis, value), requires].filter(Boolean).join(" · ");
                    return (
                      <button
                        type="button"
                        key={value}
                        className={`factor-option${selected ? " selected" : ""}`}
                        aria-pressed={selected}
                        disabled={disabled}
                        title={tip}
                        onClick={() => pick(axis, value)}
                      >
                        {label(axis, value)}
                        {requires && !disabled ? (
                          <sup className="factor-req"> {reqSeries.join(",")}</sup>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <span className="factor-na">{t.na}</span>
              )}
            </div>
          ))}
      </div>

      <button type="button" onClick={run} disabled={busy || !current?.valid}>
        {busy ? t.runBusy : t.runIdle}
      </button>

      {error && axes && <p role="alert" className="error">{error}</p>}
      {result && <Result result={result} />}
    </section>
  );
}

function Result({ result }: { result: BacktestResult }) {
  const t = COPY[useLang().lang];
  const m = result.metrics;
  const series = useMemo<ChartSeries[]>(
    () => [{ data: equityToLine(result.equity_curve), color: "#08519c", lineWidth: 2, title: m.name }],
    [result.equity_curve, m.name],
  );
  return (
    <div data-testid="result">
      <ul className="stats">
        <li>{t.stats.cagr} <b>{pct(m.cagr)}</b></li>
        <li>{t.stats.afterTax} <b>{pct(m.cagr_after_tax)}</b></li>
        <li>{t.stats.vol} <b>{pct(m.ann_vol)}</b></li>
        <li>{t.stats.maxDrawdown} <b>{pct(m.max_drawdown)}</b></li>
        <li>{t.stats.sharpe} <b>{num(m.sharpe)}</b></li>
      </ul>
      <Chart series={series} />
    </div>
  );
}
