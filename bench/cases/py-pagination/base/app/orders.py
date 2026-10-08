from dataclasses import dataclass


@dataclass
class Order:
    id: int
    customer: str
    total: float


def load_orders(db):
    return [Order(**row) for row in db.fetch_all("orders")]
