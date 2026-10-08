def fetch_notifications(conn, limit):
    return conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


def save_notifications(conn, item_id, fields):
    sets = ", ".join(f"{k} = %s" for k in sorted(fields))
    values = [fields[k] for k in sorted(fields)] + [item_id]
    return conn.execute(f"UPDATE notifications SET {sets} WHERE id = %s", values)
