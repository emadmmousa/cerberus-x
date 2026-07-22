import { MarketingLayout } from "../components/MarketingChrome";

export function Terms() {
  return (
    <MarketingLayout>
      <article className="legal panel">
        <div className="section-label">Legal</div>
        <h1>Terms of Service</h1>
        <p className="section-sub">Last updated: {new Date().getFullYear()}</p>

        <h2>1. Acceptance</h2>
        <p>
          By creating an account or using Firebreak, you agree to these Terms. If you use
          Firebreak on behalf of an organization, you represent that you have authority
          to bind that organization.
        </p>

        <h2>2. Authorized use only</h2>
        <p>
          Firebreak is a security-testing tool for <strong>authorized engagements</strong>{" "}
          only. You may use it exclusively against systems, targets, URLs, and
          applications that you own or for which you hold explicit, documented
          authorization. Any unauthorized scanning, exploitation, or access is strictly
          prohibited and may violate law. You are solely responsible for your use.
        </p>

        <h2>3. Acceptable conduct</h2>
        <ul>
          <li>Maintain valid written authorization for every target you assess.</li>
          <li>Do not target third parties or systems outside your authorized scope.</li>
          <li>Do not use the platform for fraud, extortion, or other illegal activity.</li>
          <li>Comply with all applicable laws and contractual obligations.</li>
        </ul>

        <h2>4. Subscriptions &amp; billing</h2>
        <p>
          Plans are licensed per authorized Target / URL / App. The base plan includes
          one target at {"$200/month or $2,000/year"}; each additional target seat is
          {" $180"} per billing period. Fees are billed in advance and are non-refundable
          except where required by law.
        </p>

        <h2>5. Service &amp; availability</h2>
        <p>
          We provide the platform on an “as is” and “as available” basis. We may modify,
          suspend, or discontinue features at any time.
        </p>

        <h2>6. Limitation of liability</h2>
        <p>
          To the maximum extent permitted by law, Firebreak is not liable for any
          indirect, incidental, or consequential damages, or for any loss arising from
          your use of the platform, including unauthorized or out-of-scope testing.
        </p>

        <h2>7. Termination</h2>
        <p>
          We may suspend or terminate access for violation of these Terms, including any
          unauthorized use. You may cancel your subscription at any time.
        </p>

        <h2>8. Contact</h2>
        <p>
          Questions about these Terms? Reach us at{" "}
          <a href="mailto:legal@firebreak.dev">legal@firebreak.dev</a>.
        </p>
      </article>
    </MarketingLayout>
  );
}
