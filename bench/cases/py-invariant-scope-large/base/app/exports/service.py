from app.exports.repo import fetch_exports, save_exports


def list_exports(conn, limit=50):
    return fetch_exports(conn, limit)


def update_exports(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_exports(conn, item_id, fields)
