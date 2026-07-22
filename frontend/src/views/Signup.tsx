import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../providers/AuthProvider";

export function Signup() {
  const { signup, me } = useAuth();
  const [user, setUser] = useState("");
  const [org, setOrg] = useState("");
  const [pass, setPass] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (pass !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (pass.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signup(user.trim(), pass, org.trim() || undefined);
      navigate("/missions", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  if (me?.authenticated) {
    return (
      <section className="panel launch login-panel" aria-label="Already signed in">
        <div className="login-panel__chrome">
          <ThemeToggle />
        </div>
        <h1 className="login-panel__title">Firebreak</h1>
        <p>Signed in as {me.user}.</p>
        <Link className="btn btn--primary" to="/missions">
          Open console
        </Link>
      </section>
    );
  }

  return (
    <section className="panel launch login-panel" aria-label="Create account">
      <div className="login-panel__chrome">
        <ThemeToggle />
      </div>
      <Link to="/" className="login-panel__back">
        ← Back to home
      </Link>
      <h1 className="login-panel__title">Create your account</h1>
      <p className="result-card__meta">
        Start a Firebreak org for your authorized engagements.
      </p>

      <form className="options" onSubmit={(e) => void onSubmit(e)} style={{ marginTop: "1.25rem" }}>
        <div className="field">
          <label htmlFor="user">Username</label>
          <input
            id="user"
            value={user}
            onChange={(e) => setUser(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="org">Organization (optional)</label>
          <input
            id="org"
            value={org}
            onChange={(e) => setOrg(e.target.value)}
            placeholder="Acme Red Team"
            autoComplete="organization"
          />
        </div>
        <div className="field">
          <label htmlFor="pass">Password</label>
          <input
            id="pass"
            type="password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="confirm">Confirm password</label>
          <input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button
          type="submit"
          className="btn btn--primary"
          disabled={busy || !user.trim() || !pass}
        >
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="login-panel__alt">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </section>
  );
}
