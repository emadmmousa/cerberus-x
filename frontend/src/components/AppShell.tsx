import { NavLink, Outlet } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../providers/AuthProvider";

export function AppShell() {
  const { me, can, logout, loading } = useAuth();

  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Primary">
        <NavLink to="/missions" className="app-nav__brand">
          Firebreak
        </NavLink>
        <div className="app-nav__links">
          <NavLink to="/missions">Missions</NavLink>
          {can("operator") && <NavLink to="/ai-lab">AI Lab</NavLink>}
          <NavLink to="/admin">Admin</NavLink>
        </div>
        <div className="app-nav__user">
          <ThemeToggle />
          {loading ? (
            <span className="chip">…</span>
          ) : me?.authenticated ? (
            <>
              <span className="chip">
                {me.user}
                {me.role ? ` · ${me.role}` : ""}
              </span>
              <button type="button" className="link-btn" onClick={() => void logout()}>
                Logout
              </button>
            </>
          ) : (
            <NavLink to="/login">Sign in</NavLink>
          )}
        </div>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
