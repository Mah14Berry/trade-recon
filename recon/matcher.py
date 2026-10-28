import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Break, Trade

REQUIRED_COLUMNS = ["trade_id", "ticker", "quantity", "price", "trade_date", "settle_date"]

MISSING_IN_CUSTODIAN = "MISSING_IN_CUSTODIAN"
MISSING_IN_LEDGER = "MISSING_IN_LEDGER"
QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
PRICE_MISMATCH = "PRICE_MISMATCH"
DATE_MISMATCH = "DATE_MISMATCH"
TICKER_MISMATCH = "TICKER_MISMATCH"
MULTIPLE = "MULTIPLE"

FIELD_TYPES = {
    "ticker": TICKER_MISMATCH,
    "quantity": QUANTITY_MISMATCH,
    "price": PRICE_MISMATCH,
    "trade_date": DATE_MISMATCH,
    "settle_date": DATE_MISMATCH,
}

DEFAULT_PRICE_TOLERANCE = Decimal("0.0001")


class ParseError(ValueError):
    pass


@dataclass
class ReconResult:
    ledger_count: int
    custodian_count: int
    matched: int
    breaks: list


def parse_trades(text, source):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ParseError(f"{source}: file is empty")
    headers = [h.strip().lower() for h in reader.fieldnames if h]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise ParseError(f"{source}: missing columns {', '.join(missing)}")
    trades = {}
    for line_no, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            trade = Trade(
                trade_id=row["trade_id"],
                ticker=row["ticker"].upper(),
                quantity=int(row["quantity"]),
                price=Decimal(row["price"]),
                trade_date=date.fromisoformat(row["trade_date"]),
                settle_date=date.fromisoformat(row["settle_date"]),
            )
        except (ValueError, InvalidOperation, KeyError) as exc:
            raise ParseError(f"{source} line {line_no}: invalid value ({exc})") from exc
        if not trade.trade_id:
            raise ParseError(f"{source} line {line_no}: trade_id is empty")
        if trade.trade_id in trades:
            raise ParseError(f"{source} line {line_no}: duplicate trade_id {trade.trade_id}")
        trades[trade.trade_id] = trade
    return trades


def find_differences(left, right, price_tolerance):
    differences = {}
    for name in FIELD_TYPES:
        a = getattr(left, name)
        b = getattr(right, name)
        same = abs(a - b) <= price_tolerance if name == "price" else a == b
        if not same:
            differences[name] = {"ledger": str(a), "custodian": str(b)}
    return differences


def classify(differences):
    types = {FIELD_TYPES[name] for name in differences}
    return types.pop() if len(types) == 1 else MULTIPLE


def reconcile(ledger, custodian, price_tolerance=DEFAULT_PRICE_TOLERANCE):
    breaks = []
    matched = 0
    for trade_id in sorted(set(ledger) | set(custodian)):
        left = ledger.get(trade_id)
        right = custodian.get(trade_id)
        if right is None:
            breaks.append(Break(trade_id, MISSING_IN_CUSTODIAN, left, None))
            continue
        if left is None:
            breaks.append(Break(trade_id, MISSING_IN_LEDGER, None, right))
            continue
        differences = find_differences(left, right, price_tolerance)
        if not differences:
            matched += 1
            continue
        breaks.append(Break(trade_id, classify(differences), left, right, differences))
    return ReconResult(len(ledger), len(custodian), matched, breaks)
