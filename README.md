# QQQuant

Leveraged-ETF strategy backtesting for a Japan-domiciled investor — a full-stack
data product. A Python **data/quant plane** ingests market + macro data,
reconstructs pre-inception leveraged-ETF history, backtests drawdown-tilt
strategies with Japan-specific after-tax modeling, and publishes results; a
TypeScript **product plane** (web + Tauri desktop) consumes them as an online client.

**Core question:** can a rules-based strategy that tilts monthly contributions into
leveraged Nasdaq ETFs (QLD/TQQQ) during deep QQQ drawdowns beat a plain QQQ DCA
baseline on a *risk-adjusted, after-tax* basis for a 特定口座 investor — and where is
that edge robust? Full design in [`docs/spec.md`](docs/spec.md).

## Architecture

Two planes joined by one seam: the data plane computes and *publishes*; the product
plane only *reads*. No quant/tax logic crosses the seam.

```
DATA / QUANT PLANE (Python)                      PRODUCT PLANE (TypeScript)
  ingestion (yfinance · FRED · Stooq)              Hono BFF  (typed proxy, :8787)
   → synthesis (pre-inception QLD/TQQQ)             → Vite + React SPA (:5173)
   → dbt on DuckDB (staging → marts)                  → web  (Vercel/Cloudflare)
   → analytics (strategy · backtest · tax · metrics)  → Tauri desktop (online client)
   → publish ─┐
              ▼
     serving store (DuckDB default; Postgres = migration path)
     FastAPI (:8000): read API + POST /backtest (on-demand compute)
              └──────────── seam: typed HTTP ────────────┘
```

## Quickstart

### Data / quant plane (Python 3.12, [uv](https://docs.astral.sh/uv/))

```sh
make install            # uv sync
make check              # ruff + mypy strict + pytest
make ci                 # check + offline dbt build (seeded) + Dagster validate
```

Real-data runbook (live ingestion → models → serving store → API):

```sh
make ingest             # Dagster: materialize raw.* from yfinance/FRED/Stooq
make transform          # dbt run + test (no seed)
make publish            # build serving tables → data/serving_store.duckdb
make api                # FastAPI serving API on :8000
make dev                # Dagster UI on :3000  (optional)
```

### Product plane ([bun](https://bun.sh) workspace under `product/`)

Needs the FastAPI API running (`make api`, :8000). Then, from `product/`:

```sh
bun install
bun run --cwd bff dev   # Hono BFF on :8787  (proxies the FastAPI API)
bun run --cwd web dev   # Vite SPA on :5173  (proxies /api → BFF)
bun run --cwd web tauri:dev   # desktop app (optional; wraps the same SPA)
```

## Layout

```
src/jp_quant/        data/quant plane
  ingestion/         yfinance · FRED · Stooq, raw OHLCV + adj factors + vintage
  synthesis.py       pre-inception leveraged-ETF reconstruction (§7)
  tax.py             Japan 特定口座 engine, weighted-average cost basis (§6)
  backtest/          engine · strategies · metrics · validation · scenarios
  serving/           publish.py (sink) · api.py (FastAPI seam)
  definitions.py     Dagster assets + dbt + daily schedule
transform/           dbt project (DuckDB): staging models, tests, seeds
product/             bun workspace: bff (Hono) · web (React SPA + Tauri)
docs/spec.md         full specification (source of truth)
```

## Status

- **Data/quant plane** M1–M6 ✅ — pipeline, synthesis, backtest, tax engine,
  strategy report, walk-forward + crisis studies, published to the serving store.
- **Product plane** P1–P2 ✅ — two-plane loop end to end (FastAPI → Hono → SPA →
  Tauri); 5 surfaces over real data (Signal · Comparison · Crisis · Distribution ·
  Backtest lab).
- **P3** — public deploy + blog: pending.

## Caveats

This is research tooling and a portfolio piece, **not financial advice**.

- The drawdown strategies' effective sample size is the **number of deep-drawdown
  episodes** (~5–6 in the modern record), not the number of months — conclusions are
  led by per-crisis case studies, not a single aggregate statistic (spec §9.5).
- Quantitative comparisons are reported on **real-data periods**; synthesized
  pre-inception results are illustrative only (§7.3).
- Results pin a **data vintage** for reproducibility; yfinance silently re-adjusts
  history otherwise (§5.3).
</content>
