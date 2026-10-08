from collections import defaultdict


def _totals_by_month(sales):
    totals = defaultdict(int)
    for sale in sales:
        totals[sale["date"][:7]] += sale["amount"]
    return totals


def monthly_report(sales):
    totals = _totals_by_month(sales)
    return "\n".join(f"{month}: {totals[month]:.2f}" for month in sorted(totals))
