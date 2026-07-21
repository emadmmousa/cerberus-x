import { useEffect, useState } from "react";

type AuthState = {
  authenticated?: boolean;
  user?: string;
  role?: string;
  org_id?: string;
};

type OidcState = {
  configured?: boolean;
  provider?: string;
  login_path?: string;
  domain?: string | null;
  client_id_set?: boolean;
  missing?: string[];
};

export function AuthStrip() {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [oidc, setOidc] = useState<OidcState | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/auth/status").then((r) => r.json()),
      fetch("/api/oidc/status").then((r) => r.json()),
    ])
      .then(([a, o]) => {
        if (cancelled) return;
        setAuth(a);
        setOidc(o);
      })
      .catch(() => {
        /* ignore */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loginHref = oidc?.login_path || "/login";
  const provider = oidc?.provider === "auth0" ? "Auth0" : "SSO";

  return (
    <div
      className="arsenal__note"
      style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}
    >
      {auth?.authenticated ? (
        <>
          <span>
            {auth.user}
            {auth.role ? ` · ${auth.role}` : ""}
            {auth.org_id ? ` · org ${auth.org_id}` : ""}
          </span>
          <a href="/logout">Logout</a>
        </>
      ) : (
        <span>local session</span>
      )}
      {oidc?.configured && !auth?.authenticated && (
        <>
          <a href={loginHref}>Sign in ({provider})</a>
          {oidc.provider === "auth0" && (
            <a href={`${loginHref}?screen_hint=signup`}>Signup</a>
          )}
        </>
      )}
      {!oidc?.configured &&
        (oidc?.domain || oidc?.client_id_set) &&
        Array.isArray(oidc.missing) &&
        oidc.missing.length > 0 && (
          <span title={oidc.missing.join(", ")}>
            Auth0 incomplete — set {oidc.missing.join(", ")}
          </span>
        )}
    </div>
  );
}
