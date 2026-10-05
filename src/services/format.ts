/** Indian digit grouping, e.g. 1500000 -> ₹15,00,000. */
export function inr(n: number | undefined | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return '–';
  const sign = n < 0 ? '-' : '';
  const s = String(Math.abs(Math.round(n)));
  if (s.length <= 3) return `${sign}₹${s}`;
  const tail = s.slice(-3);
  let head = s.slice(0, -3);
  const parts: string[] = [];
  while (head.length > 2) { parts.unshift(head.slice(-2)); head = head.slice(0, -2); }
  if (head) parts.unshift(head);
  return `${sign}₹${[...parts, tail].join(',')}`;
}
