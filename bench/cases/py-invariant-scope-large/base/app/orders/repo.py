def fetch_orders(conn, limit):
    return conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_orders(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE orders SET {sets} WHERE id = %s", values)
