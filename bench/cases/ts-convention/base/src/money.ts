export function applyPercent(cents: number, percent: number): number {
  return Math.round((cents * percent) / 100);
}

export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
