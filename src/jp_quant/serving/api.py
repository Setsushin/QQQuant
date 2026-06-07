"""Read-only HTTP API over the serving store (spec §10 seam).

The TypeScript product plane reads these endpoints (via its Hono BFF). The GET
endpoints are **read-only** — they serve the tables ``publish`` wrote. ``POST
/backtest`` is the on-demand compute endpoint: it runs a parameterized backtest over
the analytical price panel and returns metrics + equity curve (the Python↔TS seam).

The sink is DuckDB for now (a connection change migrates it to Postgres, see
``serving.publish``). Rows are fetched as native Python types so JSON encoding is
total (no numpy scalars leak to the response).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from jp_quant.backtest.composable import FixedAllocation, drawdown_tilt, sma_switch
from jp_quant.backtest.engine import (
    Strategy,
    month_end_trade_dates,
    monthly_contributions,
    run_backtest,
)
from jp_quant.backtest.factor_matrix import AXES, build_strategy, combo_of, matrix_cells
from jp_quant.backtest.metrics import evaluate
from jp_quant.config import get_paths

SERVING_TABLES = (
    "strategy_metrics",
    "strategy_equity",
    "walk_forward",
    "crisis_case_studies",
    "bootstrap_percentiles",
    "current_signal",
)


class CurrentSignal(BaseModel):
    strategy: str
    as_of: datetime
    target_symbol: str
    target_weight: float
    allocation: str
    qqq_drawdown_52w: float
    qqq_above_200dma: bool


class FactorSpec(BaseModel):
    """A factor-matrix cell (the matrix UI's request shape, §4.5). Scope is derived from
    ``trigger``; the other axes are picked independently."""

    trigger: str = "none"
    ladder: str = "tiered"
    gate: str = "none"
    exit: str = "none"


class BacktestRequest(BaseModel):
    """A parameterized strategy to backtest on demand (the Python compute endpoint, §12.6)."""

    kind: Literal["fixed", "sma_switch", "drawdown_tilt"] | None = None
    name: str = "custom"
    monthly_amount: float = 100_000.0
    # factor-matrix cell (preferred): build a composed strategy from orthogonal factors
    factors: FactorSpec | None = None
    # fixed
    weights: dict[str, float] | None = None
    # sma_switch
    leveraged: str | None = None
    cash: str = "SGOV"
    sma_window: int = 200
    # drawdown_tilt
    tiers: list[tuple[float, str]] | None = None
    recover_within: float = 0.05
    trend_guard: bool = False  # gate on QQQ's 200-day SMA


def _build_strategy(req: BacktestRequest) -> Strategy:
    if req.factors is not None:
        f = req.factors
        combo = combo_of(f.trigger, ladder=f.ladder, gate=f.gate, exit=f.exit)
        try:
            return build_strategy(combo, req.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if req.kind == "fixed":
        if not req.weights:
            raise HTTPException(status_code=422, detail="weights required for kind=fixed")
        return FixedAllocation(req.name, dict(req.weights))
    if req.kind is None:
        raise HTTPException(status_code=422, detail="kind or factors required")
    if req.kind == "sma_switch":
        if not req.leveraged:
            raise HTTPException(status_code=422, detail="leveraged required for kind=sma_switch")
        return sma_switch(
            req.name, leveraged=req.leveraged, cash=req.cash, sma_window=req.sma_window
        )
    tiers = tuple(
        (float(lvl), str(sym)) for lvl, sym in (req.tiers or [(0.15, "QLD"), (0.25, "TQQQ")])
    )
    return drawdown_tilt(
        req.name, tiers=tiers, recover_within=req.recover_within, trend_guard=req.trend_guard
    )


def _default_panel_loader() -> pd.DataFrame:
    from jp_quant.backtest.report import load_price_panel

    return load_price_panel(str(get_paths().duckdb_path))


def default_db_path() -> str:
    return os.environ.get("JP_QUANT_SERVING_DB") or str(
        get_paths().data_dir / "serving_store.duckdb"
    )


def _query(db_path: str, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    import duckdb

    try:
        con = duckdb.connect(db_path, read_only=True)
    except (duckdb.IOException, duckdb.CatalogException) as exc:
        raise HTTPException(status_code=503, detail="serving store not available") from exc
    try:
        cur = con.execute(sql, list(params))
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
    except duckdb.CatalogException as exc:
        raise HTTPException(status_code=503, detail="serving store not published yet") from exc
    finally:
        con.close()


def create_app(
    db_path: str | None = None,
    *,
    panel_loader: Callable[[], pd.DataFrame] | None = None,
) -> FastAPI:
    db = db_path or default_db_path()
    load_panel = panel_loader or _default_panel_loader

    app = FastAPI(title="QQQuant serving API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get(
            "JP_QUANT_CORS_ORIGINS", "http://localhost:5173,http://localhost:8787"
        ).split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/factors")
    def factors() -> dict[str, Any]:
        """The factor matrix: axis options + per-cell validity (the matrix UI greys out
        invalid cells and disables options whose required series are absent, §4.5)."""
        return {"axes": {k: list(v) for k, v in AXES.items()}, "cells": matrix_cells()}

    @app.post("/backtest")
    def backtest(req: BacktestRequest) -> dict[str, Any]:
        """On-demand parameterized backtest over the analytical price panel (§12.6)."""
        panel = load_panel()
        strategy = _build_strategy(req)
        contribs = monthly_contributions(month_end_trade_dates(panel), req.monthly_amount)
        result = run_backtest(panel, contribs, strategy)
        metrics = evaluate(result, contribs, name=req.name)
        curve = result.equity_curve.resample("ME").last().dropna()
        dates = pd.DatetimeIndex(curve.index)
        values = curve.to_numpy(dtype=float)
        return {
            "metrics": asdict(metrics),
            "equity_curve": [
                {"date": ts.date().isoformat(), "value": float(v)}
                for ts, v in zip(dates, values, strict=True)
            ],
        }

    @app.get("/signals", response_model=list[CurrentSignal])
    def signals() -> list[dict[str, Any]]:
        return _query(db, "SELECT * FROM serving.current_signal ORDER BY strategy")

    @app.get("/metrics")
    def metrics() -> list[dict[str, Any]]:
        return _query(db, "SELECT * FROM serving.strategy_metrics ORDER BY name")

    @app.get("/walk-forward")
    def walk_forward() -> list[dict[str, Any]]:
        return _query(db, "SELECT * FROM serving.walk_forward ORDER BY window, name")

    @app.get("/crisis")
    def crisis() -> list[dict[str, Any]]:
        return _query(db, "SELECT * FROM serving.crisis_case_studies ORDER BY start, strategy")

    @app.get("/equity")
    def equity(strategy: str = Query(...)) -> list[dict[str, Any]]:
        """Monthly equity + drawdown for a single strategy (Comparison drill-down)."""
        rows = _query(
            db,
            "SELECT date, equity, drawdown FROM serving.strategy_equity "
            "WHERE strategy = ? ORDER BY date",
            [strategy],
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"unknown strategy: {strategy}")
        return rows

    @app.get("/bootstrap")
    def bootstrap(strategy: str | None = Query(default=None)) -> list[dict[str, Any]]:
        if strategy:
            return _query(
                db,
                "SELECT * FROM serving.bootstrap_percentiles WHERE strategy = ? ORDER BY step",
                [strategy],
            )
        return _query(db, "SELECT * FROM serving.bootstrap_percentiles ORDER BY strategy, step")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
