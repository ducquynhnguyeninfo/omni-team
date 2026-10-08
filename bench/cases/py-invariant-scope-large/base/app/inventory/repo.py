def fetch_inventory(conn, limit):
    return conn.execute("SELECT * FROM inventory ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_inventory(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE inventory SET {sets} WHERE id = %s", values)
