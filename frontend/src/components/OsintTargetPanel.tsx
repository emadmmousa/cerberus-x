import { useEffect, useMemo, useState } from "react";
import { fetchBreachIntelStatus, type BreachProviderStatus } from "../api/client";
import {
  breachProviderChipLabel,
  EXPOSURE_INTEL_PRODUCT,
} from "../lib/breachIntelBranding";
import {
  mergeOsintSeeds,
  normalizeOsintSeed,
  OSINT_TARGET_KINDS,
  osintKindLabel,
  osintSeedLabel,
  validateOsintSeed,
  type OsintSeed,
  type OsintTargetKind,
} from "../lib/osintTargets";

type Props = {
  seeds: OsintSeed[];
  onChange: (seeds: OsintSeed[]) => void;
  disabled?: boolean;
};

export function OsintTargetPanel({ seeds, onChange, disabled = false }: Props) {
  const [kind, setKind] = useState<OsintTargetKind>("domain");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(seeds.length > 0);
  const [breachStatus, setBreachStatus] = useState<BreachProviderStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchBreachIntelStatus()
      .then((status) => {
        if (!cancelled) setBreachStatus(status);
      })
      .catch(() => {
        if (!cancelled) setBreachStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const kindMeta = useMemo(
    () => OSINT_TARGET_KINDS.find((row) => row.id === kind) ?? OSINT_TARGET_KINDS[0],
    [kind],
  );

  function addSeed() {
    const validation = validateOsintSeed(kind, value);
    if (validation) {
      setError(validation);
      return;
    }
    const seed = normalizeOsintSeed(kind, value);
    onChange(mergeOsintSeeds(seeds, seed));
    setValue("");
    setError(null);
    setExpanded(true);
  }

  function removeSeed(seed: OsintSeed) {
    onChange(seeds.filter((row) => !(row.kind === seed.kind && row.value === seed.value)));
  }

  return (
    <section className="osint-panel" aria-label="OSINT targets">
      <div className="osint-panel__head">
        <button
          type="button"
          className="osint-panel__toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          <span className="osint-panel__title">OSINT targets</span>
          <span className="osint-panel__summary">
            {seeds.length > 0
              ? `${seeds.length} seed${seeds.length === 1 ? "" : "s"} set`
              : "Set one or more identifiers for OSINT"}
          </span>
        </button>
      </div>

      {expanded && (
        <div className="osint-panel__body">
          <p className="osint-panel__hint">
            Add social URL, username, full name, mobile, email, or domain. Firebreak scrapes
            public and hidden sources and matches leaked records to these seeds only — no vuln
            scans or exploitation.
          </p>

          {breachStatus && (
            <div className="osint-panel__providers" aria-label={`${EXPOSURE_INTEL_PRODUCT} sources`}>
              <span
                className={`osint-panel__provider${breachStatus.breach_vault.available ? " osint-panel__provider--on" : ""}`}
              >
                {breachProviderChipLabel("dehashed", breachStatus.breach_vault.available)}
              </span>
              <span
                className={`osint-panel__provider${breachStatus.leak_radar.available ? " osint-panel__provider--on" : ""}`}
              >
                {breachProviderChipLabel("leakcheck", breachStatus.leak_radar.available)}
              </span>
            </div>
          )}

          <div className="osint-panel__form">
            <label className="osint-panel__field">
              <span>Identifier type</span>
              <select
                value={kind}
                disabled={disabled}
                onChange={(e) => setKind(e.target.value as OsintTargetKind)}
                aria-label="OSINT identifier type"
              >
                {OSINT_TARGET_KINDS.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="osint-panel__field osint-panel__field--grow">
              <span>{kindMeta.label}</span>
              <input
                value={value}
                disabled={disabled}
                placeholder={kindMeta.placeholder}
                onChange={(e) => {
                  setValue(e.target.value);
                  if (error) setError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addSeed();
                  }
                }}
                aria-label={kindMeta.label}
              />
            </label>
            <button type="button" className="btn btn--sm" disabled={disabled} onClick={addSeed}>
              Add
            </button>
          </div>

          {error && <p className="error-text osint-panel__error">{error}</p>}

          {seeds.length > 0 ? (
            <ul className="osint-panel__chips">
              {seeds.map((seed) => (
                <li key={`${seed.kind}:${seed.value}`} className="osint-panel__chip">
                  <span className="osint-panel__chip-kind">{osintKindLabel(seed.kind)}</span>
                  <span className="osint-panel__chip-value">{osintSeedLabel(seed)}</span>
                  <button
                    type="button"
                    className="osint-panel__chip-remove"
                    disabled={disabled}
                    aria-label={`Remove ${osintSeedLabel(seed)}`}
                    onClick={() => removeSeed(seed)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="osint-panel__empty">No OSINT seeds yet.</p>
          )}
        </div>
      )}
    </section>
  );
}
