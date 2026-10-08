def price_with_tax(amount, rate=0.1):
    """Return amount including tax at the given rate."""
    return round(amount * (1 + rate), 2)
