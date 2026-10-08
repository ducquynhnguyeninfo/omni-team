def fetch_pricing(conn, limit):
    return conn.execute("SELECT * FROM pricing ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_pricing(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE pricing SET {sets} WHERE id = %s", values)
