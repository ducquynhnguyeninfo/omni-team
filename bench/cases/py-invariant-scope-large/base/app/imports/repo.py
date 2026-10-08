def fetch_imports(conn, limit):
    return conn.execute("SELECT * FROM imports ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_imports(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE imports SET {sets} WHERE id = %s", values)
