import { OsintTargetPanel } from "./OsintTargetPanel";
import type { OsintSeed } from "../lib/osintTargets";

type Props = {
  seeds: OsintSeed[];
  onChange: (seeds: OsintSeed[]) => void;
  disabled?: boolean;
};

export function OsintTabPanel({ seeds, onChange, disabled = false }: Props) {
  return (
    <section className="panel ops-osint-panel" aria-label="OSINT targets">
      <header className="ops-osint-panel__head">
        <h2 className="ops-osint-panel__title">OSINT targets</h2>
        <p className="ops-osint-panel__lead">
          Configure identifiers used by chat missions, strike prompts, and breach lookups.
          These seeds stay separate from the agent conversation.
        </p>
      </header>
      <OsintTargetPanel seeds={seeds} onChange={onChange} disabled={disabled} />
    </section>
  );
}
