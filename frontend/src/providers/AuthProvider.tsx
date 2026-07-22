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
  localSignup,
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
  signup: (user: string, pass: string, org?: string) => Promise<void>;
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

  const signup = useCallback(
    async (user: string, pass: string, org?: string) => {
      await localSignup(user, pass, org);
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    // Route by the *actual* session method, not merely whether Auth0 is
    // configured — otherwise local sessions get bounced to Auth0 and back.
    const method = me?.auth_method;
    try {
      await logoutSession();
    } catch {
      /* ignore */
    }
    setMe(null);
    if (method === "auth0") {
      window.location.assign("/logout");
      return;
    }
    // Hard navigation guarantees a clean, unauthenticated app state regardless
    // of whether RBAC enforcement is on.
    window.location.assign("/login");
  }, [me]);

  const ssoHref = oidc?.login_path || "/auth/sso";

  const value = useMemo(
    () => ({
      me,
      oidc,
      loading,
      refresh,
      can,
      loginLocal,
      signup,
      logout,
      ssoHref,
    }),
    [me, oidc, loading, refresh, can, loginLocal, signup, logout, ssoHref],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth requires AuthProvider");
  return ctx;
}
