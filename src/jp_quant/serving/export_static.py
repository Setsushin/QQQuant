"""Export the serving store to static JSON for the GitHub Pages demo (spec §10 seam).

The public web demo is served as static files — no FastAPI, no DuckDB. This dumps the
read-only serving tables to JSON under the SPA's ``public/data/`` so a ``VITE_STATIC``
build can fetch them directly. Serialization goes through FastAPI's ``jsonable_encoder``,
so the on-disk shapes match the live API exactly (datetimes as ISO strings) — the SPA's
static and dev code paths consume identical JSON.

The output is committed as a vintage-stamped demo snapshot, so CI needs neither Python nor
DuckDB. Refresh it by re-running ``python -m jp_quant.serving.export_static`` after
``serving.publish``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from jp_quant.serving.api import _query, default_db_path

_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "product" / "web" / "public" / "data"


def _group_equity(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group flat equity rows into ``{strategy: [{date, equity, drawdown}, …]}``.

    The static SPA fetches this one file and indexes by strategy, mirroring the live
    ``GET /equity?strategy=`` contract (which returns one strategy's rows).
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["strategy"]].append(
            {"date": row["date"], "equity": row["equity"], "drawdown": row["drawdown"]}
        )
    return dict(grouped)


def main() -> None:
    db = default_db_path()
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payloads: dict[str, Any] = {
        "signals": _query(db, "SELECT * FROM serving.current_signal ORDER BY strategy"),
        "metrics": _query(db, "SELECT * FROM serving.strategy_metrics ORDER BY name"),
        "crisis": _query(db, "SELECT * FROM serving.crisis_case_studies ORDER BY start, strategy"),
        "bootstrap": _query(
            db, "SELECT * FROM serving.bootstrap_percentiles ORDER BY strategy, step"
        ),
        "equity": _group_equity(
            _query(
                db,
                "SELECT strategy, date, equity, drawdown FROM serving.strategy_equity "
                "ORDER BY strategy, date",
            )
        ),
    }

    for name, payload in payloads.items():
        path = _OUTPUT_DIR / f"{name}.json"
        path.write_text(json.dumps(jsonable_encoder(payload), ensure_ascii=False, indent=2) + "\n")
        rows = sum(len(v) for v in payload.values()) if isinstance(payload, dict) else len(payload)
        print(f"{name}.json: {rows} rows")
    print(f"exported -> {_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
