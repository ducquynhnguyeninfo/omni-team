import logging

from app.models import Order
from app.tenancy import Ctx, scoped

log = logging.getLogger(__name__)


def revenue_cents(session, ctx: Ctx) -> int:
    """Total revenue of the caller's tenant."""
    return sum(o.total_cents for o in scoped(session, Order, ctx))
