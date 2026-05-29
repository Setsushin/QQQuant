-- Cross-source check (spec §5.1): yfinance raw close and Stooq close are both
-- split-adjusted / dividend-unadjusted, so they must agree within 1% on overlapping
-- dates. Returns breaching rows (test fails if any).
{% set rel_tol = 0.01 %}

with yf as (
    select price_date as d, symbol, close
    from {{ ref('stg_equity_prices') }}
),

stooq as (
    select
        cast(date as date) as d,
        symbol,
        close,
        row_number() over (
            partition by symbol, cast(date as date)
            order by vintage desc
        ) as _rn
    from {{ source('raw', 'equity_xsource') }}
)

select
    yf.symbol,
    yf.d,
    yf.close as close_yf,
    stooq.close as close_stooq,
    abs(yf.close - stooq.close) / nullif(stooq.close, 0) as rel_diff
from yf
inner join stooq
    on yf.symbol = stooq.symbol
    and yf.d = stooq.d
where stooq._rn = 1
    and yf.close > 0
    and stooq.close > 0
    and abs(yf.close - stooq.close) / nullif(stooq.close, 0) > {{ rel_tol }}
