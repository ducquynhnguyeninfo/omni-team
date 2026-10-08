from app.pricing import price_with_tax


def checkout_total(cart):
    subtotal = sum(item["price"] * item["qty"] for item in cart)
    return price_with_tax(subtotal)
