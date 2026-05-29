import type { Lang } from "./i18n";

// Plain-language descriptions for the strategy codes the data plane emits.
// Codes (B0/B2/B3/T1/T2/D1–D4) are internal anchors from the spec; the UI
// should always show what they mean. Family stays English — it's a categorical
// tag, not display copy.

export interface StrategyMeta {
  code: string;
  family: "Baseline" | "Trend" | "Drawdown tilt";
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
  "D4 Tiered+200WMA": {
    family: "Drawdown tilt",
    description: {
      en: "Tiered tilt (D3), additionally gated by the 200-week MA to skip structurally bearish regimes.",
      zh: "分档加仓（D3），并以 200 周均线为闸门，跳过结构性熊市。",
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
