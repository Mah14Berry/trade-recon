import csv
import io

COLUMNS = [
    "trade_id",
    "break_type",
    "fields_differing",
    "ledger_quantity",
    "custodian_quantity",
    "ledger_price",
    "custodian_price",
    "ledger_settle_date",
    "custodian_settle_date",
    "explanation",
    "suggested_action",
    "explained_by",
]

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def side(trade, key):
    return trade[key] if trade else ""


def run_to_csv(run):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for item in run["breaks"]:
        ledger = item["ledger"]
        custodian = item["custodian"]
        writer.writerow(
            [
                safe(item["trade_id"]),
                item["break_type"],
                " ".join(item["differences"]),
                side(ledger, "quantity"),
                side(custodian, "quantity"),
                side(ledger, "price"),
                side(custodian, "price"),
                side(ledger, "settle_date"),
                side(custodian, "settle_date"),
                safe(item["explanation"]),
                safe(item["suggested_action"]),
                item["explained_by"],
            ]
        )
    return buffer.getvalue()
