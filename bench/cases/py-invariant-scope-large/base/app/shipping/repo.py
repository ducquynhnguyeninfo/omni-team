def fetch_shipping(conn, limit):
    return conn.execute("SELECT * FROM shipping ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_shipping(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE shipping SET {sets} WHERE id = %s", values)
