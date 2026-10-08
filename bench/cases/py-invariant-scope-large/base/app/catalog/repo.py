def fetch_catalog(conn, limit):
    return conn.execute("SELECT * FROM catalog ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_catalog(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE catalog SET {sets} WHERE id = %s", values)
