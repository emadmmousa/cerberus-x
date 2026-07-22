import { MarketingLayout } from "../components/MarketingChrome";

export function Privacy() {
  return (
    <MarketingLayout>
      <article className="legal panel">
        <div className="section-label">Legal</div>
        <h1>Privacy Policy</h1>
        <p className="section-sub">Last updated: {new Date().getFullYear()}</p>

        <h2>1. Overview</h2>
        <p>
          Firebreak (“we”, “us”) provides an authorized offensive-security and
          defensive-hardening platform. This policy explains what data we collect and how
          we use it. Firebreak is intended solely for security testing of systems you own
          or are explicitly authorized to assess.
        </p>

        <h2>2. Information we collect</h2>
        <ul>
          <li>
            <strong>Account data:</strong> username, organization, role, and hashed
            credentials.
          </li>
          <li>
            <strong>Engagement data:</strong> authorized targets, mission
            configurations, tool output, findings, and audit events you generate.
          </li>
          <li>
            <strong>Operational data:</strong> logs, metrics, and diagnostics needed to
            run and secure the service.
          </li>
        </ul>

        <h2>3. How we use data</h2>
        <p>
          We use your data to operate the platform, execute the missions you launch,
          produce reports, maintain an audit trail, secure the service, and provide
          support. We do not sell your personal data.
        </p>

        <h2>4. Authorization &amp; responsibility</h2>
        <p>
          You are solely responsible for ensuring you hold written authorization for
          every target you assess with Firebreak. You must not use the platform against
          systems you are not authorized to test.
        </p>

        <h2>5. Data retention &amp; security</h2>
        <p>
          Engagement data is retained for the life of your organization or until you
          delete it. Credentials are stored using salted, hashed password derivation. We
          apply role-based access control and per-organization isolation.
        </p>

        <h2>6. Your rights</h2>
        <p>
          You may access, export, or delete your organization’s data by contacting your
          administrator or our support team.
        </p>

        <h2>7. Contact</h2>
        <p>
          Questions about this policy? Reach us at{" "}
          <a href="mailto:privacy@firebreak.dev">privacy@firebreak.dev</a>.
        </p>
      </article>
    </MarketingLayout>
  );
}
