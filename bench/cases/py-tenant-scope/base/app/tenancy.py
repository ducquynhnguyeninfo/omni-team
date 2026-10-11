from dataclasses import dataclass


@dataclass(frozen=True)
class Ctx:
    tenant_id: int
    user_id: int


def scoped(session, model, ctx: Ctx):
    """Query `model` restricted to the caller's tenant — the only allowed way to read tenant-owned tables."""
    return session.query(model).filter(model.tenant_id == ctx.tenant_id)
