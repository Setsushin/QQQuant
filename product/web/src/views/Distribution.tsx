import { useMemo, useState } from "react";
import { getBootstrap, getMetrics } from "../api";
import { Chart, type ChartSeries } from "../components/Chart";
import { bootstrapFan } from "../format";
import { type Lang, useLang } from "../i18n";
import { strategyMeta } from "../strategies";
import type { BootstrapPoint } from "../types";
import { Loadable, useFetch } from "../useFetch";

const COPY: Record<Lang, {
  title: string;
  caveat: { pre: string; floor: string; post: string };
  strategy: string;
}> = {
  en: {
    title: "Outcome distribution",
    caveat: {
      pre: "Same monthly returns, replayed in randomized blocks to show how much luck of timing matters. The dark line is the median outcome; the shaded band is the 5th–95th percentile range. Block resampling softens drawdown clustering, so treat this as a ",
      floor: "floor",
      post: " on dispersion, not a forecast.",
    },
    strategy: "Strategy",
  },
  zh: {
    title: "结果分布",
    caveat: {
      pre: "相同的月度收益，以随机区块重排，展示择时运气的影响有多大。深色线是中位结果；阴影带是 5–95 百分位区间。区块重采样会弱化回撤聚集，因此请把它视作离散度的",
      floor: "下限",
      post: "，而非预测。",
    },
    strategy: "策略",
  },
};

export function Distribution() {
  const { lang } = useLang();
  const t = COPY[lang];
  const metrics = useFetch(getMetrics);
  const [strategy, setStrategy] = useState<string | null>(null);

  return (
    <section>
      <h2>{t.title}</h2>
      <p className="caveat" role="note">
        {t.caveat.pre}
        <em>{t.caveat.floor}</em>
        {t.caveat.post}
      </p>
      <Loadable state={metrics}>
        {(rows) => {
          const names = rows.map((r) => r.name);
          const selected = strategy ?? names[0] ?? null;
          const meta = selected ? strategyMeta(selected, lang) : null;
          return (
            <>
              <label>
                {t.strategy}{" "}
                <select value={selected ?? ""} onChange={(e) => setStrategy(e.target.value)}>
                  {names.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              {meta?.description && <p className="muted strategy-desc-inline">{meta.description}</p>}
              {selected && <Fan strategy={selected} />}
            </>
          );
        }}
      </Loadable>
    </section>
  );
}

function Fan({ strategy }: { strategy: string }) {
  const state = useFetch(() => getBootstrap(strategy), [strategy]);
  return <Loadable state={state}>{(points) => <FanChart points={points} />}</Loadable>;
}

function FanChart({ points }: { points: BootstrapPoint[] }) {
  const series = useMemo<ChartSeries[]>(() => {
    const fan = bootstrapFan(points);
    return [
      { data: fan.p95, color: "#9ecae1", lineWidth: 1, title: "p95" },
      { data: fan.p50, color: "#08519c", lineWidth: 3, title: "p50" },
      { data: fan.p5, color: "#9ecae1", lineWidth: 1, title: "p5" },
    ];
  }, [points]);
  return <Chart series={series} />;
}
