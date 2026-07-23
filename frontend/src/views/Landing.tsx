import { useState } from "react";
import { Link } from "react-router-dom";
import { MarketingLayout } from "../components/MarketingChrome";
import {
  PRICING,
  type BillingCycle,
  formatUsd,
  monthlyEquivalent,
  priceFor,
} from "../lib/pricing";

const FEATURES = [
  {
    title: "AI red-team agent",
    body: "Chat through any cyber topic, plan staged kill-chains, and launch authorized missions with one confirm.",
  },
  {
    title: "Dual-mode orchestration",
    body: "Aggressive proof-of-impact and defensive hardening from the same run — recon to post-exploitation to remediation.",
  },
  {
    title: "Wrapped tooling arsenal",
    body: "nmap, nuclei, ffuf, sqlmap, Metasploit, hydra and more — flag-safe wrappers behind an allowlist.",
  },
  {
    title: "Scoped & auditable",
    body: "Every mission is bound to your authorized targets, with full audit trail, Access Guard, and org isolation.",
  },
];

const PHASES = [
  ["01", "Recon", "Discover surface: ports, stacks, subdomains, tech fingerprints."],
  ["02", "Discovery", "Map content and endpoints with fuzzing and enumeration."],
  ["03", "Proof of impact", "Exploit vulns and stage payloads to prove real risk."],
  ["04", "Harden", "Convert findings into prioritized, actionable remediation."],
];

export function Landing() {
  const [cycle, setCycle] = useState<BillingCycle>("monthly");
  const [targets, setTargets] = useState(1);
  const plan = PRICING[cycle];
  const total = priceFor(cycle, targets);

  return (
    <MarketingLayout>
      <section className="hero">
        <span className="hero__eyebrow">Authorized offensive security platform</span>
        <h1 className="hero__title">
          Break in first. <span className="hero__accent">Then lock it down.</span>
        </h1>
        <p className="hero__lede">
          Firebreak is an AI-driven red-team console for authorized engagements. Plan
          powerful attack chains in chat, launch scoped missions, prove impact, and turn
          every finding into hardening — all in one orchestrated workflow.
        </p>
        <div className="hero__cta">
          <Link className="btn btn--primary btn--lg" to="/signup">
            Start free
          </Link>
          <Link className="btn btn--ghost btn--lg" to="/missions">
            Open console
          </Link>
          <a className="btn btn--ghost btn--lg" href="#pricing">
            See pricing
          </a>
        </div>
        <div className="hero__meta">
          <span>Per-target licensing</span>
          <span aria-hidden="true">·</span>
          <span>Full audit trail</span>
          <span aria-hidden="true">·</span>
          <span>Offense + defense</span>
        </div>
      </section>

      <section className="feature-grid" id="features">
        {FEATURES.map((f) => (
          <article key={f.title} className="feature-card panel">
            <h3>{f.title}</h3>
            <p className="section-sub">{f.body}</p>
          </article>
        ))}
      </section>

      <section className="workflow">
        <div className="section-label">The Firebreak loop</div>
        <div className="workflow__phases">
          {PHASES.map(([n, title, body]) => (
            <div key={n} className="workflow__phase panel">
              <span className="workflow__num">{n}</span>
              <h3>{title}</h3>
              <p className="section-sub">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="pricing" id="pricing">
        <div className="pricing__head">
          <div className="section-label">Pricing</div>
          <h2>One authorized target included. Scale by seat.</h2>
          <p className="section-sub">
            Every plan covers one authorized Target / URL / App. Add more targets as
            your engagement grows.
          </p>
          <div className="pricing__toggle" role="tablist" aria-label="Billing cycle">
            {(["monthly", "yearly"] as BillingCycle[]).map((c) => (
              <button
                key={c}
                type="button"
                role="tab"
                aria-selected={cycle === c}
                className={`admin-tab${cycle === c ? " admin-tab--active" : ""}`}
                onClick={() => setCycle(c)}
              >
                {PRICING[c].label}
                {c === "yearly" && <span className="pricing__save">save ~17%</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="pricing__cards">
          <article className="pricing-card panel">
            <div className="section-label">Base</div>
            <div className="pricing-card__price">
              {formatUsd(plan.base)}
              <span className="pricing-card__unit">{plan.unit}</span>
            </div>
            <p className="section-sub">One authorized Target / URL / App.</p>
            <ul className="pricing-card__list">
              <li>AI red-team chat &amp; mission launch</li>
              <li>Full tooling arsenal + wrappers</li>
              <li>Offense + defensive hardening reports</li>
              <li>Audit trail &amp; Access Guard</li>
            </ul>
            <Link className="btn btn--primary" to="/signup">
              Start free
            </Link>
          </article>

          <article className="pricing-card panel pricing-card--feature">
            <div className="section-label">Additional seats</div>
            <div className="pricing-card__price">
              {formatUsd(plan.seat)}
              <span className="pricing-card__unit">{plan.unit} / target</span>
            </div>
            <p className="section-sub">
              Each extra authorized Target / URL / App adds a seat.
            </p>

            <div className="pricing-calc">
              <label htmlFor="targets">
                Authorized targets: <strong>{targets}</strong>
              </label>
              <input
                id="targets"
                type="range"
                min={1}
                max={25}
                value={targets}
                onChange={(e) => setTargets(Number(e.target.value))}
              />
              <div className="pricing-calc__total">
                <span className="pricing-card__price">
                  {formatUsd(total)}
                  <span className="pricing-card__unit">{plan.unit}</span>
                </span>
                {cycle === "yearly" && (
                  <span className="section-sub">
                    ≈ {formatUsd(monthlyEquivalent(cycle, targets))}/mo billed yearly
                  </span>
                )}
              </div>
              <p className="section-sub">
                {targets === 1
                  ? "Base plan — 1 target included."
                  : `${targets} targets = base + ${targets - 1} seat${targets - 1 > 1 ? "s" : ""}.`}
              </p>
            </div>

            <Link className="btn btn--primary" to="/signup">
              Get started
            </Link>
          </article>
        </div>
      </section>

      <section className="cta-band panel">
        <h2>Ready to run your first authorized mission?</h2>
        <p className="section-sub">
          Spin up an org, add your authorized target, and let the agent plan the rest.
        </p>
        <Link className="btn btn--primary btn--lg" to="/signup">
          Create your account
        </Link>
      </section>
    </MarketingLayout>
  );
}
