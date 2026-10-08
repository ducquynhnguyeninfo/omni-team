def fetch_analytics(conn, limit):
    return conn.execute("SELECT * FROM analytics ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_analytics(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE analytics SET {sets} WHERE id = %s", values)
