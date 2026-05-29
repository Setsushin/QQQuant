import { getSignals } from "../api";
import { StrategyCell } from "../components/StrategyCell";
import { pct } from "../format";
import { type Lang, useLang } from "../i18n";
import { marketContext } from "../types";
import { Loadable, useFetch } from "../useFetch";

const COPY: Record<Lang, {
  title: string;
  intro: string;
  context: (asOf: string, dd: string, trend: string) => string;
  head: { strategy: string; buy: string; weight: string };
  weightTip: string;
}> = {
  en: {
    title: "Current signal",
    intro: "For each strategy, the symbol and weight the next monthly contribution should buy.",
    context: (asOf, dd, trend) => `QQQ on ${asOf}: ${dd}% from its 52-week high · ${trend}`,
    head: { strategy: "Strategy", buy: "Buy", weight: "Weight" },
    weightTip: "Share of this month's contribution",
  },
  zh: {
    title: "当前信号",
    intro: "对每个策略，下一笔月供应买入的标的与权重。",
    context: (asOf, dd, trend) => `QQQ 截至 ${asOf}：较 52 周高点 ${dd}% · ${trend}`,
    head: { strategy: "策略", buy: "买入", weight: "权重" },
    weightTip: "本月供款的占比",
  },
};

export function SignalPanel() {
  const t = COPY[useLang().lang];
  const state = useFetch(getSignals);
  return (
    <section>
      <h2>{t.title}</h2>
      <p className="muted">{t.intro}</p>
      <Loadable state={state}>
        {(signals) => {
          const ctx = marketContext(signals);
          return (
            <>
              {ctx && (
                <p data-testid="context" className="context">
                  {t.context(ctx.asOf, ctx.drawdownPct.toFixed(1), ctx.trend)}
                </p>
              )}
              <table>
                <thead>
                  <tr>
                    <th>{t.head.strategy}</th>
                    <th>{t.head.buy}</th>
                    <th className="num" title={t.weightTip}>
                      {t.head.weight}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((s) => (
                    <tr key={s.strategy}>
                      <td>
                        <StrategyCell name={s.strategy} />
                      </td>
                      <td className="mono strong">{s.target_symbol}</td>
                      <td className="num">{pct(s.target_weight, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          );
        }}
      </Loadable>
    </section>
  );
}
