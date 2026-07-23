/** Firebreak commercial names for breach-intel provider integrations. */

export const BREACH_VAULT_PRODUCT = "Breach Vault";
export const LEAK_RADAR_PRODUCT = "Leak Radar";
export const EXPOSURE_INTEL_PRODUCT = "Exposure Intel";

export type BreachProviderId = "dehashed" | "leakcheck";

const PROVIDER_PRODUCTS: Record<BreachProviderId, string> = {
  dehashed: BREACH_VAULT_PRODUCT,
  leakcheck: LEAK_RADAR_PRODUCT,
};

export function breachProviderDisplayName(provider: BreachProviderId): string {
  return PROVIDER_PRODUCTS[provider];
}

export function breachProviderStatusLabel(available: boolean): string {
  return available ? "Live" : "Standby";
}

export function breachProviderChipLabel(
  provider: BreachProviderId,
  available: boolean,
): string {
  return `${breachProviderDisplayName(provider)} ${breachProviderStatusLabel(available)}`;
}
