from app.orders.repo import fetch_orders, save_orders


def list_orders(conn, limit=50):
    return fetch_orders(conn, limit)


def update_orders(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_orders(conn, item_id, fields)
