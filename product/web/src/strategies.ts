import type { Lang } from "./i18n";

// Plain-language descriptions for the strategy codes the data plane emits.
// Codes (B0/B2/B3/T1/T2/D1–D4) are internal anchors from the spec; the UI
// should always show what they mean. Family stays English — it's a categorical
// tag, not display copy.

export interface StrategyMeta {
  code: string;
  family: "Baseline" | "Trend" | "Drawdown tilt" | "VIX tilt";
  description: string;
}

interface Entry {
  family: StrategyMeta["family"];
  description: Record<Lang, string>;
}

const REGISTRY: Record<string, Entry> = {
  "B0 QQQ-DCA": {
    family: "Baseline",
    description: {
      en: "Buy-and-hold QQQ, monthly contribution.",
      zh: "买入持有 QQQ，按月定投。",
    },
  },
  "B2 TQQQ-DCA": {
    family: "Baseline",
    description: {
      en: "Buy-and-hold TQQQ (3× leveraged QQQ), monthly contribution.",
      zh: "买入持有 TQQQ（3× 杠杆 QQQ），按月定投。",
    },
  },
  "B3 60/40-DCA": {
    family: "Baseline",
    description: {
      en: "60% QQQ / 40% IEF bonds, monthly contribution.",
      zh: "60% QQQ / 40% IEF 债券，按月定投。",
    },
  },
  "B4 QLD-DCA": {
    family: "Baseline",
    description: {
      en: "Buy-and-hold QLD (2× leveraged QQQ), monthly contribution.",
      zh: "买入持有 QLD（2× 杠杆 QQQ），按月定投。",
    },
  },
  "T1 200-SMA-Switch": {
    family: "Trend",
    description: {
      en: "Hold QQQ above the 200-day moving average, cash below.",
      zh: "QQQ 在 200 日均线上方时持有，下方转现金。",
    },
  },
  "T2 200-SMA-QLD": {
    family: "Trend",
    description: {
      en: "Hold QLD (2×) above the 200-day moving average, cash below.",
      zh: "在 200 日均线上方持有 QLD（2×），下方转现金。",
    },
  },
  "T3 200-SMA-QQQ": {
    family: "Trend",
    description: {
      en: "Hold QQQ above the 200-day moving average, cash below.",
      zh: "QQQ 在 200 日均线上方时持有，下方转现金。",
    },
  },
  "D1 Drawdown-15-QLD": {
    family: "Drawdown tilt",
    description: {
      en: "Tilt new contributions into QLD (2×) when QQQ is ≥15% below its 52-week high.",
      zh: "当 QQQ 较 52 周高点回撤 ≥15% 时，把新供款转向 QLD（2×）。",
    },
  },
  "D2 Drawdown-25-TQQQ": {
    family: "Drawdown tilt",
    description: {
      en: "Tilt new contributions into TQQQ (3×) when QQQ is ≥25% below its 52-week high.",
      zh: "当 QQQ 较 52 周高点回撤 ≥25% 时，把新供款转向 TQQQ（3×）。",
    },
  },
  "D3 Tiered": {
    family: "Drawdown tilt",
    description: {
      en: "Two-tier tilt: contributions go to QLD at −15% drawdown, escalate to TQQQ at −25%.",
      zh: "两档加仓：回撤 −15% 时供款转 QLD，−25% 时升级到 TQQQ。",
    },
  },
  "D4 Tiered+200SMA": {
    family: "Drawdown tilt",
    description: {
      en: "Tiered tilt (D3), additionally gated by the 200-day MA to skip down-trending regimes.",
      zh: "分档加仓（D3），并以 200 日均线为闸门，跳过下行趋势。",
    },
  },
  "D5 Tiered+TimeExit12": {
    family: "Drawdown tilt",
    description: {
      en: "Tiered tilt (D3) but each leveraged lot converts back to QQQ after 12 months, regardless of price.",
      zh: "分档加仓（D3），但每笔杠杆持仓满 12 个月后无视价格转回 QQQ。",
    },
  },
  "D6 Tiered+NeverSell": {
    family: "Drawdown tilt",
    description: {
      en: "Tiered tilt (D3) that never sells — it stops adding leverage on recovery but lets the position run.",
      zh: "分档加仓（D3），但从不卖出——恢复后停止加杠杆，让持仓继续跑。",
    },
  },
  "V1 VIX-Tilt": {
    family: "VIX tilt",
    description: {
      en: "Routes the monthly contribution up a leverage ladder by fear gauge: QQQ normally, QLD when VIX ≥ 25, TQQQ when VIX ≥ 35; unwinds when VIX calms.",
      zh: "按恐慌指数把每月供款沿杠杆阶梯递进：平时 QQQ，VIX ≥ 25 转 QLD，VIX ≥ 35 转 TQQQ；VIX 回落时减杠杆。",
    },
  },
  "V2 VIX-Tilt+200SMA": {
    family: "VIX tilt",
    description: {
      en: "Same VIX ladder as V1, but new leverage is blocked while QQQ is below its 200-day MA (existing lots held until VIX calms).",
      zh: "与 V1 相同的 VIX 阶梯，但 QQQ 跌破 200 日均线时禁止新加杠杆（已有仓位等 VIX 回落再退）。",
    },
  },
  "V3 VIX-Tilt+200SMA+DeRisk": {
    family: "VIX tilt",
    description: {
      en: "Like V2, but also actively unwinds leverage to plain QQQ when QQQ breaks below its 200-day MA.",
      zh: "与 V2 相同，但当 QQQ 跌破 200 日均线时还会主动平掉杠杆、回到纯 QQQ。",
    },
  },
};

export function strategyMeta(name: string, lang: Lang = "en"): StrategyMeta {
  const hit = REGISTRY[name];
  if (hit) return { code: name, family: hit.family, description: hit.description[lang] };
  // Unknown strategy (e.g. an ad-hoc Backtest-Lab name). Surface code as-is.
  return { code: name, family: "Baseline", description: "" };
}

export function shortCode(name: string): string {
  // First space-separated token is the spec code (B0/T1/D3/…).
  return name.split(" ", 1)[0] ?? name;
}
