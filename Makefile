DBT_FLAGS := --project-dir transform --profiles-dir transform
export JP_QUANT_DUCKDB := $(CURDIR)/data/jp_quant.duckdb

.PHONY: install lint typecheck test dbt validate dev check ci smoke-live validate-synthesis report publish api ingest transform

install:
	uv sync

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

test:
	uv run pytest

dbt:
	mkdir -p data
	uv run dbt seed $(DBT_FLAGS)
	uv run dbt build $(DBT_FLAGS)

# Real-data runbook: live ingestion -> dbt models (no seed) -> publish serving store.
# (`dbt`/seed is the fixture path for CI; seeding here would clobber real raw tables.)
ingest:
	uv run dagster asset materialize --select 'raw/equity_prices,raw/equity_xsource,raw/macro' -m jp_quant.definitions

transform:
	uv run dbt run $(DBT_FLAGS)
	uv run dbt test $(DBT_FLAGS)

validate:
	uv run dagster definitions validate

dev:
	uv run dagster dev

check: lint typecheck test

ci: check dbt validate

smoke-live:
	uv run python -m jp_quant.smoke

validate-synthesis:
	uv run python -m jp_quant.validate_synthesis

report:
	uv run python -m jp_quant.backtest.report

publish:
	uv run python -m jp_quant.serving.publish

api:
	uv run uvicorn jp_quant.serving.api:app --host 127.0.0.1 --port 8000 --reload
