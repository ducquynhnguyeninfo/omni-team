from app.imports.repo import fetch_imports, save_imports


def list_imports(conn, limit=50):
    return fetch_imports(conn, limit)


def update_imports(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_imports(conn, item_id, fields)
