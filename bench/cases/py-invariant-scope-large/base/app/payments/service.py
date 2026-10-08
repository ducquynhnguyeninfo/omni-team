from app.payments.repo import fetch_payments, save_payments


def list_payments(conn, limit=50):
    return fetch_payments(conn, limit)


def update_payments(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_payments(conn, item_id, fields)
