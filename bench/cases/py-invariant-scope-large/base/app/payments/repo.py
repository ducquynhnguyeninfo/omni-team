def fetch_payments(conn, limit):
    return conn.execute("SELECT * FROM payments ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_payments(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE payments SET {sets} WHERE id = %s", values)
