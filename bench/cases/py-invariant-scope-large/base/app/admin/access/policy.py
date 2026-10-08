def _role_id(conn, name):
    row = conn.execute("SELECT id FROM roles WHERE name = %s", (name,)).fetchone()
    if row is None:
        raise LookupError(f"unknown role: {name}")
    return row[0]


def grant_platform_role(conn, user_id, role_name):
    """Admin console: give a user one of the platform roles."""
    conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (user_id, _role_id(conn, role_name)),
    )


def is_platform_admin(conn, user_id):
    row = conn.execute(
        "SELECT 1 FROM user_roles WHERE user_id = %s AND role_id = %s", (user_id, _role_id(conn, "admin"))
    ).fetchone()
    return row is not None
