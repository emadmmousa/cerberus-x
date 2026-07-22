import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../providers/AuthProvider";

export function Login() {
  const { loginLocal, ssoHref, oidc, me, refresh } = useAuth();
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/missions";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginLocal(user, pass);
      await refresh();
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  if (me?.authenticated) {
    return (
      <section className="panel launch" aria-label="Already signed in">
        <div className="login-panel__chrome">
          <ThemeToggle />
        </div>
        <div className="section-label">Session</div>
        <p>
          Signed in as {me.user} ({me.role}).
        </p>
        <Link className="btn btn--primary" to="/missions">
          Missions
        </Link>
      </section>
    );
  }

  return (
    <section className="panel launch login-panel" aria-label="Sign in">
      <div className="login-panel__chrome">
        <ThemeToggle />
      </div>
      <Link to="/" className="login-panel__back">
        ← Back to home
      </Link>
      <h1 className="login-panel__title">Firebreak</h1>
      <p className="result-card__meta">Authorized operators only. SSO-first session.</p>

      {oidc?.configured && (
        <p style={{ marginTop: "1rem" }}>
          <a className="btn btn--primary" href={ssoHref}>
            Sign in with {oidc.provider === "auth0" ? "Auth0" : "SSO"}
          </a>
        </p>
      )}

      <form className="options" onSubmit={(e) => void onSubmit(e)} style={{ marginTop: "1.25rem" }}>
        <div className="section-label">Local</div>
        <div className="field">
          <label htmlFor="user">Username</label>
          <input
            id="user"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            autoComplete="username"
          />
        </div>
        <div className="field">
          <label htmlFor="pass">Password</label>
          <input
            id="pass"
            type="password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button type="submit" className="btn btn--primary" disabled={busy || !pass}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="login-panel__alt">
        New to Firebreak? <Link to="/signup">Create an account</Link>
      </p>
    </section>
  );
}
