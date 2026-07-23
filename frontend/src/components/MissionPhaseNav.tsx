import type { PhaseView } from "../hooks/useMission";
import { PHASE_LABELS } from "../lib/summarizeFinding";

type Props = {
  phases: PhaseView[];
  runningIndex: number;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
};

function phaseLabel(name: string): string {
  return PHASE_LABELS[name] ?? name.replace(/_/g, " ");
}

export function MissionPhaseNav({
  phases,
  runningIndex,
  selectedIndex,
  onSelect,
}: Props) {
  if (phases.length === 0) return null;

  return (
    <nav className="mission-phase-nav" aria-label="Jump to step">
      <div className="mission-phase-nav__track">
        {phases.map((phase, index) => {
          const active = index === runningIndex;
          const selected = selectedIndex === index;
          return (
            <button
              key={`${phase.name}-${index}`}
              type="button"
              className={[
                "mission-phase-nav__pill",
                `mission-phase-nav__pill--${phase.state}`,
                active ? "mission-phase-nav__pill--live" : "",
                selected ? "mission-phase-nav__pill--selected" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-current={selected ? "step" : undefined}
              onClick={() => onSelect(index)}
            >
              <span className="mission-phase-nav__idx">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="mission-phase-nav__label">{phaseLabel(phase.name)}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
