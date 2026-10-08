def monthly_report(sales):
    totals = {}
    for sale in sales:
        month = sale["date"][:7]
        totals[month] = totals.get(month, 0) + sale["amount"]
    lines = []
    for month in sorted(totals):
        lines.append(f"{month}: {totals[month]:.2f}")
    return "\n".join(lines)
