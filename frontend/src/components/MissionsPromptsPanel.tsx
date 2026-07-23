import { AggressivePromptDeck } from "./AggressivePromptDeck";
import type { AggressivePrompt } from "../lib/aggressivePrompts";

type Props = {
  disabled?: boolean;
  onSelectPrompt: (prompt: AggressivePrompt) => void;
};

export function MissionsPromptsPanel({
  disabled = false,
  onSelectPrompt,
}: Props) {
  return (
    <section className="panel ops-prompts-panel" aria-label="Strike library">
      <div className="ops-prompts-panel__scroll">
        <AggressivePromptDeck disabled={disabled} onSelect={onSelectPrompt} />
      </div>
    </section>
  );
}
