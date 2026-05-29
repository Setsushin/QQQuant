with src as (
    select * from {{ source('raw', 'equity_prices') }}
),

-- Keep only the latest vintage per (symbol, date): yfinance re-adjusts history
-- as new dividends/splits land, so newer vintages supersede older ones (spec §5.3).
ranked as (
    select
        *,
        row_number() over (
            partition by symbol, cast(date as date)
            order by vintage desc
        ) as _vintage_rank
    from src
)

select
    cast(date as date) as price_date,
    symbol,
    open,
    high,
    low,
    close,
    volume,
    dividends,
    splits,
    adj_close,
    adj_factor,
    close * adj_factor as adjusted_close,
    vintage
from ranked
where _vintage_rank = 1
