import { AuditStrip } from "../components/AuditStrip";
import { AiLabPanel } from "../components/AiLabPanel";

export function AiLab() {
  return (
    <div className="mission">
      <section className="panel launch" aria-label="AI Lab">
        <div className="section-label">AI Lab</div>
        <p className="result-card__meta">
          Multi-scaffold status, marketplace, and authorized dataset contribute.
        </p>
      </section>
      <AiLabPanel />
      <AuditStrip />
    </div>
  );
}
