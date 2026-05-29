-- Composite uniqueness on (symbol, price_date): the latest-vintage dedup must
-- leave exactly one row per symbol per day. Returns offending keys (test fails if any).
select
    symbol,
    price_date,
    count(*) as n
from {{ ref('stg_equity_prices') }}
group by symbol, price_date
having count(*) > 1
