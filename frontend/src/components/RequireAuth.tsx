import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../providers/AuthProvider";

type Props = {
  minRole?: "viewer" | "operator" | "admin";
  children: React.ReactNode;
};

export function RequireAuth({ minRole = "viewer", children }: Props) {
  const { me, loading, can } = useAuth();
  const location = useLocation();

  if (loading) {
    return <p className="result-card__meta">Loading session…</p>;
  }

  if (me?.rbac_enforce && !me.authenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  if (!can(minRole)) {
    return (
      <section className="panel">
        <div className="section-label">Locked</div>
        <p className="error-text">
          Requires role <strong>{minRole}</strong>
          {me?.role ? ` (you are ${me.role})` : ""}.
        </p>
      </section>
    );
  }

  return <>{children}</>;
}
