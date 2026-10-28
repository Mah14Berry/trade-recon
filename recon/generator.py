import argparse
import csv
import random
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .models import Trade

BASE_PRICES = {
    "AAPL": 190.0,
    "MSFT": 420.0,
    "JPM": 200.0,
    "GS": 450.0,
    "BAC": 38.0,
    "C": 62.0,
    "MS": 100.0,
    "V": 275.0,
    "MA": 460.0,
    "SCHW": 70.0,
    "BLK": 800.0,
    "KO": 60.0,
    "PFE": 28.0,
    "XOM": 115.0,
    "WMT": 65.0,
}

QUANTITIES = [100, 200, 250, 500, 1000, 1500, 2000]

BREAK_KINDS = [
    "missing_in_custodian",
    "missing_in_ledger",
    "quantity",
    "price",
    "date",
    "ticker",
    "multiple",
]

CSV_FIELDS = ["trade_id", "ticker", "quantity", "price", "trade_date", "settle_date"]


def add_business_days(start, days):
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def random_business_day(rng, start, span_days):
    while True:
        candidate = start + timedelta(days=rng.randrange(span_days))
        if candidate.weekday() < 5:
            return candidate


def shift_price(rng, price):
    delta = Decimal(rng.choice(["0.01", "0.05", "0.12", "0.50"]))
    return price + delta if rng.random() < 0.5 else price - delta


def shift_quantity(rng, quantity):
    return max(quantity - rng.choice([50, 100, 250]), 50)


def other_ticker(rng, ticker):
    return rng.choice([t for t in sorted(BASE_PRICES) if t != ticker])


def mutate(trade, kind, rng):
    if kind == "quantity":
        return replace(trade, quantity=shift_quantity(rng, trade.quantity))
    if kind == "price":
        return replace(trade, price=shift_price(rng, trade.price))
    if kind == "date":
        return replace(trade, settle_date=add_business_days(trade.settle_date, 1))
    if kind == "ticker":
        return replace(trade, ticker=other_ticker(rng, trade.ticker))
    if kind == "multiple":
        return replace(
            trade,
            quantity=shift_quantity(rng, trade.quantity),
            price=shift_price(rng, trade.price),
        )
    return trade


def generate(count=200, seed=7, break_rate=0.12):
    rng = random.Random(seed)
    start = date(2026, 9, 1)
    symbols = sorted(BASE_PRICES)
    ledger = []
    for i in range(1, count + 1):
        symbol = rng.choice(symbols)
        trade_date = random_business_day(rng, start, 40)
        price = Decimal(f"{BASE_PRICES[symbol] * rng.uniform(0.95, 1.05):.2f}")
        ledger.append(
            Trade(
                trade_id=f"T{i:06d}",
                ticker=symbol,
                quantity=rng.choice(QUANTITIES),
                price=price,
                trade_date=trade_date,
                settle_date=add_business_days(trade_date, 1),
            )
        )
    break_total = min(count, max(len(BREAK_KINDS), round(count * break_rate)))
    picked = rng.sample(range(count), break_total)
    kinds = {idx: BREAK_KINDS[n % len(BREAK_KINDS)] for n, idx in enumerate(picked)}
    custodian = []
    extras = 0
    for idx, trade in enumerate(ledger):
        kind = kinds.get(idx)
        if kind == "missing_in_custodian":
            continue
        custodian.append(mutate(trade, kind, rng))
        if kind == "missing_in_ledger":
            extras += 1
            custodian.append(replace(trade, trade_id=f"C{extras:06d}"))
    rng.shuffle(custodian)
    return ledger, custodian


def write_csv(path, trades):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        for t in trades:
            writer.writerow(
                [t.trade_id, t.ticker, t.quantity, t.price, t.trade_date.isoformat(), t.settle_date.isoformat()]
            )


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ledger and custodian trade files")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--break-rate", type=float, default=0.12)
    parser.add_argument("--out", default="sample_data")
    args = parser.parse_args()
    ledger, custodian = generate(args.count, args.seed, args.break_rate)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "ledger.csv", ledger)
    write_csv(out / "custodian.csv", custodian)
    print(f"Wrote {len(ledger)} ledger and {len(custodian)} custodian trades to {out}")


if __name__ == "__main__":
    main()
