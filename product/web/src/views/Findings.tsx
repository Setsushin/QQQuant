import { num, pct } from "../format";
import { type Lang, useLang } from "../i18n";

// The Findings page is an editorial conclusion (a writeup), not a live dashboard —
// the Comparison tab already serves live per-strategy numbers. The figures below are
// stamped to a data vintage; prose is bilingual, driven by the app-wide language toggle.

interface Row {
  code: string;
  atax: number; // after-tax CAGR (fraction)
  vsB0: number; // after-tax CAGR delta vs B0 (fraction; 0 for B0 itself)
  sharpe: number;
  mdd: number; // max drawdown (fraction, negative)
}

// Static, from serving store vintage 2026-06-05 (panel ~2002–2026, after-tax 特定口座 with
// interim realized-gain tax + intra-year netting + 3y carry-forward).
const ROWS: Row[] = [
  { code: "B0 QQQ-DCA", atax: 0.1507, vsB0: 0, sharpe: 0.787, mdd: -0.534 },
  { code: "B3 60/40-DCA", atax: 0.1239, vsB0: -0.0268, sharpe: 0.89, mdd: -0.331 },
  { code: "D3 Tiered", atax: 0.1552, vsB0: 0.0045, sharpe: 0.796, mdd: -0.561 },
  { code: "D6 Tiered+NeverSell", atax: 0.2187, vsB0: 0.068, sharpe: 0.749, mdd: -0.686 },
  { code: "V1 VIX-Tilt", atax: 0.1548, vsB0: 0.0042, sharpe: 0.735, mdd: -0.544 },
  { code: "T2 200-SMA-QLD", atax: 0.1462, vsB0: -0.0045, sharpe: 0.668, mdd: -0.559 },
  { code: "T1 200-SMA-Switch", atax: 0.1803, vsB0: 0.0297, sharpe: 0.659, mdd: -0.752 },
  { code: "B2 TQQQ-DCA", atax: 0.2654, vsB0: 0.1147, sharpe: 0.704, mdd: -0.946 },
];

const TOP3 = [
  { medal: "🥇", code: "B0 QQQ-DCA", stat: "15.1% after-tax · Sharpe 0.79 · 0 ops" },
  { medal: "🥈", code: "B3 60/40-DCA", stat: "12.4% after-tax · Sharpe 0.89 · MaxDD −33%" },
  { medal: "🥉", code: "D6 Tiered+NeverSell", stat: "21.9% after-tax (+6.8pp) · MaxDD −69% · 0 sells" },
];

interface Copy {
  title: string;
  caveat: string;
  verdictLabel: string;
  verdict: string;
  head: { strat: string; atax: string; vs: string; sharpe: string; mdd: string };
  findingsLabel: string;
  findings: string[];
  recoLabel: string;
  recoIntro: string;
  top3: { role: string; why: string }[];
  avoidLabel: string;
  avoid: string[];
  todayLabel: string;
  today: string;
  liveNote: string;
}

const COPY: Record<Lang, Copy> = {
  en: {
    title: "Lever up, or just DCA?",
    caveat:
      "Data vintage 2026-06-05 · panel ~2002–2026 (it starts at IEF's 2002 inception, so the 2000–02 dot-com crash is largely outside the window) · after-tax (特定口座 20.315%). Leveraged series before 2010 are synthesized, so quantitative leverage claims lean partly on the simulator (real-data window is 2010+). Effective sample ≈ 5–6 deep-drawdown episodes, not 280+ months — no aggregate claim is statistically powered. After-tax now models 特定口座 properly: realized gains are taxed as they occur, with intra-year loss-netting and a 3-year carry-forward, plus a terminal liquidation — so tax scales with turnover and does move the rankings (high-churn strategies fall).",
    verdictLabel: "Verdict",
    verdict:
      "The headline thesis — tilt monthly contributions into QLD/TQQQ on deep QQQ drawdowns — still does not earn its keep: the best exit-bearing variant (D3) beats plain QQQ DCA by only +0.4pp after-tax. And once interim switches are taxed correctly, the trend-following edge largely evaporates — T2 (200-SMA-QLD) now trails the QQQ baseline after-tax, and T1's remaining edge rides a −75% drawdown. Nothing beats buy-and-hold by timing; the only strategies that clear B0 do so by holding more leverage (B2/B4) or never selling it (D6). An honest negative result for market-timing.",
    head: { strat: "Strategy", atax: "After-tax CAGR", vs: "vs B0", sharpe: "Sharpe", mdd: "Max DD" },
    findingsLabel: "What the data says",
    findings: [
      "Drawdown tilt with an exit (D1–D5): no robust after-tax edge — D3/D5 add ~+0.4pp, inside the noise of ~5–6 episodes, and the 200-day-guarded D4 is flat. Redirecting only new contributions barely moves a 24-year stack.",
      "Trend-following's apparent edge was a tax-model artifact: taxing its ~1.6 switches/year correctly costs ~4pp of after-tax CAGR, so T2 now trails B0 (−0.4pp) and T1's remaining +3.0pp comes with a −75% drawdown and ~10 years underwater.",
      "The only strategies that beat B0 after-tax do it with leverage, not timing: B2 TQQQ +11.5pp (−95% DD), B4 QLD +7.8pp (−83% DD), D6 +6.8pp (−69% DD) — each buys return with a far deeper drawdown (risk reallocation, not free alpha).",
      "The one tilt variant that earns its place is D6 (never-sell): by never realizing a gain it defers all tax and lets the drawdown-bought leverage ride (+6.8pp, zero taxable events) — but that makes it a tax-efficient leverage accumulator, not a timing strategy, and its drawdown is −69%.",
      "VIX tilts (V1–V3) sit on the baseline (+0.0 to +0.4pp): fear-spike timing adds no after-tax edge, and the 200-day-gated V2/V3 are indistinguishable from B0 (the gate filters out almost all the leverage).",
      "Japan tax is decisive through turnover: ~1pp drag for buy-and-hold, but 2.4–4.7pp for the trend switches — enough to flip T2 below the baseline. Tax changes the rankings.",
    ],
    recoLabel: "Top-3 recommendation",
    recoIntro:
      "Ranked by role for a monthly-DCA, real-money, drawdown-aware investor. No timing strategy robustly beats B0 on a risk-adjusted, after-tax, executable basis; the higher-return picks simply take on more risk.",
    top3: [
      {
        role: "Core · default",
        why: "The honest winner: built the whole machine, and nothing reliably beats the baseline by timing. Zero ops, near-best Sharpe.",
      },
      {
        role: "Risk-first bucket",
        why: "Best Sharpe (0.89) and the shallowest drawdown (−33%). Give up ~2.7pp CAGR for a far smoother ride.",
      },
      {
        role: "Growth satellite · eyes open",
        why: "The one active variant that clears B0 after-tax (+6.8pp) — by never selling, it pays no interim tax and lets drawdown-bought leverage compound. Costs: a −69% drawdown, and the edge is deferral + leverage, not timing alpha. Size it small.",
      },
    ],
    avoidLabel: "Not recommended",
    avoid: [
      "Drawdown tilt with active exits (D1–D5) — marginal, not robust out-of-sample, deeper drawdown (the project's most valuable negative result).",
      "Trend switches T1/T2/T3 — taxing the turnover correctly sinks T2/T3 to or below the baseline, and T1's edge needs a −75% drawdown and ~10 years underwater.",
      "B2 TQQQ-DCA — highest return but worst risk-adjusted; a −95% drawdown is unsurvivable.",
    ],
    todayLabel: "Today",
    today:
      "After the 2026-06-05 selloff QQQ is ~5.5% off its 52-week high and still above the 200-day MA, with VIX ~21 (below the 25 tilt trigger) → all drawdown and VIX tilts are dormant (buy QQQ as usual), trend strategies still risk-on. No special action for the core.",
    liveNote: "Live per-strategy numbers are on the Comparison tab.",
  },
  zh: {
    title: "杠杆梭哈，还是老实定投？",
    caveat:
      "数据 vintage 2026-06-05 · 面板 ~2002–2026（起点是 IEF 的 2002 年上市，故 2000–02 dotcom 崩盘基本在窗口外）· 税后（特定口座 20.315%）。杠杆系列 2010 年前为合成数据，杠杆类定量结论部分依赖模拟器（真实数据窗口为 2010 年起）。有效样本 ≈ 5–6 个深度回撤事件，而非 280+ 个月——任何聚合结论都不具统计功效。税后现已正确建模特定口座：已实现收益随发生即课税，含年内損益通算与 3 年亏损繰越，再加期末清算——所以税随换手率放大，且确实会改变排名（高换手策略下滑）。",
    verdictLabel: "裁决",
    verdict:
      "核心论点——深度回撤时把月供转向 QLD/TQQQ——仍不划算：带退出的最优变体（D3）税后仅比纯 QQQ 定投高 +0.4pp。而一旦把中途换仓正确计税，趋势跟随的超额基本蒸发——T2（200-SMA-QLD）税后已跌破 QQQ 基线，T1 仅剩的优势骑在 −75% 回撤上。没有任何策略靠择时打败买入持有；能盖过 B0 的，都是靠多扛杠杆（B2/B4）或从不卖出（D6）。对择时而言，这是一个诚实的负面结果（an honest negative result）。",
    head: { strat: "策略", atax: "税后 CAGR", vs: "vs B0", sharpe: "Sharpe", mdd: "最大回撤" },
    findingsLabel: "数据说了什么",
    findings: [
      "带退出的回撤加仓（D1–D5）：无稳健的税后超额——D3/D5 仅 +0.4pp，落在 ~5–6 个事件的噪声里；带 200 日护栏的 D4 基本持平。只重定向新供款，在 24 年存量上几乎撬不动。",
      "趋势跟随的表面超额是税模型假象：把它每年 ~1.6 次换仓正确计税会吃掉约 4pp 税后 CAGR——于是 T2 反跌破 B0（−0.4pp），T1 仅剩的 +3.0pp 还附带 −75% 回撤、约 10 年水下。",
      "能税后盖过 B0 的，都是靠杠杆而非择时：B2 TQQQ +11.5pp（−95% 回撤）、B4 QLD +7.8pp（−83%）、D6 +6.8pp（−69%）——都是用更深的回撤换回报（风险重配置，非免费 alpha）。",
      "唯一够格的 tilt 变体是 D6（从不卖出）：靠从不实现收益来递延全部税、让回撤期买入的杠杆一路跑（+6.8pp、零应税事件）——但这使它成了税务高效的『杠杆累积器』，而非择时策略，且回撤 −69%。",
      "VIX tilt（V1–V3）贴着基线（+0.0~+0.4pp）：恐慌择时没带来税后超额；带 200 日闸门的 V2/V3 与 B0 几乎无异（闸门把杠杆基本滤掉了）。",
      "日本税通过换手率起决定作用：买入持有约 1pp，趋势切换却 2.4–4.7pp——足以把 T2 压到基线之下。税会改变排名。",
    ],
    recoLabel: "Top-3 推荐",
    recoIntro:
      "按资金角色排序，面向月度定投、真金、回撤敏感的投资者。没有任何择时策略在风险调整 + 税后 + 可执行上稳健胜过 B0；回报更高的几个只是承担了更多风险。",
    top3: [
      {
        role: "核心 · 默认",
        why: "诚实的赢家：造了整套机器，结论是择时打不过基准。零操作、近最优 Sharpe。",
      },
      {
        role: "风险优先桶",
        why: "Sharpe 最佳（0.89）、回撤最浅（−33%）。用约 2.7pp CAGR 换大幅更平滑的曲线。",
      },
      {
        role: "卫星增长 · 睁眼上",
        why: "唯一税后盖过 B0 的主动变体（+6.8pp）——靠从不卖出，不缴中途税、让回撤期买入的杠杆复利。代价：−69% 回撤，且超额来自递延 + 杠杆而非择时 alpha。小仓位为宜。",
      },
    ],
    avoidLabel: "不推荐",
    avoid: [
      "带主动退出的回撤加仓 D1–D5——超额在噪声内、样本外不稳健、回撤更深（本项目最有价值的负面结果）。",
      "趋势切换 T1/T2/T3——把换手正确计税后，T2/T3 跌到基线或之下，T1 的优势需要 −75% 回撤 + 约 10 年水下。",
      "B2 TQQQ-DCA——回报最高但风险调整后最差，−95% 回撤不可承受。",
    ],
    todayLabel: "当下",
    today:
      "2026-06-05 抛售后，QQQ 距 52 周高点约 −5.5%、仍在 200 日线上方，VIX ~21（低于 25 加仓阈值）→ 所有回撤 / VIX tilt 休眠（照常买 QQQ），趋势策略仍 risk-on。核心仓无需动作。",
    liveNote: "各策略的实时数字见 Comparison 标签页。",
  },
};

const ppDelta = (x: number): string => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}pp`;

export function Findings() {
  const t = COPY[useLang().lang];
  return (
    <section className="findings">
      <h2>{t.title}</h2>
      <p className="caveat" role="note">
        {t.caveat}
      </p>

      <p className="context">
        <span className="strong">{t.verdictLabel}: </span>
        {t.verdict}
      </p>

      <table>
        <thead>
          <tr>
            <th>{t.head.strat}</th>
            <th className="num">{t.head.atax}</th>
            <th className="num">{t.head.vs}</th>
            <th className="num">{t.head.sharpe}</th>
            <th className="num">{t.head.mdd}</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.code}>
              <td>{r.code}</td>
              <td className="num">{pct(r.atax)}</td>
              <td className="num">{r.vsB0 === 0 ? "—" : ppDelta(r.vsB0)}</td>
              <td className="num">{num(r.sharpe)}</td>
              <td className="num">{pct(r.mdd)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>{t.findingsLabel}</h3>
      <ul>
        {t.findings.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>

      <h3>{t.recoLabel}</h3>
      <p className="muted">{t.recoIntro}</p>
      <div className="reco-list">
        {TOP3.map((r, i) => (
          <div className="reco" key={r.code}>
            <div className="reco-rank">{r.medal}</div>
            <div>
              <div className="reco-head">
                <span className="strong">{r.code}</span>
                <span className="reco-role">{t.top3[i]!.role}</span>
                <span className="reco-stat">{r.stat}</span>
              </div>
              <p className="reco-why">{t.top3[i]!.why}</p>
            </div>
          </div>
        ))}
      </div>

      <h3>{t.avoidLabel}</h3>
      <ul>
        {t.avoid.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>

      <p className="context">
        <span className="strong">{t.todayLabel}: </span>
        {t.today}
      </p>
      <p className="muted">{t.liveNote}</p>
    </section>
  );
}
