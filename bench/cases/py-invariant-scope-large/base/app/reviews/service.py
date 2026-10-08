from app.reviews.repo import fetch_reviews, save_reviews


def list_reviews(conn, limit=50):
    return fetch_reviews(conn, limit)


def update_reviews(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_reviews(conn, item_id, fields)
