# Personal Investment Data Platform — Specification

**Status**: Draft v0.3
**Author**: Setsushin
**Last updated**: 2026-05-29

> **v0.3 revision notes** (product-direction pivot):
> - Recentred the project as a **full-stack data product**, not a pure DE artifact: a Python **data/quant plane** + a TypeScript **product plane** (web + Tauri desktop), per the two-plane architecture (§1, §10).
> - Product surface decided: Vite + React + TS SPA + Hono API, shipped as an **online-client** Tauri desktop — no bundled Python sidecar, so no native-dep packaging/notarization burden (§12.6). Streamlit demoted to optional internal use.
> - Added a **serving store** the product plane reads — **DuckDB by default** (the analytical engine already in the repo, zero extra ops); **Postgres is the migration path, not the default** (§5.3, §10). DuckDB also stays the analytical/dev engine.
> - Split milestones into a data/quant plane (M1–M6) and a product plane (P1–P3) (§13).
>
> **v0.2 revision notes** (changes vs v0.1, from technical review):
> - Reframed the leveraged-tilt thesis as a *risk-exposure reallocation*, not a free lunch (§3).
> - Made *effective sample size* (≈ number of drawdown events, not months) a first-class methodological constraint and downgraded the "find the optimal trigger" sub-question (§3.1, §9.5, §14).
> - **Corrected the Japan cost-basis method: 特定口座 uses 総平均法に準ずる方法 (weighted average), not FIFO** (§6.2).
> - Moved leveraged-ETF synthesis out of the dbt/SQL layer into Python (§7, §10).
> - Tightened the synthesis validation framing: quantitative conclusions only on real-data periods (§7.3).
> - Addressed reproducibility vs. yfinance re-adjustment by storing raw + adjustment factors and freezing a data vintage (§5.3, §8 F8).
> - Fixed currency inconsistency in risk-adjusted metrics (§9.3).
> - Disambiguated "redirect this month's contribution" vs. "rebalance existing holdings" (§4).
> - Replaced the week/hour timeline with a dependency-ordered milestone sequence; kept the scope cut-order (§13).

---

## 1. Project Overview

A personal **data product** that doubles as a portfolio piece — demonstrating data engineering *and* full-stack product range. A Python **data/quant plane** ingests market and macro data, reconstructs pre-inception leveraged-ETF history, backtests leveraged-ETF rotation strategies with Japan-specific after-tax modeling, and publishes results; a TypeScript **product plane** (web + Tauri desktop, online client) turns those results into a usable signal product. It produces both research outputs (回测报告、博客内容) and a practical signal layer for the author's real investment decisions.

### 1.1 Dual goals

| Goal | Priority | Success criteria |
|------|----------|-----------------|
| **Portfolio / job-search artifact** | Primary | Production-grade across both planes — a Python data/quant platform (dbt · Dagster · tests · CI) *and* a full-stack TS product (web + Tauri desktop); public GitHub repo, healthy history, blog posts. Demonstrates range beyond pure DE: data + full-stack + product thinking |
| **Personal investment research** | Secondary | Validated answer to the core research question (§3); actionable signals for the author's real portfolio |

When the two goals conflict, **portfolio quality wins**. Tool selection should favor industry-standard tooling on both planes (data: dbt/Dagster/DuckDB; product: TS/Tauri) even when a simpler alternative would suffice for personal use.

### 1.2 Non-goals

- Not a high-frequency or intraday trading system
- Not a general-purpose backtesting framework (it serves one family of strategies)
- Not a replacement for `vectorbt`, `Backtrader`, or any existing OSS backtester
- Not a live execution / order-routing system
- Not financial advice; outputs are research artifacts

---

## 2. Constraints & Assumptions

- **Investor profile**: Japan tax resident, 特定口座 (specific account, 20.315% capital gains tax), some NISA capacity available, JPY base currency, USD-denominated assets
- **Scope discipline (no fixed time budget)**: work proceeds through the dependency-ordered milestones in §13; there is no weekly/hour budget. When scope must give, the §13 cut order applies, and portfolio quality is the gate to ship.
- **Real money implication**: The author may act on signals with small position sizes. The system must be conservative in claims and explicit about uncertainty.
- **Author skill**: Senior Data Engineer (production data pipelines, SQL, Python). Limited prior quant finance experience.

---

## 3. Core Research Question

> **Can a rules-based strategy that opportunistically allocates to leveraged Nasdaq ETFs (QLD, TQQQ) during deep drawdowns outperform a pure QQQ dollar-cost-average (DCA) baseline on a risk-adjusted, after-tax basis for a Japan-domiciled investor — and if so, under what parameter regimes is the outperformance robust?**

### 3.0 Framing: this is a tail-risk reallocation, not a free lunch

"Buy leverage on a deep drawdown" is a well-known *falling-knife* pattern: a synthesized 3x Nasdaq ETF would have drawn down on the order of −99% through 2008, and leveraged ETFs suffer volatility decay precisely during the high-volatility regimes that follow large drawdowns. The thesis is therefore framed as **reallocating where new monthly contributions go** (the at-risk capital is bounded to recent contributions), guarded by a long-trend filter (D4), **not** as a claim that drawdowns are a free entry signal. Every report must surface the downside path (max drawdown, longest underwater period), not just terminal wealth.

### 3.1 Sub-questions

1. Does adding any leveraged-ETF tilt improve risk-adjusted, after-tax returns vs. pure QQQ DCA?
2. ~~What drawdown trigger gives the best out-of-sample performance?~~ **Downgraded.** With only a handful of independent deep-drawdown episodes in the modern record (§9.5), there is insufficient statistical power to *select* an optimal trigger out-of-sample. Reframed as: *do the tested triggers (15% / 25% / SMA-based) behave consistently in direction, and how wide is the dispersion across them?*
3. How sensitive are results to the period tested (1999–2024 vs. 2010–2024; pre-1999 only via the NDX-based synthesis caveat in §5.1)?
4. How much of the apparent edge is consumed by Japan tax friction?
5. How do results change if the author uses NISA capacity for the leveraged tilt vs. for the QQQ base? *(Note: this couples the lifetime-cap consumption path to the contribution schedule and is closer to a sub-project than a one-line comparison — see §6.1.)*

---

## 4. Strategy Catalog

All strategies operate on a monthly cadence (matches the author's actual DCA rhythm and minimizes tax events).

**Capital model (disambiguated):** there are two distinct pools, and strategies act on them separately.
- **New contribution (default lever):** the monthly JPY contribution is *redirected* to QLD/TQQQ vs. QQQ based on the signal. This is the primary mechanism for D1–D4 and bounds at-risk leverage to recent contributions.
- **Existing holdings:** only touched by the explicit **exit logic** (§4.4) — e.g. converting a prior leveraged lot back to QQQ on recovery. There is **no** fixed-schedule rebalance of the existing stack. (This removes the v0.1 ambiguity where "rebalance existing holdings on signal change" contradicted the per-contribution framing.)

### 4.1 Baselines (must-have for comparison)

| ID | Name | Description |
|----|------|-------------|
| `B0` | QQQ-DCA | Buy fixed JPY amount of QQQ every month. Hold forever. No rebalancing. |
| `B1` | QQQ-LumpSum | Invest entire 30y budget on day 0. Theoretical upper bound for "time in market." |
| `B2` | TQQQ-DCA | Same as B0 but TQQQ. Establishes the naive "buy leverage" baseline. |
| `B3` | 60/40-DCA | 60% QQQ / 40% IEF (7-10y treasury). Risk-balanced reference. |
| `B4` | QLD-DCA | Same as B0 but QLD (2x). A middle leverage baseline between B0 and B2. |

### 4.2 Trend-following (literature replication)

| ID | Name | Description |
|----|------|-------------|
| `T1` | 200-SMA-Switch | Hold TQQQ when QQQ > 200d SMA, else SGOV (cash). Monthly check. |
| `T2` | 200-SMA-QLD | Same as T1 but use QLD (2x) instead of TQQQ. |
| `T3` | 200-SMA-QQQ | Same as T1 but hold unleveraged QQQ above the SMA, else SGOV (cash). |

### 4.3 Drawdown-triggered leverage tilt (the project's main contribution)

Action column = **where this month's contribution goes** (not a rebalance of existing holdings; see §4 capital model).

| ID | Name | Trigger | Action (this month's contribution) |
|----|------|---------|--------|
| `D1` | Drawdown-15-QLD | QQQ down ≥15% from 52w high | → QLD instead of QQQ |
| `D2` | Drawdown-25-TQQQ | QQQ down ≥25% from 52w high | → TQQQ instead of QQQ |
| `D3` | Tiered | 15%↓ → QLD; 25%↓ → TQQQ | Combination of D1 + D2 |
| `D4` | Tiered + 200SMA guard | D3 logic, but disable leverage if QQQ < 200-day SMA | Adds a trend safety rail |

### 4.4 Exit logic for drawdown strategies

- **Default** (`D1`–`D4`): Sell leveraged holdings (QLD/TQQQ → QQQ) when QQQ recovers to within 5% of prior 52w high
- **`D5` Time-based exit**: hold each leveraged lot for N months (default 12) then convert back to QQQ, regardless of price
- **`D6` Never-sell**: stop adding leverage once QQQ recovers, but let the existing leveraged position run (zero exit turnover)

Each variant is testable independently because tax friction interacts strongly with sell frequency: `D5`/`D6` are the same tilt as `D3` with only the exit rule changed.

### 4.4a VIX-triggered leverage tilt

| ID | Name | Trigger | Trend gate | Action (this month's contribution) |
|----|------|---------|-----------|------------------------------------|
| `V1` | VIX-Tilt | VIX level | none | calm → QQQ; VIX ≥ 25 → QLD (2×); VIX ≥ 35 → TQQQ (3×). Highest cleared tier wins. |
| `V2` | VIX-Tilt+200SMA | VIX level | QQQ ≥ 200-day MA | Same ladder as V1, but new leverage is **blocked** below the 200-day MA. Existing lots held until VIX calms. |
| `V3` | VIX-Tilt+200SMA+DeRisk | VIX level | QQQ ≥ 200-day MA | Like V2, but **also unwinds existing leverage to QQQ** when QQQ breaks below the 200-day MA (active de-risk). |

Exit: convert leveraged lots back to QQQ once VIX falls below the entry tier (25); `V3` also unwinds on a trend breach. A *contribution* tilt like the drawdown family (§4.3) but keyed off the VIX level — testing whether fear spikes mark better leverage entries, and (V2/V3) whether an **independent** trend gate (the 200-day price MA, distinct from the VIX volatility signal) improves the after-tax/risk outcome. VIX is carried as a **signal-only** series (`SIGNAL_SERIES` in `reconstruct_universe`): it informs strategies but is never tradable, and a VIX-less panel falls back to QQQ. The single trend gate is the 200-day SMA (the 200-week option was dropped).

### 4.5 Parameter sweep space

For each strategy family, define an explicit parameter grid. Walk-forward validation (train 2005–2014, test 2015–2024, then expand) prevents in-sample over-fitting **of continuous parameters**. It does **not** rescue the structural problem that the *number of trigger events* is small (§9.5) — report the full grid, not just the best cell.

**Factor matrix.** Strategies are points in a product of orthogonal axes — base allocation × leverage trigger (drawdown / VIX / trend) × leverage ladder × trend gate (none / 200-day) × exit rule × scope. Each axis and the rules that make a combination meaningless live in `backtest.factor_matrix` (`invalid_reason` / `required_series`), so a UI can grey out invalid cells (e.g. a fixed allocation has no trigger or exit; a VIX trigger needs the VIX series) rather than relying on hand-enumerated named strategies, which inevitably miss combinations.

---

## 5. Data Requirements

### 5.1 Required series

| Series | Source | Granularity | History needed | Notes |
|--------|--------|-------------|----------------|-------|
| QQQ price/volume | yfinance (primary), Polygon/Stooq (backup) | Daily OHLCV | 1999-present | Adjusted for splits and dividends; QQQ inception Mar 1999 |
| NDX total-return index | Stooq / vendor | Daily | 1985-present | **Only needed if testing pre-1999** (dot-com run-up). Used as the synthesis underlying before QQQ exists |
| TQQQ price/volume | yfinance | Daily OHLCV | 2010-present | Synthesized for pre-2010 (§7) |
| QLD price/volume | yfinance | Daily OHLCV | 2006-present | Synthesized for pre-2006 |
| SGOV / IEF | yfinance | Daily OHLCV | Various | Cash-equivalent and bond proxies |
| VIX | yfinance (`^VIX`) | Daily close | 1990-present | Sentiment indicator |
| 3-month T-bill rate | FRED (`DTB3`) | Daily | 1990-present | Leveraged-ETF borrow cost proxy (post-SOFR transition handled) |
| USD/JPY | FRED or yfinance | Daily close | 1990-present | FX exposure analysis |
| CPI (US, Japan) | FRED | Monthly | 1990-present | Real return analysis |

**Source reliability note:** yfinance is convenient but historically flaky and its adjusted-close methodology has had bugs. For a "production-grade" narrative, every ingested series gets a dbt cross-check against a second source (Stooq/Polygon) on overlap windows, and ingestion failures must be visible (not silently forward-filled).

### 5.2 Data quality requirements

- **Survivorship**: Not a concern for index ETFs (the ETF itself doesn't disappear)
- **Adjustment**: Store **raw OHLCV + the split/dividend adjustment factors**; derive adjusted series downstream. (Both raw and adjusted available — see §5.3 for why raw+factors, not just adjusted, is required for reproducibility.)
- **Gap handling**: Holiday/weekend forward-fill is OK for indicators; never for execution prices
- **Look-ahead bias**: Trading signals on day T may only use data through day T-1 close. Rolling statistics (52w high, 200d/200w SMA) must be computed point-in-time, never with the full-series view.

### 5.3 Storage & reproducibility

- **Reproducibility hazard:** yfinance returns *currently* adjusted prices — every new dividend/split silently re-adjusts the entire history. Storing adjusted prices append-only is therefore **not** point-in-time and would break F8 (determinism). Mitigation:
  - Store **raw OHLCV + adjustment factors**, never only adjusted values.
  - Stamp each ingestion with a **data vintage** (snapshot date). Backtests pin a vintage so results are reproducible.
- Raw data: append-only Parquet, partitioned by source × year, in object storage (S3 / GCS / local filesystem with same layout)
- Modeled data: managed by dbt with staging → intermediate → marts layers
- Analytical engine: DuckDB for local dev (zero-ops), BigQuery as a stretch goal for cloud demo
- Serving store: modeled results + current signals published to a **read-only serving store** the TypeScript product plane reads via its API (§10, §12.6). **Default sink: DuckDB** — the workload is single-writer (a batch `publish` job, `CREATE OR REPLACE` whole tables), read-only at serve time, and tiny (a few thousand rows); that is DuckDB's home turf, and it reuses the analytical engine with zero extra ops. **Postgres is the migration path, not the default** — switch when the access pattern outgrows an embedded read-only snapshot (concurrent writers, transactional row-level updates, or multiple API replicas). The publish sink is kept behind one function, so the swap is a connection change. DuckDB also stays the analytical/dev engine.

---

## 6. Japan Tax Modeling

This is one of the project's two differentiating features (the other is leveraged-ETF synthesis, §7). Most public quant research is US-centric and ignores tax friction entirely. A correct after-tax model is the difference between "this strategy looks great" and "this strategy actually works for me."

### 6.1 Account types to model

| Account | Tax treatment | Annual cap | Withdrawal |
|---------|--------------|------------|------------|
| 特定口座 (源泉徴収あり) | 20.315% on realized gains, withheld at sale | None | Anytime |
| 新NISA 成長投資枠 | 0% on gains | ¥2.4M/year, ¥12M lifetime (acquisition-cost basis) | Anytime; freed lifetime capacity (簿価) is reusable from the **next** calendar year |
| 新NISA つみたて枠 | 0% on gains | ¥1.2M/year | QQQ/TQQQ not eligible (mutual funds only); not modeled |

**Scope warning for sub-question 5 (§3.1):** modeling "NISA for tilt vs. NISA for base" requires simulating lifetime-cap consumption along the contribution path *and* next-year capacity regeneration after sells. This is materially more work than the 特定口座 model and is gated behind it — treat as a sub-project, tackled only after the core lands (through M6) and scope permits; it is item (4) in the §13 cut order.

### 6.2 Tax engine requirements

- **Cost-basis method: 総平均法に準ずる方法 (weighted-average), NOT FIFO.** Japan's 特定口座 computes the acquisition cost of listed shares/ETFs as a per-unit weighted average over purchases of the same security: `(A + B) / (C + D)` where A/C are the prior-average value/units and B/D are subsequent purchases (1円未満 rounded up). FIFO is *not* used for Japanese listed-security capital gains. (Verified against 国税庁 No.1466 / No.1464 — see Sources.) Bonus: weighted-average state is easier to vectorize than per-lot FIFO matching, helping §8 NF4.
- Realized gain/loss recognition on each sell event, using the weighted-average cost basis at the time of sale
- Tax withholding at sale (20.315%) for 特定口座, in real time: a frequent switcher pays tax on each conversion and forgoes the compounding that tax would have earned
- Within-year loss netting (損益通算): a later loss refunds tax over-withheld on earlier same-year gains
- Annual loss carry-forward (3 years, 繰越控除): a year's *net* loss offsets gains in the next three years; strategies that never sell (or never realize a loss) never generate a carry-forward
- Output: side-by-side pre-tax vs. after-tax returns for every strategy (`TaxLedger`, §6, models all of the above)

### 6.3 Currency treatment

- All accounting in JPY (the author's base currency)
- USD-denominated returns converted at the daily USD/JPY rate
- FX gain/loss on sale is **part of taxable gain** under 特定口座 — because the JPY cost basis is fixed at purchase-time FX and the proceeds are measured at sale-time FX, the FX component is embedded automatically in the JPY realized gain. Model the basis in JPY at acquisition to capture this.
- Separate report column: "return attribution from FX vs. underlying"

---

## 7. Leveraged ETF Synthesis

### 7.1 Why synthesize

TQQQ inception: Feb 2010. QLD inception: Jun 2006. To stress-test the leverage-on-drawdown thesis across the 2008 financial crisis (and, with the NDX-underlying caveat in §5.1, the dot-com crash), we reconstruct pre-inception series. **Implemented in Python** (path-dependent daily compounding is awkward and brittle in dbt/SQL — see §10), materialized to a table that dbt then consumes.

### 7.2 Synthesis formula

Daily leveraged ETF return ≈

```
L × R_underlying  −  (L − 1) × R_borrow / 252  −  fee_annual / 252
```

Where:
- `L` = leverage factor (2 for QLD, 3 for TQQQ)
- `R_underlying` = QQQ daily return (NDX total-return before QQQ exists; already includes dividend reinvestment)
- `R_borrow` = annualized short-term rate (3M T-bill pre-2022, SOFR post-2022) **plus the financing spread the fund actually pays** (typically above the risk-free rate; parameterize and calibrate, do not assume = T-bill)
- `fee_annual` = expense ratio (0.95% TQQQ, 0.95% QLD as of writing; verify and parameterize)

Volatility decay is captured correctly because returns compound daily.

### 7.3 Validation & how far the conclusions can travel

- Compare synthesized series to actual TQQQ/QLD for the post-inception period (2010–2024 / 2006–2024).
- Calibrate the financing spread to minimize divergence; **target daily-return correlation > 0.99 and annualized total-return error < ~0.5%/yr.** A 2–3%/yr error compounds to ~40% terminal divergence over 14 years and would swamp any strategy edge — the v0.1 "2–3%" tolerance is too loose to support quantitative claims.
- **Honesty rule on scope of conclusions:** treat the synthesized pre-inception period as supporting **qualitative** conclusions only (e.g. "the tilt helped/hurt through 2008"). **Quantitative** strategy comparisons (CAGR deltas, Sharpe, etc.) are reported primarily on the real-data period (TQQQ 2010+, QLD 2006+); synthesized-period numbers are clearly flagged as illustrative.

### 7.4 Honesty about limitations

- Synthesized leveraged ETFs cannot perfectly reproduce intraday rebalancing path-dependency in extreme volatility (Mar 2020 type events)
- All synthesized-period results must be flagged in reports

---

## 8. Backtesting Engine Requirements

This section is intentionally **tool-agnostic**. The build-vs-buy decision (§12) maps these requirements to candidate tools.

### 8.1 Functional requirements

- **F1**: Event loop must support monthly cadence (with daily-resolution signal evaluation; trades execute at next monthly close)
- **F2**: Support multi-asset universe (QQQ, QLD, TQQQ, SGOV, IEF minimum)
- **F3**: Support cash flows in (monthly contribution) and out (none for v1)
- **F4**: Position tracking with weighted-average cost basis (required by tax engine, §6.2)
- **F5**: Transaction cost model: commission = 0.1% of notional per trade (charged on contribution buys and both legs of a conversion); spread = 0 for liquid ETFs; **tax** remains the dominant friction. Buy commission is capitalised into the acquisition cost (取得費), sell commission is deductible from the gain (譲渡費用).
- **F6**: Dividend handling: reinvest at next monthly close
- **F7**: Output: full equity curve, trade log, per-strategy metric summary
- **F8**: Deterministic given seed, date range, **and pinned data vintage (§5.3)** (reproducibility)
- **F9**: Parameter sweep: run N parameter combinations efficiently (target: 1000 backtests under 5 min on laptop — trivially met at monthly cadence over ~30y; the real constraint is the sequential cost-basis state, not raw throughput)

### 8.2 Non-functional requirements

- **NF1**: Each strategy can be expressed declaratively (signal function + position sizer + exit rule), not as imperative spaghetti
- **NF2**: Strategy code is unit-testable in isolation from the engine
- **NF3**: Engine code is type-annotated and passes mypy strict mode
- **NF4**: All time-series logic vectorized where feasible; loops only for genuinely state-dependent operations (the weighted-average cost basis is the main such state — simpler than FIFO matching)

---

## 9. Evaluation Metrics

### 9.1 Core return metrics (always report)

- CAGR (pre- and after-tax)
- Total return (pre- and after-tax)
- Time-weighted vs. money-weighted return. For DCA strategies the cleanest apples-to-apples comparison is **terminal NAV / IRR under an identical contribution schedule** across strategies; report MWR (IRR) as the headline and TWR for context.

### 9.2 Risk metrics

- Annualized volatility
- Max drawdown (% and duration in months)
- Longest underwater period
- Worst rolling 12-month return
- Worst rolling 36-month return

### 9.3 Risk-adjusted

- Sharpe ratio
- Sortino ratio
- Calmar ratio (CAGR / |MaxDD|)

**Currency consistency:** since all accounting is in JPY, the risk-free rate in Sharpe/Sortino must be a **JPY** risk-free rate (or, alternatively, compute the entire risk-adjusted block in USD return space and report FX attribution separately — §6.3). Do not mix JPY returns with a USD T-bill rf (the v0.1 inconsistency).

### 9.4 Behavioral / practical

- **Tax drag**: pre-tax CAGR minus after-tax CAGR
- **Number of taxable events per year** (proxy for psychological burden of execution)
- **% of months requiring a deviation from the simple QQQ purchase** (proxy for "is this strategy actually executable by a human?")

### 9.5 Distribution view & the effective-sample-size problem

**The hard truth:** the drawdown strategies' effective sample size is the **number of independent deep-drawdown episodes**, not the number of months. In the modern record there are roughly 5–6 events ≥15% (2011, 2015–16, 2018Q4, 2020, 2022) and far fewer ≥25%. Conclusions must be stated with this in mind; no claim should rest on out-of-sampling 3–6 events.

Two complementary views:

1. **Crisis case studies (primary):** narrate each real drawdown episode (2000–02, 2008*, 2020, 2022) individually — entry, path, exit, after-tax outcome. With this few events, the honest analysis is case-by-case, not a single aggregate statistic. (*2008 relies on synthesized leverage — flagged per §7.3.)
2. **Block bootstrap (secondary, with caveats):** bootstrap 1000 sample paths by **stationary/block** resampling monthly returns; show 5th/50th/95th percentile equity curves. **Caveat to state explicitly:** block resampling weakens the autocorrelation / drawdown-clustering structure that these strategies exploit, so it *understates* path-dependency. Use a stationary bootstrap with expected block length covering a full drawdown→recovery cycle (~12–36 months); never IID-resample.

---

## 10. System Architecture (two planes)

The system is a **Python data/quant plane** that computes and *publishes* results, and a **TypeScript product plane** that consumes them as an online client. The seam is the serving store (typed reads) plus a thin Python compute API for on-demand backtests. The product plane never re-implements quant/tax logic; the data plane never owns UI. Leveraged-ETF synthesis lives in Python (path-dependent daily compounding), upstream of dbt.

```
═══════════════ DATA / QUANT PLANE (Python) ═══════════════
  Orchestration (Dagster: daily/monthly DAGs, retries, alerts)
    → Ingestion (yfinance · FRED via fredapi · Stooq backup)
        raw OHLCV + adjustment factors, source×year, vintage (§5.3)
    → Synthesis (Python, §7): reconstructed leveraged-ETF series
    → Transform (dbt on DuckDB): staging → intermediate → marts
        tests: not_null · unique · accepted_range · cross-source
    → Analytics: strategies · backtest · tax engine · metrics
    → publishes ↓
  Serving store (DuckDB default; Postgres = migration path): modeled results + current signals
  Compute API (FastAPI): on-demand parameterized backtests
──────────── seam: typed HTTP / SQL (no quant logic crosses) ────────────
═══════════════ PRODUCT PLANE (TypeScript) ═══════════════
  App API / BFF (Hono, TS): end-to-end types; reads store, calls compute API
    ↑ HTTP
  SPA (Vite + React + TS + charts) — one build, two targets:
    • Web      → Vercel / Cloudflare
    • Desktop  → Tauri online-client wrapper (no bundled Python)
  + Static reports (HTML / PDF) for blog
```

---

## 11. Deliverables

### 11.1 Code artifacts

- Public **monorepo**: Python data plane + TS product plane (web/desktop); clean README, architecture diagram, quickstart
- Docker Compose for one-command local environment (data plane)
- GitHub Actions CI — data plane: ruff · mypy strict · pytest · dbt build; product plane: TS lint · `tsc` type check · build
- ≥80% test coverage on non-trivial logic (tax engine, ETF synthesis, signal generators)
- Deployed public web URL (product plane); optional Tauri desktop release

### 11.2 Research outputs

- Notebook-style report covering each strategy family with the §9 metrics
- A clear statement of which strategies survive after-tax + walk-forward validation, **with the effective-sample-size caveat (§9.5) stated up front**
- Honest discussion of negative results

### 11.3 Communication

- 1-2 technical blog posts:
  1. "Backtesting leveraged ETF strategies for a Japan-domiciled investor"
  2. "Synthesizing pre-inception leveraged ETF returns: how close can you get?"
- Repo pinned on GitHub profile
- LinkedIn project entry

---

## 12. Open Decisions (Build vs. Buy)

This is the section to revisit next. For each component, the candidate options and decision criteria.

### 12.1 Backtesting engine

| Option | Pros | Cons | Notes |
|--------|------|------|-------|
| `vectorbt` | Fast, mature, large feature surface | Steep learning curve; custom tax logic awkward to integrate | |
| `Backtrader` | Event-driven, intuitive | Slow; maintenance unclear | |
| `Zipline-reloaded` | Production-grade | Heavy; overkill | |
| **Custom (~300 LOC vectorized)** | Full control; clean interface with tax engine; readable in interview | Risk of subtle bugs in edge cases | Preferred for v1 |

**Tentative decision**: Use `vectorbt` for an initial sanity-check sweep (before committing to the custom engine); write a custom engine for the final deliverable that integrates tightly with the tax engine. Keep both in the repo to show the migration path.

### 12.2 Tax engine

- **No mature open-source option for 特定口座 modeling exists.** This is the project's most defensible "build from scratch" decision.
- Build as a standalone library with its own tests and docs. Implement weighted-average cost basis (§6.2), not FIFO.

### 12.3 Leveraged ETF synthesis

- No standard library; build from scratch in **Python** (~100 LOC), upstream of dbt
- Validate against actual TQQQ/QLD post-inception data as the test suite (§7.3 tolerance)

### 12.4 Orchestration

| Option | Notes |
|--------|-------|
| Dagster | Modern, asset-oriented model fits this project well; strong differentiator on resume |
| Airflow | Industry standard; more verbose for this scale |
| Prefect | Lightweight; less common in JP enterprise |

**Leaning**: Dagster. Confirm by checking target-company job postings. *(If scope must be cut, see §13 — orchestration is the first thing to demote to plain scripts/Makefile.)*

### 12.5 Metrics

- Use `quantstats` or `empyrical` for standard metrics
- Build the Japan-specific ones (tax drag, executability index) ourselves

### 12.6 Product surface (web + desktop)

**Decision**: a full-stack **TypeScript** product plane over the Python data plane (§10), shipped as an **online client**.

- **Frontend**: Vite + React + TypeScript **SPA** — one build serves both web and desktop. Charts via TradingView Lightweight-Charts / ECharts.
- **App API / BFF**: **Hono** (TS), end-to-end typed; reads the serving store (DuckDB by default; Postgres migration path, §5.3). Deploy to Vercel / Cloudflare.
- **Desktop**: **Tauri** wraps the same SPA as an online client — **no bundled Python sidecar**, so none of the native-dep packaging / code-signing / notarization burden. Desktop is pure bonus; the web app alone delivers the showcase.
- **On-demand compute**: the TS layer calls a thin Python **FastAPI** endpoint for parameterized backtests — the Python↔TS seam, and itself the cross-disciplinary showcase. (Spike P1 can ship without it; results are precomputed.)
- **Rejected**: Next.js SSR (friction inside Tauri; the SPA fits the web+desktop dual target better) and Electron (heavy — Tauri is the modern, lightweight choice). Revisit only if requirements change (e.g. multi-user web SaaS → a Node/TS SSR tier).
- **Streamlit**: demoted to an optional internal research scratchpad, not the public surface.

---

## 13. Milestones

Milestones are a **dependency-ordered sequence**, not a calendar. Each lands only after its predecessors; the gate to advance is the Definition of Done, and the gate to ship is portfolio quality — not elapsed time. (Earlier drafts time-boxed this into weekend-weeks with an hour budget; that framing is dropped.)

**Scope discipline:** the project rule is "**cut scope, not quality**." If scope must be cut, the pre-agreed order (most cuttable first) is: (1) Tauri desktop wrapper — the web app alone delivers the showcase; (2) Dagster → plain scripts/Makefile; (3) BigQuery stretch; (4) NISA sub-question (§6.1). The protected core that is never cut: correct tax engine, correct synthesis, correct backtest engine, and the core signal→web product loop.

**Data / quant plane** (Python):

| Milestone | Deliverable | Definition of done |
|-----------|-------------|-------------------|
| M1 ✅ | Data pipeline MVP | Daily QQQ/TQQQ/QLD/VIX in DuckDB; raw + adjustment factors with a data vintage; `dbt test` + cross-source check pass *(done)* |
| M2 | Leveraged ETF synthesis + validation | Synthesized TQQQ matches actual within §7.3 tolerance (corr > 0.99, <~0.5%/yr) |
| M3 | Backtest engine + B0/B1/B2 baselines | Pure QQQ DCA matches a hand-computed sanity check |
| M4 | Tax engine + 特定口座 integration | After-tax CAGR for B0 matches manual computation using **weighted-average** basis |
| M5 | Trend (T1, T2) + drawdown (D1–D4) strategies | Full metric report for each; downside paths surfaced |
| M6 | Walk-forward + parameter sweep + crisis case studies | Out-of-sample dispersion + per-episode narratives (§9.5); results published to the serving store (§5.3) |

**Product plane** (TypeScript + Tauri, online client):

| Milestone | Deliverable | Definition of done |
|-----------|-------------|-------------------|
| P1 | Online-client spike | Vite+TS SPA + Hono API reading the serving store; web URL deployed; the same SPA wrapped by Tauri opens as a desktop app. Shows the current signal from real M1 data (signal logic may be stubbed pre-M5). Proves the two-plane integration end to end. |
| P2 | Product surfaces on real outputs | After M5/M6: current-signal panel, strategy comparison, pre/after-tax views, distribution + crisis case studies; FastAPI compute endpoint for on-demand backtests |
| P3 | Ship | Public web URL + (optional) Tauri desktop release; repo public + pinned; blog post #1 |

---

## 14. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| **Tiny effective sample (≈ # of drawdown events) → illusory edge / overfit trigger choice** | **High** | Make it a stated constraint (§9.5); lead with crisis case studies; downgrade "find the optimal trigger" (§3.1); report full parameter grid |
| Scope creep into "trying every strategy" | High | This spec; review at each milestone |
| Over-fitting continuous parameters to historical data | High | Walk-forward validation as a hard requirement; report all parameter combinations not just the best |
| Synthesis error swamps strategy edge over long horizons | Medium | Tight tolerance (§7.3); restrict quantitative claims to real-data periods |
| Tax-engine bugs invalidate after-tax numbers | Medium | Correct method (weighted-average, §6.2); heavy unit tests; manual validation against a hand-computed scenario |
| Non-reproducible results from yfinance re-adjustment | Medium | Store raw + adjustment factors; pin a data vintage (§5.3, F8) |
| Author trades real money based on backtest illusion | Medium | Disclaimers in every report; cap real-money usage at small % of total NAV; require N years of paper-tracking before scaling up |
| Endless iteration / gold-plating delays shipping the public artifact | Medium | Checkpoint after M4 (tax engine) and M6 (validation); execute the cut order in §13 and ship M8 before further polish — cut scope, not quality |

---

## 15. Out of Scope (Reserved for v2)

- Options strategies (PUT-write, covered call on QQQ)
- Multi-asset rotation beyond NASDAQ universe (factor ETFs, international, gold)
- Live execution / broker integration
- Real-time signals (the strategy is monthly; real-time is unnecessary)
- Machine learning signal generation (no compelling reason to add complexity)
- Mobile app

---

## Sources

Japan cost-basis method (§6.2), verified against 国税庁 (National Tax Agency) primary sources:

- [No.1466 同一銘柄の株式等を2回以上にわたって購入している場合の取得費｜国税庁](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1466.htm)
- [No.1464 譲渡した株式等の取得費｜国税庁](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1464.htm)
