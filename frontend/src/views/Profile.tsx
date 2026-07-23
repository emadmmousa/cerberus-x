import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  checkUsernameAvailable,
  getProfile,
  updateProfile,
  ApiError,
  type RbacMe,
  type UserProfile,
} from "../api/client";
import { PageHero } from "../components/PageHero";
import { PasswordRequirements } from "../components/PasswordRequirements";
import { passwordMeetsRequirements } from "../lib/passwordValidation";
import { useAuth } from "../providers/AuthProvider";

function formatTimestamp(value?: number | null): string {
  if (!value) return "—";
  const date = new Date(value * 1000);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function profileFromSession(me: RbacMe): UserProfile {
  return {
    username: me.user ?? "",
    role: me.role,
    org_id: me.org_id,
    auth_method: me.auth_method ?? undefined,
    disabled: false,
    has_password: false,
    can_edit_username: false,
    can_edit_password: false,
    can_edit_org_name: false,
    managed_externally: Boolean(me.auth_method && me.auth_method !== "local"),
  };
}

export function Profile() {
  const { me, refresh } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

  const [username, setUsername] = useState("");
  const [orgName, setOrgName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [usernameCheck, setUsernameCheck] = useState<{
    state: "idle" | "checking" | "ok" | "taken" | "invalid";
    message?: string;
  }>({ state: "idle" });
  const [busy, setBusy] = useState(false);

  const flash = useCallback((kind: "ok" | "err", msg: string) => {
    setBanner({ kind, msg });
    window.setTimeout(() => setBanner(null), 4000);
  }, []);

  useEffect(() => {
    if (!me || !me.authenticated) {
      setLoading(false);
      setProfile(null);
      setError("Sign in to manage your profile.");
      return;
    }

    const authMe = me;
    let cancelled = false;

    async function load(attempt = 0) {
      setLoading(true);
      setError(null);
      try {
        const data = await getProfile();
        if (cancelled) return;
        setProfile(data);
        setUsername(data.username || "");
        setOrgName(data.org_name || "");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404 && attempt < 2) {
          await new Promise((resolve) => window.setTimeout(resolve, 1200));
          return load(attempt + 1);
        }
        const fallback = profileFromSession(authMe);
        setProfile(fallback);
        setUsername(fallback.username || "");
        setOrgName(fallback.org_name || "");
        if (err instanceof ApiError && err.status === 404) {
          setError(
            "Profile service is unavailable. Run `docker compose restart orchestrator`, then reload.",
          );
        } else if (!(err instanceof ApiError) || err.status !== 401) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load full profile — showing session details.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [me]);

  const usernameChanged = useMemo(() => {
    if (!profile?.username) return false;
    return username.trim() !== profile.username;
  }, [profile?.username, username]);

  const orgNameChanged = useMemo(() => {
    if (!profile?.can_edit_org_name) return false;
    return orgName.trim() !== (profile.org_name || "");
  }, [profile?.can_edit_org_name, profile?.org_name, orgName]);

  useEffect(() => {
    if (!profile?.can_edit_username || !usernameChanged) {
      setUsernameCheck({ state: "idle" });
      return;
    }
    const candidate = username.trim();
    if (candidate.length < 3) {
      setUsernameCheck({
        state: "invalid",
        message: "Username must be at least 3 characters",
      });
      return;
    }
    setUsernameCheck({ state: "checking" });
    const timer = window.setTimeout(() => {
      void checkUsernameAvailable(candidate)
        .then((res) => {
          if (res.available) {
            setUsernameCheck({ state: "ok", message: "Username is available" });
            return;
          }
          setUsernameCheck({
            state: res.reason ? "invalid" : "taken",
            message: res.reason || "Username is already taken",
          });
        })
        .catch(() => {
          setUsernameCheck({ state: "invalid", message: "Could not check username" });
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [profile?.can_edit_username, username, usernameChanged]);

  const showPasswordRules = newPassword.length > 0 || confirmPassword.length > 0;
  const passwordValid =
    !newPassword || passwordMeetsRequirements(newPassword, confirmPassword);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!profile) return;

    if (newPassword && !passwordMeetsRequirements(newPassword, confirmPassword)) {
      flash("err", "New password does not meet the requirements");
      return;
    }
    if (usernameChanged && usernameCheck.state !== "ok") {
      flash("err", usernameCheck.message || "Choose an available username");
      return;
    }
    if (!currentPassword) {
      flash("err", "Enter your current password to save changes");
      return;
    }

    const payload: {
      current_password: string;
      username?: string;
      new_password?: string;
      org_name?: string;
    } = { current_password: currentPassword };

    if (usernameChanged && profile.can_edit_username) {
      payload.username = username.trim();
    }
    if (newPassword && profile.can_edit_password) {
      payload.new_password = newPassword;
    }
    if (orgNameChanged) {
      payload.org_name = orgName.trim();
    }

    if (!payload.username && !payload.new_password && payload.org_name === undefined) {
      flash("err", "No changes to save");
      return;
    }

    setBusy(true);
    try {
      const updated = await updateProfile(payload);
      setProfile(updated);
      setUsername(updated.username || "");
      setOrgName(updated.org_name || "");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      await refresh();
      flash("ok", "Profile updated");
    } catch (err) {
      flash("err", err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  const managedExternally =
    profile?.managed_externally ||
    (!profile?.can_edit_username && !profile?.can_edit_password && !profile?.can_edit_org_name);

  return (
    <div className="profile-workspace">
      <PageHero
        crumbs={[{ label: "Console", to: "/missions" }, { label: "Profile" }]}
        title="Profile"
        lede="Manage your account, credentials, and organization details."
        error={error}
      />

      {banner && (
        <p
          className={`profile-banner profile-banner--${banner.kind}`}
          role="status"
          aria-live="polite"
        >
          {banner.msg}
        </p>
      )}

      {loading ? (
        <p className="result-card__meta">Loading profile…</p>
      ) : profile ? (
        <form className="profile-grid" onSubmit={(e) => void onSubmit(e)}>
          <section className="panel profile-card" aria-labelledby="profile-account">
            <h2 id="profile-account" className="profile-card__title">
              Account
            </h2>
            <p className="profile-card__lede">
              Your sign-in name across Firebreak. Usernames must be unique.
            </p>
            <div className="field">
              <label htmlFor="profile-username">Username</label>
              <input
                id="profile-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                disabled={!profile.can_edit_username || busy}
                required
              />
              {profile.can_edit_username && usernameChanged && usernameCheck.state !== "idle" && (
                <p
                  className={`profile-hint profile-hint--${
                    usernameCheck.state === "ok" ? "ok" : "warn"
                  }`}
                >
                  {usernameCheck.state === "checking"
                    ? "Checking availability…"
                    : usernameCheck.message}
                </p>
              )}
              {!profile.can_edit_username && (
                <p className="profile-hint profile-hint--muted">
                  {profile.auth_method && profile.auth_method !== "local"
                    ? `Managed by ${profile.auth_method}.`
                    : "Username changes are not available for this account."}
                </p>
              )}
            </div>
          </section>

          <section className="panel profile-card" aria-labelledby="profile-security">
            <h2 id="profile-security" className="profile-card__title">
              Security
            </h2>
            <p className="profile-card__lede">
              Confirm your current password whenever you change account details.
            </p>
            <div className="field">
              <label htmlFor="profile-current-password">Current password</label>
              <input
                id="profile-current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                disabled={busy || managedExternally}
              />
            </div>
            {profile.can_edit_password ? (
              <>
                <div className="field">
                  <label htmlFor="profile-new-password">New password</label>
                  <input
                    id="profile-new-password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    autoComplete="new-password"
                    disabled={busy}
                    aria-describedby="profile-password-requirements"
                    aria-invalid={showPasswordRules && !passwordValid}
                  />
                </div>
                <div className="field">
                  <label htmlFor="profile-confirm-password">Confirm new password</label>
                  <input
                    id="profile-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                    disabled={busy}
                    aria-describedby="profile-password-requirements"
                    aria-invalid={
                      confirmPassword.length > 0 &&
                      newPassword.length > 0 &&
                      newPassword !== confirmPassword
                    }
                  />
                </div>
                <PasswordRequirements
                  password={newPassword}
                  confirm={confirmPassword}
                />
                {showPasswordRules && !passwordValid && (
                  <p className="profile-hint profile-hint--warn">
                    Fix the password requirements before saving.
                  </p>
                )}
              </>
            ) : (
              <p className="profile-hint profile-hint--muted">
                Password changes are not available for this sign-in method.
              </p>
            )}
          </section>

          <section className="panel profile-card" aria-labelledby="profile-org">
            <h2 id="profile-org" className="profile-card__title">
              Organization
            </h2>
            <div className="profile-meta-grid">
              <div>
                <span className="profile-meta-grid__label">Org ID</span>
                <span className="profile-meta-grid__value">{profile.org_id || me?.org_id || "—"}</span>
              </div>
              <div>
                <span className="profile-meta-grid__label">Role</span>
                <span className="profile-meta-grid__value">{profile.role || me?.role || "—"}</span>
              </div>
            </div>
            {profile.can_edit_org_name ? (
              <div className="field">
                <label htmlFor="profile-org-name">Display name</label>
                <input
                  id="profile-org-name"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  disabled={busy}
                />
                <p className="profile-hint profile-hint--muted">
                  You are the only member of this organization.
                </p>
              </div>
            ) : (
              <p className="profile-hint profile-hint--muted">
                Organization name: {profile.org_name || profile.org_id || "—"}
              </p>
            )}
          </section>

          <section className="panel profile-card" aria-labelledby="profile-details">
            <h2 id="profile-details" className="profile-card__title">
              Session details
            </h2>
            <dl className="profile-details">
              <div>
                <dt>Auth method</dt>
                <dd>{profile.auth_method || "—"}</dd>
              </div>
              <div>
                <dt>Account created</dt>
                <dd>{formatTimestamp(profile.created_at)}</dd>
              </div>
              <div>
                <dt>Last updated</dt>
                <dd>{formatTimestamp(profile.updated_at)}</dd>
              </div>
            </dl>
          </section>

          <div className="profile-actions">
            <button
              type="submit"
              className="btn btn--primary"
              disabled={busy || managedExternally}
            >
              {busy ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
