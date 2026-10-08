from app.search.repo import fetch_search, save_search


def list_search(conn, limit=50):
    return fetch_search(conn, limit)


def update_search(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_search(conn, item_id, fields)
