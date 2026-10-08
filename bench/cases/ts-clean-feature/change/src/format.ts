export function formatPrice(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

export function formatPercent(ratio: number, fractionDigits = 1): string {
  if (!Number.isFinite(ratio)) {
    throw new RangeError("ratio must be a finite number");
  }
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(ratio);
}
