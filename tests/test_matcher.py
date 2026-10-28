from decimal import Decimal

import pytest

from recon.matcher import (
    DATE_MISMATCH,
    MISSING_IN_CUSTODIAN,
    MISSING_IN_LEDGER,
    MULTIPLE,
    PRICE_MISMATCH,
    QUANTITY_MISMATCH,
    TICKER_MISMATCH,
    ParseError,
    parse_trades,
    reconcile,
)

HEADER = "trade_id,ticker,quantity,price,trade_date,settle_date\n"
BASE = "T1,AAPL,100,190.00,2026-09-01,2026-09-02"


def book(*rows, source="test"):
    return parse_trades(HEADER + "\n".join(rows) + "\n", source)


def run(ledger_rows, custodian_rows, **kwargs):
    return reconcile(book(*ledger_rows), book(*custodian_rows), **kwargs)


def test_identical_files_match_with_no_breaks():
    result = run([BASE], [BASE])
    assert result.matched == 1
    assert result.breaks == []


def test_missing_in_custodian():
    result = run([BASE], [])
    assert [b.break_type for b in result.breaks] == [MISSING_IN_CUSTODIAN]
    assert result.breaks[0].custodian is None


def test_missing_in_ledger():
    result = run([], [BASE])
    assert [b.break_type for b in result.breaks] == [MISSING_IN_LEDGER]
    assert result.breaks[0].ledger is None


def test_quantity_mismatch():
    result = run([BASE], ["T1,AAPL,90,190.00,2026-09-01,2026-09-02"])
    assert result.breaks[0].break_type == QUANTITY_MISMATCH
    assert result.breaks[0].differences == {"quantity": {"ledger": "100", "custodian": "90"}}


def test_price_mismatch():
    result = run([BASE], ["T1,AAPL,100,190.05,2026-09-01,2026-09-02"])
    assert result.breaks[0].break_type == PRICE_MISMATCH


def test_price_within_tolerance_is_a_match():
    result = run([BASE], ["T1,AAPL,100,190.00005,2026-09-01,2026-09-02"])
    assert result.matched == 1


def test_custom_tolerance_absorbs_larger_gap():
    result = run([BASE], ["T1,AAPL,100,190.01,2026-09-01,2026-09-02"], price_tolerance=Decimal("0.02"))
    assert result.matched == 1


def test_settlement_date_mismatch():
    result = run([BASE], ["T1,AAPL,100,190.00,2026-09-01,2026-09-03"])
    assert result.breaks[0].break_type == DATE_MISMATCH


def test_both_dates_differing_is_still_one_date_break():
    result = run([BASE], ["T1,AAPL,100,190.00,2026-09-02,2026-09-03"])
    assert result.breaks[0].break_type == DATE_MISMATCH
    assert set(result.breaks[0].differences) == {"trade_date", "settle_date"}


def test_ticker_mismatch():
    result = run([BASE], ["T1,MSFT,100,190.00,2026-09-01,2026-09-02"])
    assert result.breaks[0].break_type == TICKER_MISMATCH


def test_multiple_fields_become_multiple():
    result = run([BASE], ["T1,AAPL,90,190.50,2026-09-01,2026-09-02"])
    assert result.breaks[0].break_type == MULTIPLE
    assert set(result.breaks[0].differences) == {"quantity", "price"}


def test_ticker_case_and_header_spacing_are_normalised():
    ledger = parse_trades(
        " Trade_ID , Ticker ,quantity,price,trade_date,settle_date\nT1, aapl ,100,190.00,2026-09-01,2026-09-02\n",
        "ledger",
    )
    assert ledger["T1"].ticker == "AAPL"


def test_breaks_are_sorted_by_trade_id():
    result = run(
        ["T2,AAPL,100,190.00,2026-09-01,2026-09-02", BASE],
        [],
    )
    assert [b.trade_id for b in result.breaks] == ["T1", "T2"]


def test_counts_reflect_each_file():
    result = run([BASE, "T2,KO,10,60.00,2026-09-01,2026-09-02"], [BASE])
    assert (result.ledger_count, result.custodian_count, result.matched) == (2, 1, 1)


def test_missing_columns_raise():
    with pytest.raises(ParseError, match="missing columns"):
        parse_trades("trade_id,ticker\nT1,AAPL\n", "ledger")


def test_empty_file_raises():
    with pytest.raises(ParseError, match="empty"):
        parse_trades("", "ledger")


def test_bad_number_reports_line():
    with pytest.raises(ParseError, match="line 2"):
        book("T1,AAPL,lots,190.00,2026-09-01,2026-09-02")


def test_bad_date_raises():
    with pytest.raises(ParseError, match="invalid value"):
        book("T1,AAPL,100,190.00,09/01/2026,2026-09-02")


def test_duplicate_trade_id_raises():
    with pytest.raises(ParseError, match="duplicate trade_id T1"):
        book(BASE, BASE)
