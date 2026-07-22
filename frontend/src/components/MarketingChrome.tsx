import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../providers/AuthProvider";

export function MarketingLayout({ children }: { children: ReactNode }) {
  const { me } = useAuth();

  return (
    <div className="marketing">
      <header className="marketing-nav">
        <Link to="/" className="marketing-nav__brand">
          Firebreak
        </Link>
        <nav className="marketing-nav__links" aria-label="Marketing">
          <a href="/#features">Platform</a>
          <a href="/#pricing">Pricing</a>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </nav>
        <div className="marketing-nav__cta">
          <ThemeToggle />
          {me?.authenticated ? (
            <Link className="btn btn--primary" to="/missions">
              Open console
            </Link>
          ) : (
            <>
              <Link className="link-btn" to="/login">
                Sign in
              </Link>
              <Link className="btn btn--primary" to="/signup">
                Start free
              </Link>
            </>
          )}
        </div>
      </header>

      <main className="marketing-main">{children}</main>

      <footer className="marketing-footer">
        <div className="marketing-footer__brand">
          <span className="marketing-nav__brand">Firebreak</span>
          <p className="section-sub">
            Authorized offensive security &amp; defensive hardening, orchestrated.
          </p>
        </div>
        <nav className="marketing-footer__links" aria-label="Footer">
          <a href="/#features">Platform</a>
          <a href="/#pricing">Pricing</a>
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
          <Link to="/login">Sign in</Link>
        </nav>
        <p className="marketing-footer__legal">
          © {new Date().getFullYear()} Firebreak. For authorized security testing
          only.
        </p>
      </footer>
    </div>
  );
}
