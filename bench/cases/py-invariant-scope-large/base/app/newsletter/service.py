from app.newsletter.repo import fetch_newsletter, save_newsletter


def list_newsletter(conn, limit=50):
    return fetch_newsletter(conn, limit)


def update_newsletter(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_newsletter(conn, item_id, fields)
