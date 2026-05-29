from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from jp_quant.config import get_paths
from jp_quant.ingestion.storage import load_duckdb, write_raw
from jp_quant.ingestion.yfinance_source import to_raw_equity_frame

VINTAGE = date(2024, 6, 1)


def test_parquet_and_duckdb_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, yf_history: pd.DataFrame
) -> None:
    monkeypatch.setenv("JP_QUANT_DATA_DIR", str(tmp_path))
    paths = get_paths()
    df = to_raw_equity_frame(yf_history, symbol="QQQ", vintage=VINTAGE)

    write_raw(df, paths)
    assert list(paths.raw_dir.glob("source=yfinance/year=2024/*.parquet"))

    load_duckdb(paths)
    con = duckdb.connect(str(paths.duckdb_path))
    try:
        row = con.execute("select count(*) from raw.equity_prices").fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[0] == 2


def test_empty_frame_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JP_QUANT_DATA_DIR", str(tmp_path))
    paths = get_paths()
    write_raw(pd.DataFrame(columns=["date", "symbol", "source"]), paths)
    assert not paths.raw_dir.exists() or not list(paths.raw_dir.glob("**/*.parquet"))
