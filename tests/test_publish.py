import json
from pathlib import Path

import numpy as np
import pandas as pd

from jp_quant.backtest.strategies import B0_QQQ_DCA, T1_SMA_TQQQ
from jp_quant.serving.publish import (
    build_serving_tables,
    current_signals,
    publish,
)


def _panel() -> pd.DataFrame:
    idx = pd.bdate_range("2012-01-03", "2022-12-30")
    n = len(idx)
    ret = np.full(n, 0.0005)
    ret[0] = 0.0
    ret[1200:1240] = -0.02
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


def test_current_signals_target_is_in_universe() -> None:
    panel = _panel()
    sig = current_signals(panel, [B0_QQQ_DCA, T1_SMA_TQQQ])
    assert len(sig) == 2
    assert set(sig["target_symbol"]).issubset(set(panel.columns))
    # B0 always targets QQQ; the trend strategy targets its sleeve or cash
    b0 = sig.set_index("strategy").loc["B0 QQQ-DCA"]
    assert b0["target_symbol"] == "QQQ"
    assert json.loads(str(b0["allocation"])) == {"QQQ": 1.0}


def test_build_serving_tables_has_expected_nonempty_tables() -> None:
    panel = _panel()
    tables = build_serving_tables(
        panel, strategies=[B0_QQQ_DCA, T1_SMA_TQQQ], n_windows=2, bootstrap_paths=50
    )
    expected = {
        "strategy_metrics",
        "strategy_equity",
        "walk_forward",
        "crisis_case_studies",
        "bootstrap_percentiles",
        "current_signal",
    }
    assert set(tables) == expected
    assert all(not df.empty for df in tables.values())
    assert {"p5", "p50", "p95"}.issubset(tables["bootstrap_percentiles"].columns)
    equity = tables["strategy_equity"]
    assert {"strategy", "date", "equity", "drawdown"} <= set(equity.columns)
    # Drawdown is by construction non-positive.
    assert equity["drawdown"].max() <= 1e-12
    # Both strategies must be present and yield positive equity (monthly contributions).
    assert set(equity["strategy"].unique()) == {"B0 QQQ-DCA", "T1 200-SMA-Switch"}
    assert (equity["equity"] > 0).all()


def test_publish_round_trips_through_duckdb(tmp_path: Path) -> None:
    import duckdb

    panel = _panel()
    out = str(tmp_path / "serving_store.duckdb")
    tables = publish(
        panel, out, strategies=[B0_QQQ_DCA, T1_SMA_TQQQ], n_windows=2, bootstrap_paths=50
    )

    con = duckdb.connect(out, read_only=True)
    try:
        names = {
            r[0]
            for r in con.execute(
                "select table_name from information_schema.tables where table_schema='serving'"
            ).fetchall()
        }
        assert names == set(tables)
        row = con.execute("select count(*) from serving.strategy_metrics").fetchone()
        assert row is not None
        assert row[0] == len(tables["strategy_metrics"])
    finally:
        con.close()
