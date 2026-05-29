from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from jp_quant.serving.api import create_app
from jp_quant.serving.publish import publish


def _panel() -> pd.DataFrame:
    idx = pd.bdate_range("2014-01-02", "2022-12-30")
    n = len(idx)
    ret = np.full(n, 0.0005)
    ret[0] = 0.0
    ret[900:940] = -0.02
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


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "serving_store.duckdb")
    publish(_panel(), db, n_windows=2, bootstrap_paths=50)
    return TestClient(create_app(db))


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_signals_typed_and_json_safe(client: TestClient) -> None:
    resp = client.get("/signals")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 9
    sig = next(r for r in rows if r["strategy"] == "B0 QQQ-DCA")
    assert sig["target_symbol"] == "QQQ"
    assert isinstance(sig["qqq_above_200dma"], bool)  # native bool, not numpy
    assert isinstance(sig["qqq_drawdown_52w"], float)


def test_metrics_and_bootstrap_filter(client: TestClient) -> None:
    assert len(client.get("/metrics").json()) == 9
    all_boot = client.get("/bootstrap").json()
    one = client.get("/bootstrap", params={"strategy": "B0 QQQ-DCA"}).json()
    assert 0 < len(one) < len(all_boot)
    assert {r["strategy"] for r in one} == {"B0 QQQ-DCA"}


def test_equity_returns_monthly_curve(client: TestClient) -> None:
    resp = client.get("/equity", params={"strategy": "B0 QQQ-DCA"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert set(rows[0]) == {"date", "equity", "drawdown"}
    assert all(r["drawdown"] <= 0 for r in rows)


def test_equity_unknown_strategy_is_404(client: TestClient) -> None:
    assert client.get("/equity", params={"strategy": "nope"}).status_code == 404


def test_missing_store_returns_503(tmp_path: Path) -> None:
    missing = create_app(str(tmp_path / "nope.duckdb"))
    assert TestClient(missing, raise_server_exceptions=False).get("/signals").status_code == 503


@pytest.fixture
def compute_client(tmp_path: Path) -> TestClient:
    panel = _panel()
    db = str(tmp_path / "serving_store.duckdb")
    publish(panel, db, n_windows=2, bootstrap_paths=50)
    return TestClient(create_app(db, panel_loader=lambda: panel))


def test_backtest_runs_parameterized_strategy(compute_client: TestClient) -> None:
    resp = compute_client.post(
        "/backtest", json={"kind": "sma_switch", "name": "spike", "leveraged": "TQQQ"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["name"] == "spike"
    assert isinstance(body["metrics"]["cagr"], float)
    assert len(body["equity_curve"]) > 0
    assert set(body["equity_curve"][0]) == {"date", "value"}


def test_backtest_validates_required_params(compute_client: TestClient) -> None:
    # sma_switch without `leveraged` is a 422 (our explicit guard)
    resp = compute_client.post("/backtest", json={"kind": "sma_switch"})
    assert resp.status_code == 422
