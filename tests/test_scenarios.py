import numpy as np
import pandas as pd

from jp_quant.backtest.engine import month_end_trade_dates, monthly_contributions, run_backtest
from jp_quant.backtest.scenarios import (
    CRISIS_EPISODES,
    bootstrap_equity_percentiles,
    crisis_case_studies,
    monthly_twr_returns,
    stationary_bootstrap_indices,
)
from jp_quant.backtest.strategies import B0_QQQ_DCA, D3_TIERED


def _long_panel() -> pd.DataFrame:
    idx = pd.bdate_range("1999-01-04", "2022-12-30")
    n = len(idx)
    ret = np.full(n, 0.0004)
    ret[0] = 0.0
    # carve crashes into the dotcom and covid windows
    dotcom = (idx >= pd.Timestamp("2000-03-01")) & (idx <= pd.Timestamp("2002-10-31"))
    covid = (idx >= pd.Timestamp("2020-02-15")) & (idx <= pd.Timestamp("2020-03-31"))
    ret[dotcom.nonzero()[0][:120]] = -0.004
    ret[covid] = -0.03
    qqq_ret = pd.Series(ret, index=idx)

    def lev(mult: float) -> np.ndarray:
        return 100.0 * np.cumprod(1.0 + (mult * qqq_ret).to_numpy())

    return pd.DataFrame(
        {
            "QQQ": 100.0 * np.cumprod(1.0 + ret),
            "QLD": lev(2.0),
            "TQQQ": lev(3.0),
            "SGOV": 100.0 * np.cumprod(1.0 + np.full(n, 2e-5)),
            "IEF": 100.0 * np.cumprod(1.0 + np.full(n, 1e-4)),
        },
        index=idx,
    )


def test_crisis_case_studies_flags_synthesized_and_captures_drawdown() -> None:
    panel = _long_panel()
    cs = crisis_case_studies(panel, [B0_QQQ_DCA, D3_TIERED])

    assert set(cs["episode"]) == {e.name for e in CRISIS_EPISODES}
    assert (cs["qqq_drawdown"] <= 0).all()
    # pre-2010 episodes lean on synthesized leverage (§7.4); later ones do not
    flags = cs.drop_duplicates("episode").set_index("episode")["synthesized"]
    assert bool(flags["dotcom"]) and bool(flags["gfc"])
    assert not bool(flags["covid"]) and not bool(flags["rate-shock-2022"])
    # the metric block rode along
    assert "cagr_after_tax" in cs.columns and cs["cagr"].notna().all()


def test_stationary_bootstrap_indices_shape_and_range() -> None:
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(50, 200, 18.0, rng)
    assert idx.shape == (200,)
    assert idx.min() >= 0 and idx.max() < 50


def test_bootstrap_percentiles_ordered_and_deterministic() -> None:
    panel = _long_panel()
    contribs = monthly_contributions(month_end_trade_dates(panel), 100_000.0)
    res = run_backtest(panel, contribs, B0_QQQ_DCA)
    monthly = monthly_twr_returns(res.equity_curve, contribs)

    a = bootstrap_equity_percentiles(monthly, n_paths=200, horizon=120, seed=7)
    b = bootstrap_equity_percentiles(monthly, n_paths=200, horizon=120, seed=7)
    pd.testing.assert_frame_equal(a, b)  # deterministic given seed
    assert list(a.columns) == ["p5", "p50", "p95"]
    assert len(a) == 120
    last = a.iloc[-1]
    assert last["p5"] <= last["p50"] <= last["p95"]
