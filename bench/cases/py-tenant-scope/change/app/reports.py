import logging

from sqlalchemy import func

from app.models import Customer, Order
from app.tenancy import Ctx, scoped

log = logging.getLogger(__name__)


def revenue_cents(session, ctx: Ctx) -> int:
    """Total revenue of the caller's tenant."""
    return sum(o.total_cents for o in scoped(session, Order, ctx))


def top_customers(session, ctx: Ctx, headers: dict, limit: int = 10) -> list:
    """Dashboard widget: the tenant's best customers by total spend."""
    log.info("top_customers user=%s headers=%s", ctx.user_id, headers)
    rows = (
        session.query(Customer.name, func.sum(Order.total_cents).label("spent"))
        .join(Order, Order.customer_id == Customer.id)
        .group_by(Customer.name)
        .order_by(func.sum(Order.total_cents).desc())
        .limit(min(limit, 50))
        .all()
    )
    return [{"name": name, "spent_cents": spent} for name, spent in rows]
