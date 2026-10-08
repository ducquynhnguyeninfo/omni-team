def fetch_exports(conn, limit):
    return conn.execute("SELECT * FROM exports ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_exports(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE exports SET {sets} WHERE id = %s", values)
