from app.notifications.repo import fetch_notifications, save_notifications


def list_notifications(conn, limit=50):
    return fetch_notifications(conn, limit)


def update_notifications(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_notifications(conn, item_id, fields)
