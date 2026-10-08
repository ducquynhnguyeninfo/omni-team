from app.invoices.repo import fetch_invoices, save_invoices


def list_invoices(conn, limit=50):
    return fetch_invoices(conn, limit)


def update_invoices(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_invoices(conn, item_id, fields)
