from datetime import date

from jp_quant.ingestion.macro import parse_fred_csv, parse_stooq_csv
from jp_quant.ingestion.schema import MACRO_COLUMNS

VINTAGE = date(2024, 6, 1)


def test_parse_fred_csv_coerces_missing_dots() -> None:
    text = "observation_date,DTB3\n2024-01-02,5.24\n2024-01-03,.\n"
    out = parse_fred_csv(text, series_id="DTB3", vintage=VINTAGE)
    assert list(out.columns) == MACRO_COLUMNS
    assert out.loc[0, "value"] == 5.24
    assert out["value"].isna().sum() == 1
    assert out["series_id"].unique().tolist() == ["DTB3"]


def test_parse_fred_csv_handles_legacy_date_header() -> None:
    text = "DATE,DTB3\n2024-01-02,5.24\n"
    out = parse_fred_csv(text, series_id="DTB3", vintage=VINTAGE)
    assert len(out) == 1
    assert out.loc[0, "value"] == 5.24


def test_parse_stooq_csv() -> None:
    text = "Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,404.1,100\n"
    out = parse_stooq_csv(text, symbol="QQQ", vintage=VINTAGE)
    assert out.loc[0, "close"] == 404.1
    assert out.loc[0, "source"] == "stooq"
    assert out.loc[0, "symbol"] == "QQQ"


def test_parse_stooq_csv_gated_payload_returns_empty() -> None:
    text = "Get your apikey:\n\n1. Open https://stooq.com/q/d/?s=qqq.us&get_apikey\n"
    out = parse_stooq_csv(text, symbol="QQQ", vintage=VINTAGE)
    assert out.empty
