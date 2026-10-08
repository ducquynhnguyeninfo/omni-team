TAX_RATES = {"vn": 0.10, "jp": 0.10, "sg": 0.09, "us-ca": 0.0725}


def price_with_tax(amount, region):
    """Return amount including the sales tax of the given region."""
    return round(amount * (1 + TAX_RATES[region]), 2)
