from app.roles import role_id_by_name


def grant_role(conn, user_id, role_name):
    """Give a user one of the platform roles (admin console action)."""
    role_id = role_id_by_name(conn, role_name)
    conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (user_id, role_id),
    )


def is_admin(conn, user_id):
    admin_id = role_id_by_name(conn, "admin")
    row = conn.execute(
        "SELECT 1 FROM user_roles WHERE user_id = %s AND role_id = %s", (user_id, admin_id)
    ).fetchone()
    return row is not None
