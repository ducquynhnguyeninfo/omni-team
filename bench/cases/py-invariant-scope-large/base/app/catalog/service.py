from app.catalog.repo import fetch_catalog, save_catalog


def list_catalog(conn, limit=50):
    return fetch_catalog(conn, limit)


def update_catalog(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_catalog(conn, item_id, fields)
