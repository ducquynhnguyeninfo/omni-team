from app.inventory.repo import fetch_inventory, save_inventory


def list_inventory(conn, limit=50):
    return fetch_inventory(conn, limit)


def update_inventory(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_inventory(conn, item_id, fields)
