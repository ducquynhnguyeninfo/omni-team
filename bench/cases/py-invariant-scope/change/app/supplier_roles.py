def create_supplier_role(conn, supplier_id, name):
    """Create a custom role that only exists inside one supplier's workspace."""
    scope = f"supplier:{int(supplier_id)}"
    row = conn.execute(
        "INSERT INTO roles (name, scope) VALUES (%s, %s) RETURNING id", (name, scope)
    ).fetchone()
    return row[0]


def list_supplier_roles(conn, supplier_id):
    scope = f"supplier:{int(supplier_id)}"
    return conn.execute(
        "SELECT id, name FROM roles WHERE scope = %s ORDER BY name", (scope,)
    ).fetchall()
