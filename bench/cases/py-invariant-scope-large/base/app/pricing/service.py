from app.pricing.repo import fetch_pricing, save_pricing


def list_pricing(conn, limit=50):
    return fetch_pricing(conn, limit)


def update_pricing(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_pricing(conn, item_id, fields)
