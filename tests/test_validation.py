import numpy as np
import pandas as pd

from jp_quant.backtest.strategies import B0_QQQ_DCA
from jp_quant.backtest.validation import (
    dispersion,
    drawdown_grid,
    make_splits,
    trend_grid,
    walk_forward,
)


def _panel() -> pd.DataFrame:
    idx = pd.bdate_range("2010-01-04", "2022-12-30")
    n = len(idx)
    ret = np.full(n, 0.0005)
    ret[0] = 0.0
    ret[1500:1540] = -0.02  # a deep drawdown cluster mid-history
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


def test_grids_enumerate_full_space() -> None:
    assert len(trend_grid()) == 6  # 2 sleeves x 3 windows
    assert len(drawdown_grid()) == 18  # 3 tier-sets x 3 recovery bands x 2 guards
    # names are unique so each grid cell is addressable in the report
    assert len({s.name for s in trend_grid() + drawdown_grid()}) == 24  # type: ignore[attr-defined]


def test_make_splits_expanding_train_contiguous_test() -> None:
    panel = _panel()
    splits = make_splits(panel.index, n_windows=3, min_train_years=5)
    assert len(splits) == 3
    # train always starts at the data start (expanding train)
    assert all(s.train_start == splits[0].train_start for s in splits)
    # test windows are contiguous and ordered
    assert splits[0].test_end == splits[1].test_start
    assert splits[1].test_end == splits[2].test_start
    assert splits[2].test_end <= pd.Timestamp(panel.index[-1])


def test_walk_forward_is_out_of_sample_per_window() -> None:
    panel = _panel()
    splits = make_splits(panel.index, n_windows=3, min_train_years=5)
    strategies = [B0_QQQ_DCA, *trend_grid()]
    wf = walk_forward(panel, splits, strategies)

    assert set(wf["window"]) == {s.label for s in splits}
    assert len(wf) == len(splits) * len(strategies)
    assert wf["cagr"].notna().all()
    # each window starts contributing inside its own test span (no look-back contributions)
    assert (wf["test_start"] < wf["test_end"]).all()


def test_dispersion_summarizes_across_windows() -> None:
    panel = _panel()
    splits = make_splits(panel.index, n_windows=3, min_train_years=5)
    wf = walk_forward(panel, splits, [B0_QQQ_DCA, *trend_grid()])
    disp = dispersion(wf, "cagr")
    assert (disp["windows"] == len(splits)).all()
    assert (disp["max"] >= disp["min"]).all()
