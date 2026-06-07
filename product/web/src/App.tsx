import { useState } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { type Lang, LangProvider, useLang } from "./i18n";
import { BacktestLab } from "./views/BacktestLab";
import { CrisisStudies } from "./views/CrisisStudies";
import { Distribution } from "./views/Distribution";
import { FactorMatrix } from "./views/FactorMatrix";
import { Findings } from "./views/Findings";
import { SignalPanel } from "./views/SignalPanel";
import { StrategyComparison } from "./views/StrategyComparison";

// Ordered as a derivation: weigh the evidence (broad comparison → crisis stress →
// outcome uncertainty → roll-your-own), then the synthesized verdict, then the
// concrete action it implies.
const TABS = [
  { id: "compare", view: <StrategyComparison /> },
  { id: "crisis", view: <CrisisStudies /> },
  { id: "distribution", view: <Distribution /> },
  { id: "matrix", view: <FactorMatrix /> },
  { id: "lab", view: <BacktestLab /> },
  { id: "findings", view: <Findings /> },
  { id: "signal", view: <SignalPanel /> },
] as const;

type TabId = (typeof TABS)[number]["id"];

// Backtest lab needs live Python compute, which the static GitHub Pages demo can't serve —
// hide that tab there. Default `active` ("compare") survives the filter in both builds.
const STATIC = import.meta.env.VITE_STATIC === "1";
const LIVE_ONLY: ReadonlySet<TabId> = new Set(["lab", "matrix"]);
const VISIBLE_TABS = STATIC ? TABS.filter((tab) => !LIVE_ONLY.has(tab.id)) : TABS;

interface Copy {
  tagline: string;
  toggle: string;
  tabs: Record<TabId, string>;
  retry: string;
  failed: string;
}

const COPY: Record<Lang, Copy> = {
  en: {
    tagline: "leveraged-ETF strategies for a Japan-domiciled investor",
    toggle: "中文",
    tabs: {
      signal: "Signal",
      findings: "Findings",
      compare: "Comparison",
      crisis: "Crisis",
      distribution: "Distribution",
      matrix: "Factor matrix",
      lab: "Backtest lab",
    },
    retry: "Retry",
    failed: "failed to render",
  },
  zh: {
    tagline: "面向日本居住投资者的杠杆 ETF 策略",
    toggle: "English",
    tabs: {
      signal: "信号",
      findings: "结论",
      compare: "对比",
      crisis: "危机",
      distribution: "分布",
      matrix: "因素矩阵",
      lab: "回测台",
    },
    retry: "重试",
    failed: "渲染失败",
  },
};

function Shell() {
  const { lang, setLang } = useLang();
  const t = COPY[lang];
  const [active, setActive] = useState<TabId>("compare");
  const current = VISIBLE_TABS.find((tab) => tab.id === active) ?? TABS[0];

  return (
    <div className="app">
      <header>
        <h1>QQQuant</h1>
        <span className="muted">{t.tagline}</span>
        <button
          type="button"
          className="lang-toggle"
          style={{ marginLeft: "auto" }}
          onClick={() => setLang(lang === "en" ? "zh" : "en")}
        >
          {t.toggle}
        </button>
      </header>
      <nav>
        {VISIBLE_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={tab.id === active ? "active" : ""}
            aria-current={tab.id === active ? "page" : undefined}
            onClick={() => setActive(tab.id)}
          >
            {t.tabs[tab.id]}
          </button>
        ))}
      </nav>
      <main>
        {/* Per-tab boundary: one panel's crash must not blank the shell. Key on the
            active tab so switching tabs resets a previously-tripped boundary. */}
        <ErrorBoundary
          key={current.id}
          label={t.tabs[current.id]}
          retryLabel={t.retry}
          failedText={t.failed}
        >
          {current.view}
        </ErrorBoundary>
      </main>
    </div>
  );
}

export function App() {
  return (
    <LangProvider>
      <Shell />
    </LangProvider>
  );
}
