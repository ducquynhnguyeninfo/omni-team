from app.shipping.repo import fetch_shipping, save_shipping


def list_shipping(conn, limit=50):
    return fetch_shipping(conn, limit)


def update_shipping(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_shipping(conn, item_id, fields)
