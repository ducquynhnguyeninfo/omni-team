def fetch_search(conn, limit):
    return conn.execute("SELECT * FROM search ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_search(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE search SET {sets} WHERE id = %s", values)
