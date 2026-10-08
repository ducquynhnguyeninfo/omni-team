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
