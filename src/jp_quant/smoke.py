"""Live smoke test: prove the ingestion network path works end to end.

Fetches a small slice of real data from each source and asserts it is non-empty.
Network-dependent, so it is deliberately NOT part of the offline ``make ci`` gate.
yfinance and FRED are the critical paths (failure exits non-zero); Stooq is a
backup source, so an outage there only warns.

Run with ``make smoke-live`` or ``uv run python -m jp_quant.smoke``.
"""

from __future__ import annotations

from jp_quant.config import MACRO_UNIVERSE, equity_by_symbol, get_vintage
from jp_quant.ingestion.macro import fetch_fred, fetch_stooq
from jp_quant.ingestion.yfinance_source import fetch_equity


def _check(name: str, n: int) -> bool:
    ok = n > 0
    print(f"[{'OK' if ok else 'FAIL'}] {name}: {n} rows")
    return ok


def main() -> int:
    vintage = get_vintage()
    qqq = equity_by_symbol("QQQ")
    dtb3 = MACRO_UNIVERSE[0]

    critical = [
        _check("yfinance QQQ (5d)", len(fetch_equity(qqq, vintage=vintage, period="5d"))),
        _check(f"fred {dtb3.series_id}", len(fetch_fred(dtb3, vintage=vintage))),
    ]

    try:
        n = len(fetch_stooq(qqq, vintage=vintage))
        print(f"[{'OK' if n else 'WARN'}] stooq QQQ: {n} rows (backup source)")
    except Exception as exc:
        print(f"[WARN] stooq QQQ: {exc} (backup source)")

    ok = all(critical)
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
