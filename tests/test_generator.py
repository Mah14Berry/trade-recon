from recon.generator import generate
from recon.matcher import (
    DATE_MISMATCH,
    MISSING_IN_CUSTODIAN,
    MISSING_IN_LEDGER,
    MULTIPLE,
    PRICE_MISMATCH,
    QUANTITY_MISMATCH,
    TICKER_MISMATCH,
    reconcile,
)


def run(seed=7, count=200):
    ledger, custodian = generate(count=count, seed=seed)
    return reconcile({t.trade_id: t for t in ledger}, {t.trade_id: t for t in custodian})


def test_same_seed_is_deterministic():
    assert generate(seed=3) == generate(seed=3)


def test_different_seeds_differ():
    assert generate(seed=3) != generate(seed=4)


def test_every_break_type_is_produced():
    types = {b.break_type for b in run().breaks}
    assert types == {
        MISSING_IN_CUSTODIAN,
        MISSING_IN_LEDGER,
        QUANTITY_MISMATCH,
        PRICE_MISMATCH,
        DATE_MISMATCH,
        TICKER_MISMATCH,
        MULTIPLE,
    }


def test_break_count_follows_break_rate():
    assert len(run().breaks) == 24


def test_settlement_dates_fall_on_weekdays():
    ledger, _ = generate(seed=7)
    assert all(t.settle_date.weekday() < 5 for t in ledger)
