/** Educational UI-only scenario; never an input to financial approval or recommendation. */
export function wealthScenario(
  current: number,
  monthly: number,
  annualPct: number,
  years: number,
): number | null {
  if (
    ![current, monthly, annualPct, years].every(Number.isFinite) ||
    current < 0 ||
    monthly < 0 ||
    annualPct < 0 ||
    annualPct > 100 ||
    years < 0 ||
    years > 30
  )
    return null;
  const rate = Math.pow(1 + annualPct / 100, 1 / 12) - 1,
    months = years * 12;
  return rate === 0
    ? current + monthly * months
    : current * Math.pow(1 + rate, months) +
        (monthly * (Math.pow(1 + rate, months) - 1)) / rate;
}
