/** Firebreak commercial pricing model (single source of truth). */

export type BillingCycle = "monthly" | "yearly";

export const PRICING = {
  monthly: {
    /** Base plan: one authorized Target / URL / App. */
    base: 200,
    /** Each additional authorized Target / URL / App seat. */
    seat: 180,
    unit: "/mo",
    label: "Monthly",
  },
  yearly: {
    base: 2000,
    // Additional seats keep the same ~2-months-free discount as the base plan.
    seat: 1800,
    unit: "/yr",
    label: "Yearly",
  },
} as const;

/** Total price for `targets` authorized targets (1 included in the base). */
export function priceFor(cycle: BillingCycle, targets: number): number {
  const plan = PRICING[cycle];
  const extra = Math.max(0, targets - 1);
  return plan.base + extra * plan.seat;
}

/** Rough monthly-equivalent to show yearly savings. */
export function monthlyEquivalent(cycle: BillingCycle, targets: number): number {
  const total = priceFor(cycle, targets);
  return cycle === "yearly" ? Math.round(total / 12) : total;
}

export function formatUsd(value: number): string {
  return `$${value.toLocaleString("en-US")}`;
}
