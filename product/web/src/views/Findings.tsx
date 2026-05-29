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

// Static, from serving store vintage 2026-05-27 (panel ~2002–2026, after-tax 特定口座).
const ROWS: Row[] = [
  { code: "B0 QQQ-DCA", atax: 0.1527, vsB0: 0, sharpe: 0.796, mdd: -0.534 },
  { code: "B3 60/40-DCA", atax: 0.1257, vsB0: -0.027, sharpe: 0.902, mdd: -0.331 },
  { code: "T2 200-SMA-QLD", atax: 0.1897, vsB0: 0.037, sharpe: 0.688, mdd: -0.545 },
  { code: "T1 200-SMA-Switch", atax: 0.2334, vsB0: 0.081, sharpe: 0.676, mdd: -0.745 },
  { code: "D3 Tiered", atax: 0.1596, vsB0: 0.0069, sharpe: 0.805, mdd: -0.561 },
  { code: "D4 Tiered+200WMA", atax: 0.1519, vsB0: -0.0008, sharpe: 0.789, mdd: -0.549 },
  { code: "B2 TQQQ-DCA", atax: 0.2719, vsB0: 0.119, sharpe: 0.712, mdd: -0.946 },
];

const TOP3 = [
  { medal: "🥇", code: "B0 QQQ-DCA", stat: "15.3% after-tax · Sharpe 0.80 · 0 ops" },
  { medal: "🥈", code: "B3 60/40-DCA", stat: "12.6% after-tax · Sharpe 0.90 · MaxDD −33%" },
  { medal: "🥉", code: "T2 200-SMA-QLD", stat: "19.0% after-tax (+3.7pp) · MaxDD ≈ B0" },
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
      "Data vintage 2026-05-27 · panel ~2002–2026 · after-tax (特定口座 20.315%). Leveraged series before 2010 are synthesized, so quantitative leverage claims lean partly on the simulator (real-data window is 2010+). Effective sample ≈ 5–6 deep-drawdown episodes, not 280+ months — no aggregate claim is statistically powered. After-tax is a simplified single terminal-liquidation model (no intra-year loss-netting/refund, no 3-year carry-forward), so it doesn't fully match real 特定口座 treatment — but the approximation shifts CAGRs by ~1pp and changes neither the rankings nor the verdict.",
    verdictLabel: "Verdict",
    verdict:
      "The headline thesis — tilt monthly contributions into QLD/TQQQ on deep QQQ drawdowns — does not earn its keep. The best variant (D3) beats plain QQQ DCA by only +0.7pp after-tax CAGR and +0.01 Sharpe, with a deeper max drawdown; the guarded D4 underperforms the baseline. Walk-forward shows the edge concentrated in a single out-of-sample window. This is an honest negative result.",
    head: { strat: "Strategy", atax: "After-tax CAGR", vs: "vs B0", sharpe: "Sharpe", mdd: "Max DD" },
    findingsLabel: "What the data says",
    findings: [
      "Drawdown tilt (D1–D4): no robust risk-adjusted, after-tax edge. The tilt only redirects new contributions, so on a 24-year stack it barely moves terminal IRR.",
      "The edge that exists is episode-driven, not systematic — D3 helps in deep V-shaped crashes (2022: 33% vs 15%), but two of four episodes are synthesized and crisis CAGRs are endpoint-inflated.",
      "Naive leverage (B2 TQQQ) has the highest return (27%) but the worst risk-adjusted profile — Sharpe 0.71 < baseline 0.80, −95% drawdown, ~6 years underwater.",
      "Trend-following is more promising than the tilt: T2 adds +3.7pp after-tax CAGR at roughly baseline-level drawdown — though with a 74-month underwater stretch.",
      "Japan tax is not decisive: ~1pp CAGR drag, and it does not change the rankings.",
    ],
    recoLabel: "Top-3 recommendation",
    recoIntro:
      "Ranked by role for a monthly-DCA, real-money, drawdown-aware investor. No active strategy robustly beats B0 on a risk-adjusted, after-tax, executable basis.",
    top3: [
      {
        role: "Core · default",
        why: "The honest winner: built the whole machine, and nothing reliably beats the baseline. Zero ops, near-best Sharpe.",
      },
      {
        role: "Risk-first bucket",
        why: "Best Sharpe / Sortino / Calmar and the shallowest drawdown (−33%). Give up ~2.7pp CAGR for a far smoother ride.",
      },
      {
        role: "Growth satellite · eyes open",
        why: "The one active strategy that earns a place: +3.7pp at baseline-level drawdown. Costs: 74-month underwater, whole-stack rebalance, whipsaw risk; Sharpe still below B0.",
      },
    ],
    avoidLabel: "Not recommended",
    avoid: [
      "Drawdown tilt D1–D4 — marginal, not robust out-of-sample, deeper drawdown (the project's most valuable negative result).",
      "B2 TQQQ-DCA — worst risk-adjusted; a −95% drawdown is unsurvivable.",
      "T1 TQQQ trend — −74% drawdown and ~10 years underwater unless risk tolerance is very high.",
    ],
    todayLabel: "Today",
    today:
      "QQQ at a 52-week high, above the 200-day MA → all drawdown tilts are dormant (buy QQQ as usual); trend strategies are risk-on. No special action for the core.",
    liveNote: "Live per-strategy numbers are on the Comparison tab.",
  },
  zh: {
    title: "杠杆梭哈，还是老实定投？",
    caveat:
      "数据 vintage 2026-05-27 · 面板 ~2002–2026 · 税后（特定口座 20.315%）。杠杆系列 2010 年前为合成数据，杠杆类定量结论部分依赖模拟器（真实数据窗口为 2010 年起）。有效样本 ≈ 5–6 个深度回撤事件，而非 280+ 个月——任何聚合结论都不具统计功效。税后为简化的期末一次性清算模型（未含年内損益通算/還付，也无 3 年亏损繰越），与真实特定口座税制并不完全吻合——但该近似仅使 CAGR 偏移约 1pp，既不改排名也不改结论。",
    verdictLabel: "裁决",
    verdict:
      "核心论点——深度回撤时把月供转向 QLD/TQQQ——并不划算。最优变体（D3）税后 CAGR 仅比纯 QQQ 定投高 0.7pp、Sharpe 高 0.01，且最大回撤更深；带护栏的 D4 反而跑输基准。走查显示这点超额集中在单一样本外窗口。这是一个诚实的负面结果。",
    head: { strat: "策略", atax: "税后 CAGR", vs: "vs B0", sharpe: "Sharpe", mdd: "最大回撤" },
    findingsLabel: "数据说了什么",
    findings: [
      "回撤加仓（D1–D4）：无稳健的风险调整后、税后超额。tilt 只重定向新供款，在 24 年存量上几乎撬不动终值 IRR。",
      "存在的那点超额是事件驱动、非系统性——D3 在深 V 型崩盘里有用（2022：33% vs 15%），但四个案例里两个是合成的，且危机 CAGR 受端点效应放大。",
      "天真上杠杆（B2 TQQQ）回报最高（27%）但风险调整后最差——Sharpe 0.71 < 基准 0.80，回撤 −95%，水下约 6 年。",
      "趋势跟随比 tilt 更有戏：T2 在基准级回撤下多挣 +3.7pp 税后 CAGR——但有 74 个月的水下期。",
      "日本税不是决定因素：约 1pp CAGR 拖累，且不改排名。",
    ],
    recoLabel: "Top-3 推荐",
    recoIntro:
      "按资金角色排序，面向月度定投、真金、回撤敏感的投资者。没有任何主动策略在风险调整 + 税后 + 可执行上稳健胜过 B0。",
    top3: [
      {
        role: "核心 · 默认",
        why: "诚实的赢家：造了整套机器，结论是基准很难被打败。零操作、近最优 Sharpe。",
      },
      {
        role: "风险优先桶",
        why: "Sharpe / Sortino / Calmar 全场最佳、回撤最浅（−33%）。用约 2.7pp CAGR 换大幅更平滑的曲线。",
      },
      {
        role: "卫星增长 · 睁眼上",
        why: "唯一够格的主动策略：基准级回撤下 +3.7pp。代价：水下 74 个月、整存量 rebalance、打脸风险；Sharpe 仍低于 B0。",
      },
    ],
    avoidLabel: "不推荐",
    avoid: [
      "回撤加仓 D1–D4——超额在噪声内、样本外不稳健、回撤更深（本项目最有价值的负面结果）。",
      "B2 TQQQ-DCA——风险调整后最差，−95% 回撤不可承受。",
      "T1 TQQQ 趋势——除非风险偏好极高，否则 −74% 回撤 + 约 10 年水下难以承受。",
    ],
    todayLabel: "当下",
    today:
      "QQQ 处 52 周高点、在 200 日线上方 → 所有回撤 tilt 休眠（照常买 QQQ）；趋势策略 risk-on。核心仓无需动作。",
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
