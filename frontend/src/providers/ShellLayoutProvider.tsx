import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applySidebarCollapsed,
  persistSidebarCollapsed,
  resolveInitialSidebarCollapsed,
} from "../lib/shellLayout";

type ShellLayoutContextValue = {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
};

const ShellLayoutContext = createContext<ShellLayoutContextValue | null>(null);

export function ShellLayoutProvider({ children }: { children: ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(() =>
    resolveInitialSidebarCollapsed(),
  );

  useEffect(() => {
    applySidebarCollapsed(sidebarCollapsed);
    persistSidebarCollapsed(sidebarCollapsed);
  }, [sidebarCollapsed]);

  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    setSidebarCollapsedState(collapsed);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsedState((prev) => !prev);
  }, []);

  const value = useMemo(
    () => ({ sidebarCollapsed, setSidebarCollapsed, toggleSidebar }),
    [sidebarCollapsed, setSidebarCollapsed, toggleSidebar],
  );

  return (
    <ShellLayoutContext.Provider value={value}>{children}</ShellLayoutContext.Provider>
  );
}

export function useShellLayout(): ShellLayoutContextValue {
  const ctx = useContext(ShellLayoutContext);
  if (!ctx) throw new Error("useShellLayout requires ShellLayoutProvider");
  return ctx;
}
