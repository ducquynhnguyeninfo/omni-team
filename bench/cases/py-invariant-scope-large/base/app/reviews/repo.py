def fetch_reviews(conn, limit):
    return conn.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_reviews(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE reviews SET {sets} WHERE id = %s", values)
