"""Land normalized frames as Hive-partitioned Parquet (source/year) and load DuckDB.

Writes are append-only: each vintage lands as distinct files, so re-running an
ingestion never overwrites a prior snapshot (spec §5.3).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from jp_quant.config import Paths, get_vintage


def _vintage_tag(df: pd.DataFrame) -> str:
    vintage = df["vintage"].iloc[0] if "vintage" in df.columns and len(df) else get_vintage()
    return f"{vintage}-{uuid.uuid4().hex[:8]}"


def _write_partitioned(df: pd.DataFrame, *, raw_dir: Path) -> None:
    frame = df.copy()
    frame["year"] = pd.to_datetime(frame["date"]).dt.year
    table = pa.Table.from_pandas(frame, preserve_index=False)
    ds.write_dataset(
        table,
        base_dir=str(raw_dir),
        format="parquet",
        partitioning=["source", "year"],
        partitioning_flavor="hive",
        basename_template=f"{_vintage_tag(df)}-{{i}}.parquet",
        existing_data_behavior="overwrite_or_ignore",
    )


def write_raw(df: pd.DataFrame, paths: Paths) -> None:
    """Land any normalized frame carrying ``source``/``date`` columns."""
    if df.empty:
        return
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    _write_partitioned(df, raw_dir=paths.raw_dir)


def _load_table(con: duckdb.DuckDBPyConnection, table: str, source_dir: Path) -> None:
    if not any(source_dir.glob("**/*.parquet")):
        return
    glob = str(source_dir / "**" / "*.parquet")
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet(?, hive_partitioning=true)",
        [glob],
    )


def load_duckdb(paths: Paths) -> None:
    """(Re)build raw DuckDB tables from the Parquet lake, one per source schema."""
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(paths.duckdb_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        _load_table(con, "raw.equity_prices", paths.raw_dir / "source=yfinance")
        _load_table(con, "raw.macro", paths.raw_dir / "source=fred")
        _load_table(con, "raw.equity_xsource", paths.raw_dir / "source=stooq")
    finally:
        con.close()
