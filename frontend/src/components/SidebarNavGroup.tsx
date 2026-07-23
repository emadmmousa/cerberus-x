import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  persistNavGroupExpanded,
  resolveNavGroupExpanded,
  type NavGroupId,
} from "../lib/shellLayout";

export type SidebarNavItem = {
  to: string;
  end?: boolean;
  label: string;
  icon: string;
};

type Props = {
  id: NavGroupId;
  label: string;
  icon: string;
  pathname: string;
  sidebarCollapsed: boolean;
  overview?: SidebarNavItem;
  items: SidebarNavItem[];
  onNavigate?: () => void;
};

export function SidebarNavGroup({
  id,
  label,
  icon,
  pathname,
  sidebarCollapsed,
  overview,
  items,
  onNavigate,
}: Props) {
  const [expanded, setExpanded] = useState(() => resolveNavGroupExpanded(id, pathname));
  const prefix = id === "ai-lab" ? "/ai-lab" : "/admin";
  const isActiveGroup = pathname.startsWith(prefix);

  useEffect(() => {
    if (isActiveGroup && !expanded) {
      setExpanded(true);
      persistNavGroupExpanded(id, true);
    }
  }, [expanded, id, isActiveGroup]);

  function toggleExpanded() {
    setExpanded((open) => {
      const next = !open;
      persistNavGroupExpanded(id, next);
      return next;
    });
  }

  const links = overview ? [overview, ...items] : items;

  if (sidebarCollapsed && overview) {
    return (
      <div
        className={`app-sidebar__group app-sidebar__group--rail${
          isActiveGroup ? " app-sidebar__group--active" : ""
        }`}
      >
        <NavLink
          to={overview.to}
          end={overview.end}
          className={({ isActive }) =>
            `app-sidebar__link app-sidebar__link--rail${isActive ? " active" : ""}`
          }
          title={label}
          onClick={onNavigate}
        >
          <span className="app-sidebar__icon" aria-hidden="true">
            {icon}
          </span>
          <span className="app-sidebar__link-text">{label}</span>
        </NavLink>
      </div>
    );
  }

  return (
    <div
      className={`app-sidebar__group${expanded ? " app-sidebar__group--open" : ""}${
        isActiveGroup ? " app-sidebar__group--active" : ""
      }`}
    >
      <button
        type="button"
        className="app-sidebar__group-toggle"
        aria-expanded={expanded}
        aria-controls={`nav-group-${id}`}
        title={sidebarCollapsed ? label : undefined}
        onClick={toggleExpanded}
      >
        <span className="app-sidebar__icon app-sidebar__group-icon" aria-hidden="true">
          {icon}
        </span>
        <span className="app-sidebar__group-label">{label}</span>
        <span className="app-sidebar__group-chevron" aria-hidden="true" />
      </button>

      {expanded && (
        <div id={`nav-group-${id}`} className="app-sidebar__group-items">
          {links.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `app-sidebar__link app-sidebar__link--sub${isActive ? " active" : ""}`
              }
              title={item.label}
              onClick={onNavigate}
            >
              <span className="app-sidebar__icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="app-sidebar__link-text">{item.label}</span>
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}
