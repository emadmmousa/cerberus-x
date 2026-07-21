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
  getAuthStatus,
  getOidcStatus,
  getRbacMe,
  localLogin,
  logoutSession,
  type OidcStatus,
  type RbacMe,
} from "../api/client";

const RANK: Record<string, number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
};

type AuthContextValue = {
  me: RbacMe | null;
  oidc: OidcStatus | null;
  loading: boolean;
  refresh: () => Promise<void>;
  can: (minRole: "viewer" | "operator" | "admin") => boolean;
  loginLocal: (user: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  ssoHref: string;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<RbacMe | null>(null);
  const [oidc, setOidc] = useState<OidcStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [rbac, auth, oidcStatus] = await Promise.all([
        getRbacMe(true),
        getAuthStatus(),
        getOidcStatus(),
      ]);
      setMe({
        ...rbac,
        authenticated: Boolean(auth.authenticated ?? rbac.authenticated),
        user: auth.user ?? rbac.user,
        role: auth.role ?? rbac.role,
        org_id: auth.org_id ?? rbac.org_id,
        auth_method: auth.auth_method ?? rbac.auth_method,
      });
      setOidc(oidcStatus);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const can = useCallback(
    (minRole: "viewer" | "operator" | "admin") => {
      if (!me?.rbac_enforce) return true;
      if (!me.authenticated) return false;
      const have = RANK[(me.role || "viewer").toLowerCase()] ?? 0;
      return have >= (RANK[minRole] ?? 99);
    },
    [me],
  );

  const loginLocal = useCallback(
    async (user: string, pass: string) => {
      await localLogin(user, pass);
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    try {
      await logoutSession();
    } catch {
      /* ignore */
    }
    if (oidc?.configured && oidc.provider === "auth0") {
      window.location.assign("/logout");
      return;
    }
    await refresh();
  }, [oidc, refresh]);

  const ssoHref = oidc?.login_path || "/auth/sso";

  const value = useMemo(
    () => ({
      me,
      oidc,
      loading,
      refresh,
      can,
      loginLocal,
      logout,
      ssoHref,
    }),
    [me, oidc, loading, refresh, can, loginLocal, logout, ssoHref],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth requires AuthProvider");
  return ctx;
}
