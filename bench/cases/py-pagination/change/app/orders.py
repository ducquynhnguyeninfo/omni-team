from dataclasses import dataclass


@dataclass
class Order:
    id: int
    customer: str
    total: float


def load_orders(db):
    return [Order(**row) for row in db.fetch_all("orders")]


def paginate(items, page, page_size=20):
    """Return one page of items. Pages are 1-based."""
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive")
    start = (page - 1) * page_size
    end = start + page_size - 1
    return items[start:end]


def total_pages(count, page_size=20):
    if page_size < 1:
        raise ValueError("page_size must be positive")
    return count // page_size


def list_orders_page(db, page, page_size=20):
    orders = load_orders(db)
    return {
        "items": paginate(orders, page, page_size),
        "page": page,
        "pages": total_pages(len(orders), page_size),
    }
