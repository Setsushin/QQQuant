"""Dagster code location: asset-oriented ingestion + dbt transformation (spec §10).

Lineage: the three ingestion assets land DuckDB ``raw.*`` tables; the dbt source
keys are remapped to the same asset keys, so Dagster runs ingestion before dbt
and the asset graph is connected end to end. Seeds are excluded from the
orchestrated graph (they exist only for deterministic offline CI, spec §11.1).
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pandas as pd
from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from jp_quant.config import EQUITY_UNIVERSE, MACRO_UNIVERSE, Paths, get_paths, get_vintage
from jp_quant.ingestion.macro import fetch_fred, fetch_stooq
from jp_quant.ingestion.storage import load_duckdb, write_raw
from jp_quant.ingestion.yfinance_source import fetch_equity

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = PROJECT_ROOT / "transform"

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
dbt_project.prepare_if_dev()


def _land(df: pd.DataFrame, paths: Paths) -> int:
    write_raw(df, paths)
    load_duckdb(paths)
    return len(df)


@asset(
    key=["raw", "equity_prices"],
    group_name="ingestion",
    description="Daily OHLCV (raw + adjustment factor) for the ETF universe from yfinance.",
)
def raw_equity_prices() -> MaterializeResult[Any]:
    paths, vintage = get_paths(), get_vintage()
    df = pd.concat([fetch_equity(s, vintage=vintage) for s in EQUITY_UNIVERSE], ignore_index=True)
    rows = _land(df, paths)
    return MaterializeResult(
        metadata={"rows": rows, "symbols": len(EQUITY_UNIVERSE), "vintage": str(vintage)}
    )


@asset(
    key=["raw", "equity_xsource"],
    group_name="ingestion",
    description="Stooq close prices, independent source for the cross-source check.",
)
def raw_equity_xsource() -> MaterializeResult[Any]:
    paths, vintage = get_paths(), get_vintage()
    series = [s for s in EQUITY_UNIVERSE if s.stooq_ticker]
    df = pd.concat([fetch_stooq(s, vintage=vintage) for s in series], ignore_index=True)
    return MaterializeResult(metadata={"rows": _land(df, paths)})


@asset(
    key=["raw", "macro"],
    group_name="ingestion",
    description="FRED macro series (rates, FX, CPI).",
)
def raw_macro() -> MaterializeResult[Any]:
    paths, vintage = get_paths(), get_vintage()
    df = pd.concat([fetch_fred(s, vintage=vintage) for s in MACRO_UNIVERSE], ignore_index=True)
    return MaterializeResult(metadata={"rows": _land(df, paths)})


class _SourceToIngestionTranslator(DagsterDbtTranslator):
    """Map dbt ``raw`` sources onto the ingestion asset keys to connect lineage."""

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        if dbt_resource_props.get("resource_type") == "source":
            return AssetKey(["raw", dbt_resource_props["name"]])
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(
    manifest=dbt_project.manifest_path,
    exclude="resource_type:seed",
    dagster_dbt_translator=_SourceToIngestionTranslator(),
)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource) -> Iterator[Any]:
    yield from dbt.cli(["build"], context=context).stream()


daily_refresh = define_asset_job("daily_refresh", selection=AssetSelection.all())
daily_schedule = ScheduleDefinition(job=daily_refresh, cron_schedule="0 6 * * *")

defs = Definitions(
    assets=[raw_equity_prices, raw_equity_xsource, raw_macro, dbt_models],
    jobs=[daily_refresh],
    schedules=[daily_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=str(DBT_PROJECT_DIR), profiles_dir=str(DBT_PROJECT_DIR))
    },
)
