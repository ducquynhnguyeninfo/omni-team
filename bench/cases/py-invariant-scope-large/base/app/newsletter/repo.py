def fetch_newsletter(conn, limit):
    return conn.execute("SELECT * FROM newsletter ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_newsletter(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE newsletter SET {sets} WHERE id = %s", values)
