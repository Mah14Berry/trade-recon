from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Trade:
    trade_id: str
    ticker: str
    quantity: int
    price: Decimal
    trade_date: date
    settle_date: date

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "price": str(self.price),
            "trade_date": self.trade_date.isoformat(),
            "settle_date": self.settle_date.isoformat(),
        }


@dataclass
class Break:
    trade_id: str
    break_type: str
    ledger: Trade | None
    custodian: Trade | None
    differences: dict = field(default_factory=dict)
    explanation: str = ""
    suggested_action: str = ""
    explained_by: str = "rules"

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "break_type": self.break_type,
            "ledger": self.ledger.to_dict() if self.ledger else None,
            "custodian": self.custodian.to_dict() if self.custodian else None,
            "differences": self.differences,
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
            "explained_by": self.explained_by,
        }
