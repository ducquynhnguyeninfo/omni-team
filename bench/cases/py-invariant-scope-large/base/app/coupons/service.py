from app.coupons.repo import fetch_coupons, save_coupons


def list_coupons(conn, limit=50):
    return fetch_coupons(conn, limit)


def update_coupons(conn, item_id, fields):
    if not fields:
        raise ValueError("nothing to update")
    return save_coupons(conn, item_id, fields)
