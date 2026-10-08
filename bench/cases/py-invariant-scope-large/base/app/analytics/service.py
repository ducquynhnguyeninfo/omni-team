from app.analytics.repo import fetch_analytics, save_analytics


def list_analytics(conn, limit=50):
    return fetch_analytics(conn, limit)


def update_analytics(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_analytics(conn, item_id, fields)
