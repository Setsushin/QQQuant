import { getCrisis } from "../api";
import { StrategyCell } from "../components/StrategyCell";
import { num, pct } from "../format";
import { type Lang, useLang } from "../i18n";
import type { CrisisRow } from "../types";
import { Loadable, useFetch } from "../useFetch";

const COPY: Record<Lang, {
  title: string;
  caveat: string;
  synthesized: string;
  synthesizedTip: string;
  head: { strategy: string; cagr: string; afterTax: string; maxDrawdown: string; taxEvents: string };
  tips: { cagr: string; afterTax: string; maxDrawdown: string; taxEvents: string };
}> = {
  en: {
    title: "Crisis case studies",
    caveat:
      "How each strategy fared across a handful of named drawdowns. With only ~5 episodes the sample is tiny — read these case by case, not as out-of-sample evidence.",
    synthesized: "synthesized",
    synthesizedTip:
      "Leveraged returns before the ETF's inception are reconstructed from QQQ + a borrow cost — accuracy is the simulator's, not the market's.",
    head: {
      strategy: "Strategy",
      cagr: "CAGR",
      afterTax: "After-tax CAGR",
      maxDrawdown: "Max drawdown",
      taxEvents: "Tax events / yr",
    },
    tips: {
      cagr: "Compound annual growth rate during the episode.",
      afterTax: "CAGR net of Japan 特定口座 tax on terminal liquidation.",
      maxDrawdown: "Worst peak-to-trough loss during the episode.",
      taxEvents: "Realized-gain events per year during the episode.",
    },
  },
  zh: {
    title: "危机案例研究",
    caveat:
      "各策略在若干具名回撤事件中的表现。仅约 5 个事件、样本极小——请逐例解读，而非当作样本外证据。",
    synthesized: "合成",
    synthesizedTip:
      "杠杆 ETF 在其上市之前的回报，是用 QQQ + 借贷成本重构的——精度取决于模拟器，而非真实市场。",
    head: {
      strategy: "策略",
      cagr: "CAGR",
      afterTax: "税后 CAGR",
      maxDrawdown: "最大回撤",
      taxEvents: "税务事件 / 年",
    },
    tips: {
      cagr: "事件期间的复合年增长率。",
      afterTax: "扣除日本特定口座清算税后的 CAGR。",
      maxDrawdown: "事件期间最严重的峰谷损失。",
      taxEvents: "事件期间每年的已实现收益事件数。",
    },
  },
};

interface Episode {
  name: string;
  start: string;
  end: string;
  qqq_drawdown: number;
  synthesized: boolean;
  rows: CrisisRow[];
}

function groupByEpisode(rows: CrisisRow[]): Episode[] {
  const byName = new Map<string, Episode>();
  for (const r of rows) {
    let ep = byName.get(r.episode);
    if (!ep) {
      ep = {
        name: r.episode,
        start: r.start.slice(0, 10),
        end: r.end.slice(0, 10),
        qqq_drawdown: r.qqq_drawdown,
        synthesized: r.synthesized,
        rows: [],
      };
      byName.set(r.episode, ep);
    }
    ep.rows.push(r);
  }
  return [...byName.values()].sort((a, b) => a.start.localeCompare(b.start));
}

export function CrisisStudies() {
  const t = COPY[useLang().lang];
  const state = useFetch(getCrisis);
  return (
    <section>
      <h2>{t.title}</h2>
      <p className="caveat" role="note">
        {t.caveat}
      </p>
      <Loadable state={state}>
        {(rows) => (
          <>
            {groupByEpisode(rows).map((ep) => (
              <div className="episode" key={ep.name}>
                <h3>
                  {ep.name}{" "}
                  <span className="muted">
                    {ep.start} → {ep.end} · QQQ {pct(ep.qqq_drawdown)}
                  </span>
                  {ep.synthesized && (
                    <span className="badge" title={t.synthesizedTip}>
                      {t.synthesized}
                    </span>
                  )}
                </h3>
                <table>
                  <thead>
                    <tr>
                      <th>{t.head.strategy}</th>
                      <th className="num" title={t.tips.cagr}>
                        {t.head.cagr}
                      </th>
                      <th className="num" title={t.tips.afterTax}>
                        {t.head.afterTax}
                      </th>
                      <th className="num" title={t.tips.maxDrawdown}>
                        {t.head.maxDrawdown}
                      </th>
                      <th className="num" title={t.tips.taxEvents}>
                        {t.head.taxEvents}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ep.rows.map((r) => (
                      <tr key={r.strategy}>
                        <td>
                          <StrategyCell name={r.strategy} />
                        </td>
                        <td className="num">{pct(r.cagr)}</td>
                        <td className="num">{pct(r.cagr_after_tax)}</td>
                        <td className="num">{pct(r.max_drawdown)}</td>
                        <td className="num">{num(r.taxable_events_per_year)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </>
        )}
      </Loadable>
    </section>
  );
}

export { groupByEpisode };
