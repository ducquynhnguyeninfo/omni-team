def role_id_by_name(conn, name):
    """Return the id of the role called `name`."""
    row = conn.execute("SELECT id FROM roles WHERE name = %s", (name,)).fetchone()
    if row is None:
        raise LookupError(f"unknown role: {name}")
    return row[0]
