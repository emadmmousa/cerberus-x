import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";
import { SidebarNavGroup } from "./SidebarNavGroup";
import { ADMIN_SECTIONS, adminPageTitle } from "../lib/adminSections";
import { AI_LAB_SECTIONS, aiLabPageTitle } from "../lib/aiLabSections";
import { useAuth } from "../providers/AuthProvider";
import { useShellLayout } from "../providers/ShellLayoutProvider";

const PRIMARY_NAV = [
  { to: "/missions", label: "Missions", icon: "⌖", minRole: "viewer" as const },
];

function pageTitle(pathname: string): string {
  if (pathname.startsWith("/missions/new")) return "New mission";
  if (pathname.startsWith("/missions/")) return "Mission detail";
  if (pathname.startsWith("/ai-lab")) {
    const section = pathname.replace(/^\/ai-lab\/?/, "") || undefined;
    return aiLabPageTitle(section);
  }
  if (pathname.startsWith("/admin")) {
    const section = pathname.replace(/^\/admin\/?/, "") || undefined;
    return adminPageTitle(section);
  }
  if (pathname.startsWith("/profile")) return "Profile";
  return "Mission control";
}

export function AppShell() {
  const { me, can, logout, loading } = useAuth();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const { sidebarCollapsed, toggleSidebar } = useShellLayout();

  const primaryLinks = PRIMARY_NAV.filter((item) => can(item.minRole));
  const showAiLab = can("operator");
  const showAdmin = can("viewer");
  const collapseLabel = sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar";

  return (
    <div className={`app-shell${sidebarCollapsed ? " app-shell--sidebar-collapsed" : ""}`}>
      {navOpen && (
        <button
          type="button"
          className="app-sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      )}

      <aside
        id="console-nav"
        className={`app-sidebar${navOpen ? " app-sidebar--open" : ""}`}
        aria-label="Console navigation"
        aria-expanded={!sidebarCollapsed}
      >
        <div className="app-sidebar__top">
          <NavLink
            to="/missions"
            className="app-sidebar__brand"
            title="Firebreak"
            onClick={() => setNavOpen(false)}
          >
            <span className="app-sidebar__mark" aria-hidden="true" />
            <span className="app-sidebar__name">Firebreak</span>
          </NavLink>
          <button
            type="button"
            className="app-sidebar__collapse"
            aria-label={collapseLabel}
            title={collapseLabel}
            onClick={toggleSidebar}
          >
            <span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span>
          </button>
        </div>

        <nav className="app-sidebar__nav">
          {primaryLinks.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `app-sidebar__link app-sidebar__link--rail${isActive ? " active" : ""}`
              }
              title={item.label}
              onClick={() => setNavOpen(false)}
            >
              <span className="app-sidebar__icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="app-sidebar__link-text">{item.label}</span>
            </NavLink>
          ))}

          {showAiLab && (
            <SidebarNavGroup
              id="ai-lab"
              label="AI Lab"
              icon="🧪"
              pathname={location.pathname}
              sidebarCollapsed={sidebarCollapsed}
              onNavigate={() => setNavOpen(false)}
              overview={{
                to: "/ai-lab",
                end: true,
                label: "Overview",
                icon: "◉",
              }}
              items={AI_LAB_SECTIONS.map((section) => ({
                to: section.path,
                label: section.label,
                icon: section.icon,
              }))}
            />
          )}

          {showAdmin && (
            <SidebarNavGroup
              id="settings"
              label="Settings"
              icon="⊞"
              pathname={location.pathname}
              sidebarCollapsed={sidebarCollapsed}
              onNavigate={() => setNavOpen(false)}
              overview={{
                to: "/admin",
                end: true,
                label: "Overview",
                icon: "⚙",
              }}
              items={ADMIN_SECTIONS.map((section) => ({
                to: section.path,
                label: section.label,
                icon: section.icon,
              }))}
            />
          )}
        </nav>

        <div className="app-sidebar__footer">
          <ThemeToggle compact={sidebarCollapsed} />
          {loading ? (
            <span className="chip app-sidebar__chip">Loading…</span>
          ) : me?.authenticated ? (
            <>
              <NavLink
                to="/profile"
                className={({ isActive }) =>
                  `app-sidebar__user-link${isActive ? " active" : ""}`
                }
                title="Profile settings"
                onClick={() => setNavOpen(false)}
              >
                <span className="app-sidebar__user-avatar" aria-hidden="true">
                  {(me.user || "?").slice(0, 1).toUpperCase()}
                </span>
                <span className="app-sidebar__user-body">
                  <span className="app-sidebar__user-name">{me.user}</span>
                  {me.role && <span className="app-sidebar__user-role">{me.role}</span>}
                </span>
              </NavLink>
              <button
                type="button"
                className="btn btn--ghost btn--sm app-sidebar__signout"
                title="Sign out"
                onClick={() => void logout()}
              >
                <span className="app-sidebar__signout-icon" aria-hidden="true">
                  ⎋
                </span>
                <span className="app-sidebar__signout-text">Sign out</span>
              </button>
            </>
          ) : (
            <NavLink className="btn btn--primary btn--sm" to="/login" title="Sign in">
              <span className="app-sidebar__signout-text">Sign in</span>
            </NavLink>
          )}
        </div>
      </aside>

      <div className="app-content">
        <header className="app-topbar">
          <button
            type="button"
            className="app-topbar__menu"
            aria-expanded={navOpen}
            aria-controls="console-nav"
            onClick={() => setNavOpen((v) => !v)}
          >
            Menu
          </button>
          <button
            type="button"
            className="app-topbar__collapse"
            aria-label={collapseLabel}
            title={collapseLabel}
            onClick={toggleSidebar}
          >
            <span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span>
          </button>
          <h1 className="app-topbar__title">{pageTitle(location.pathname)}</h1>
          <span className="app-topbar__hint">Authorized engagements only</span>
        </header>
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
