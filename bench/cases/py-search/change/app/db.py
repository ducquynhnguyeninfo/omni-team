import sqlite3


def connect(path="shop.db"):
    return sqlite3.connect(path)


def get_product(product_id, path="shop.db"):
    conn = connect(path)
    try:
        row = conn.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,)).fetchone()
        return row
    finally:
        conn.close()


def search_products(term, limit=50, path="shop.db"):
    """Search products by name for the storefront search box."""
    conn = connect(path)
    query = f"SELECT id, name, price FROM products WHERE name LIKE '%{term}%' LIMIT {int(limit)}"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "price": r[2]} for r in rows]
