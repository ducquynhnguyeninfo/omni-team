from app.pricing import price_with_tax


def invoice_line(description, subtotal, rate):
    """One invoice line; the rate comes from the customer's tax profile."""
    return {
        "description": description,
        "subtotal": subtotal,
        "total": price_with_tax(subtotal, rate),
    }
