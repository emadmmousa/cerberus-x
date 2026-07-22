import { useCallback, useEffect, useState } from "react";
import {
  associateUserOrg,
  addAuthorizedTarget,
  createAdminOrg,
  createAdminUser,
  deleteAdminOrg,
  deleteAdminUser,
  deleteAuthorizedTarget,
  deleteMission,
  getAdminLogs,
  getAdminSettings,
  listAdminOrgs,
  listAdminUsers,
  listAuthorizedTargets,
  listMissions,
  restartMission,
  setAuthMethod,
  setEdition,
  setOpsSettings,
  setRbacEnforce,
  stopMission,
  updateAdminUser,
  type AdminOrg,
  type AdminSettings,
  type AdminUser,
  type AuditEvent,
  type AuthorizedTargetRow,
  type MissionSummaryRow,
} from "../api/client";
import { useAuth } from "../providers/AuthProvider";

type TabId =
  | "users"
  | "orgs"
  | "auth"
  | "rbac"
  | "edition"
  | "ops"
  | "targets"
  | "missions"
  | "logs";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "users", label: "Users" },
  { id: "orgs", label: "Organizations" },
  { id: "auth", label: "Auth method" },
  { id: "rbac", label: "RBAC" },
  { id: "edition", label: "Edition" },
  { id: "ops", label: "Ops" },
  { id: "targets", label: "Targets" },
  { id: "missions", label: "Missions" },
  { id: "logs", label: "Logs" },
];

export function Admin() {
  const { refresh } = useAuth();
  const [tab, setTab] = useState<TabId>("users");
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; msg: string } | null>(
    null,
  );

  const flash = useCallback((kind: "ok" | "err", msg: string) => {
    setBanner({ kind, msg });
    window.setTimeout(() => setBanner(null), 4000);
  }, []);

  return (
    <div className="mission">
      <section className="panel" aria-label="Admin console">
        <div className="section-label">Admin console</div>
        <p className="section-sub">
          Manage users, organizations, authentication, RBAC, edition, ops,
          missions, and audit logs.
        </p>
        <div className="admin-tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`admin-tab${tab === t.id ? " admin-tab--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {banner && (
          <p className={banner.kind === "ok" ? "ok-text" : "error-text"}>
            {banner.msg}
          </p>
        )}
      </section>

      {tab === "users" && <UsersTab flash={flash} />}
      {tab === "orgs" && <OrgsTab flash={flash} />}
      {tab === "auth" && <AuthTab flash={flash} />}
      {tab === "rbac" && <RbacTab flash={flash} onChange={refresh} />}
      {tab === "edition" && <EditionTab flash={flash} onChange={refresh} />}
      {tab === "ops" && <OpsTab flash={flash} />}
      {tab === "targets" && <TargetsTab flash={flash} />}
      {tab === "missions" && <MissionsTab flash={flash} />}
      {tab === "logs" && <LogsTab flash={flash} />}
    </div>
  );
}

type FlashFn = (kind: "ok" | "err", msg: string) => void;

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// --------------------------------------------------------------------------
// Users
// --------------------------------------------------------------------------
function UsersTab({ flash }: { flash: FlashFn }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [form, setForm] = useState({
    username: "",
    password: "",
    role: "viewer",
    org_id: "default",
    auth_method: "local",
  });

  const load = useCallback(async () => {
    try {
      const [u, o] = await Promise.all([listAdminUsers(), listAdminOrgs()]);
      setUsers(u);
      setOrgs(o);
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    try {
      await createAdminUser(form);
      flash("ok", `Created user ${form.username}`);
      setForm({ ...form, username: "", password: "" });
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function patch(username: string, body: Partial<AdminUser> & { password?: string }) {
    try {
      await updateAdminUser(username, body);
      flash("ok", `Updated ${username}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function remove(username: string) {
    if (!window.confirm(`Delete user "${username}"?`)) return;
    try {
      await deleteAdminUser(username);
      flash("ok", `Deleted ${username}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  return (
    <>
      <section className="panel" aria-label="Add user">
        <div className="section-label">Add user</div>
        <div className="admin-form">
          <div className="field">
            <label>Username</label>
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="jsmith"
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="(optional for SSO users)"
            />
          </div>
          <div className="field">
            <label>Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="viewer">viewer</option>
              <option value="operator">operator</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div className="field">
            <label>Organization</label>
            <select
              value={form.org_id}
              onChange={(e) => setForm({ ...form, org_id: e.target.value })}
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.id})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Auth method</label>
            <select
              value={form.auth_method}
              onChange={(e) => setForm({ ...form, auth_method: e.target.value })}
            >
              <option value="local">local</option>
              <option value="auth0">auth0</option>
              <option value="google">google</option>
              <option value="github">github</option>
            </select>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!form.username.trim()}
            onClick={() => void create()}
          >
            Add user
          </button>
        </div>
      </section>

      <section className="panel" aria-label="Users">
        <div className="section-label">Users ({users.length})</div>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Org</th>
                <th>Auth</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td className="mono">{u.username}</td>
                  <td>
                    <select
                      value={u.role}
                      onChange={(e) => void patch(u.username, { role: e.target.value })}
                    >
                      <option value="viewer">viewer</option>
                      <option value="operator">operator</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <select
                      value={u.org_id}
                      onChange={(e) =>
                        void patch(u.username, { org_id: e.target.value })
                      }
                    >
                      {orgs.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="mono">{u.auth_method}</td>
                  <td>
                    <span
                      className={`badge ${u.disabled ? "badge--warn" : "badge--ok"}`}
                    >
                      {u.disabled ? "disabled" : "active"}
                    </span>
                  </td>
                  <td className="admin-actions">
                    <button
                      type="button"
                      className="btn"
                      onClick={() =>
                        void patch(u.username, { disabled: !u.disabled })
                      }
                    >
                      {u.disabled ? "Enable" : "Disable"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        const pw = window.prompt(`New password for ${u.username}`);
                        if (pw) void patch(u.username, { password: pw });
                      }}
                    >
                      Set password
                    </button>
                    <button
                      type="button"
                      className="btn btn--danger"
                      onClick={() => void remove(u.username)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

// --------------------------------------------------------------------------
// Organizations
// --------------------------------------------------------------------------
function OrgsTab({ flash }: { flash: FlashFn }) {
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [form, setForm] = useState({ id: "", name: "" });
  const [assoc, setAssoc] = useState({ username: "", org_id: "" });

  const load = useCallback(async () => {
    try {
      const [o, u] = await Promise.all([listAdminOrgs(), listAdminUsers()]);
      setOrgs(o);
      setUsers(u);
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    try {
      await createAdminOrg(form);
      flash("ok", `Created org ${form.id}`);
      setForm({ id: "", name: "" });
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function rename(id: string, current: string) {
    const name = window.prompt(`Rename org "${id}"`, current);
    if (!name) return;
    try {
      await updateAdminOrgName(id, name);
      flash("ok", `Renamed ${id}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function remove(id: string) {
    if (!window.confirm(`Delete org "${id}"?`)) return;
    try {
      await deleteAdminOrg(id);
      flash("ok", `Deleted ${id}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function associate() {
    try {
      await associateUserOrg(assoc.org_id, assoc.username);
      flash("ok", `Associated ${assoc.username} → ${assoc.org_id}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  return (
    <>
      <section className="panel" aria-label="Create organization">
        <div className="section-label">Create organization</div>
        <div className="admin-form">
          <div className="field">
            <label>ID</label>
            <input
              value={form.id}
              onChange={(e) => setForm({ ...form, id: e.target.value })}
              placeholder="acme"
            />
          </div>
          <div className="field">
            <label>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Acme Corp"
            />
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!form.id.trim()}
            onClick={() => void create()}
          >
            Create
          </button>
        </div>
      </section>

      <section className="panel" aria-label="Organizations">
        <div className="section-label">Organizations ({orgs.length})</div>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Users</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.id}>
                  <td className="mono">{o.id}</td>
                  <td>{o.name}</td>
                  <td>{o.user_count ?? 0}</td>
                  <td className="admin-actions">
                    <button
                      type="button"
                      className="btn"
                      onClick={() => void rename(o.id, o.name)}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      className="btn btn--danger"
                      onClick={() => void remove(o.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" aria-label="Associate user">
        <div className="section-label">Associate user to organization</div>
        <div className="admin-form">
          <div className="field">
            <label>User</label>
            <select
              value={assoc.username}
              onChange={(e) => setAssoc({ ...assoc, username: e.target.value })}
            >
              <option value="">Choose user…</option>
              {users.map((u) => (
                <option key={u.username} value={u.username}>
                  {u.username} ({u.org_id})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Organization</label>
            <select
              value={assoc.org_id}
              onChange={(e) => setAssoc({ ...assoc, org_id: e.target.value })}
            >
              <option value="">Choose org…</option>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.id}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!assoc.username || !assoc.org_id}
            onClick={() => void associate()}
          >
            Associate
          </button>
        </div>
      </section>
    </>
  );
}

// updateAdminOrg is imported lazily to keep the associate form simple.
async function updateAdminOrgName(id: string, name: string) {
  const { updateAdminOrg } = await import("../api/client");
  return updateAdminOrg(id, { name });
}

// --------------------------------------------------------------------------
// Auth method
// --------------------------------------------------------------------------
function AuthTab({ flash }: { flash: FlashFn }) {
  const [settings, setSettings] = useState<AdminSettings | null>(null);

  const load = useCallback(async () => {
    try {
      setSettings(await getAdminSettings());
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(method: string, enabled: boolean) {
    try {
      await setAuthMethod(method, enabled);
      flash("ok", `${method} ${enabled ? "enabled" : "disabled"}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  const methods = settings?.settings.auth_methods ?? {};
  const sso = settings?.sso;

  const DESCRIPTIONS: Record<string, string> = {
    local: "Username + password against the local user directory.",
    auth0: "Auth0 OIDC single sign-on (fully integrated).",
    google: "Google OAuth 2.0 — set GOOGLE_CLIENT_ID / SECRET to start.",
    github: "GitHub OAuth — set GITHUB_CLIENT_ID / SECRET to start.",
  };

  return (
    <section className="panel" aria-label="Auth methods">
      <div className="section-label">Authentication methods</div>
      <p className="section-sub">
        Enable sign-in integrations. Auth0 is production-ready; Google and
        GitHub ship as OAuth stubs you finish by adding client credentials.
      </p>
      {sso && (
        <p className="result-card__meta">
          SSO ready: {sso.ready ? "yes" : "no"}
          {sso.preferred ? ` · preferred ${sso.preferred}` : ""}
          {sso.auth0?.configured ? " · auth0 configured" : ""}
        </p>
      )}
      <ul className="info-grid" style={{ listStyle: "none", padding: 0 }}>
        {["local", "auth0", "google", "github"].map((m) => (
          <li key={m} className="info-item">
            <div className="admin-auth-row">
              <div>
                <div className="info-item__label">{m}</div>
                <div className="result-card__meta">{DESCRIPTIONS[m]}</div>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={m === "local" ? methods[m] !== false : Boolean(methods[m])}
                  onChange={(e) => void toggle(m, e.target.checked)}
                />
                <span className="toggle__track">
                  <span className="toggle__thumb" />
                </span>
              </label>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// --------------------------------------------------------------------------
// RBAC
// --------------------------------------------------------------------------
function RbacTab({ flash, onChange }: { flash: FlashFn; onChange: () => void }) {
  const [settings, setSettings] = useState<AdminSettings | null>(null);

  const load = useCallback(async () => {
    try {
      setSettings(await getAdminSettings());
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function apply(value: boolean | null) {
    try {
      await setRbacEnforce(value);
      flash(
        "ok",
        value === null
          ? "RBAC set to defer to environment"
          : `RBAC enforce ${value ? "ON" : "OFF"}`,
      );
      await load();
      onChange();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  const current = settings?.settings.rbac_enforce;
  const effective = settings?.effective.rbac_enforce;

  const OPTIONS: Array<{ id: string; value: boolean | null; label: string; hint: string }> = [
    { id: "on", value: true, label: "Enforce ON", hint: "Require auth + role on every protected route." },
    { id: "off", value: false, label: "Enforce OFF", hint: "Lab mode — all routes open (no auth required)." },
    { id: "env", value: null, label: "Defer to environment", hint: "Use FIREBREAK_RBAC_ENFORCE from deployment." },
  ];

  return (
    <section className="panel" aria-label="RBAC enforce">
      <div className="section-label">RBAC enforcement</div>
      <p className="section-sub">
        Effective now: <strong>{effective ? "ENFORCED" : "OFF (lab)"}</strong>.
        Enabling enforcement requires an admin password or configured SSO to
        avoid lockout.
      </p>
      <div className="admin-radio-group">
        {OPTIONS.map((o) => {
          const selected =
            (o.value === null && current === null) || current === o.value;
          return (
            <button
              key={o.id}
              type="button"
              className={`admin-radio${selected ? " admin-radio--active" : ""}`}
              onClick={() => void apply(o.value)}
            >
              <span className="admin-radio__title">{o.label}</span>
              <span className="admin-radio__hint">{o.hint}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------
// Edition
// --------------------------------------------------------------------------
function EditionTab({ flash, onChange }: { flash: FlashFn; onChange: () => void }) {
  const [settings, setSettings] = useState<AdminSettings | null>(null);

  const load = useCallback(async () => {
    try {
      setSettings(await getAdminSettings());
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function apply(value: string | null) {
    try {
      await setEdition(value);
      flash("ok", value ? `Edition set to ${value}` : "Edition deferring to env");
      await load();
      onChange();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  const editions = settings?.options.editions ?? ["community", "pro"];
  const current = settings?.settings.edition;
  const effective = settings?.effective.edition;

  return (
    <section className="panel" aria-label="Edition">
      <div className="section-label">Edition</div>
      <p className="section-sub">
        Effective now: <strong>{effective}</strong>. Community keeps all scanning
        capabilities; Pro unlocks SSO packaging, marketplace, and hosting hooks.
      </p>
      <div className="admin-radio-group">
        {editions.map((e) => (
          <button
            key={e}
            type="button"
            className={`admin-radio${current === e ? " admin-radio--active" : ""}`}
            onClick={() => void apply(e)}
          >
            <span className="admin-radio__title">{e}</span>
            <span className="admin-radio__hint">
              {e === "pro"
                ? "SSO packaging · marketplace · managed hosting hooks"
                : "Full scanning · multi-scaffold · own model"}
            </span>
          </button>
        ))}
        <button
          type="button"
          className={`admin-radio${current == null ? " admin-radio--active" : ""}`}
          onClick={() => void apply(null)}
        >
          <span className="admin-radio__title">Defer to environment</span>
          <span className="admin-radio__hint">Use FIREBREAK_EDITION.</span>
        </button>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------
// Ops (auto-scale, train, learning tick)
// --------------------------------------------------------------------------
type OpsFlag = "auto_scale" | "auto_train" | "learning_tick";

const OPS_FLAGS: Array<{
  key: OpsFlag;
  label: string;
  env: string;
  hint: string;
}> = [
  {
    key: "auto_scale",
    label: "Auto-Scale",
    env: "FIREBREAK_AUTO_SCALE",
    hint: "Celery scale tick for worker pool sizing.",
  },
  {
    key: "auto_train",
    label: "Auto-Train",
    env: "FIREBREAK_AUTO_TRAIN",
    hint: "Background fine-tune pipeline when dataset grows.",
  },
  {
    key: "learning_tick",
    label: "Learning Tick",
    env: "FIREBREAK_LEARNING_TICK",
    hint: "Periodic learning / memory consolidation jobs.",
  },
];

function OpsTab({ flash }: { flash: FlashFn }) {
  const [settings, setSettings] = useState<AdminSettings | null>(null);

  const load = useCallback(async () => {
    try {
      setSettings(await getAdminSettings());
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function apply(flag: OpsFlag, value: boolean | null) {
    const meta = OPS_FLAGS.find((f) => f.key === flag);
    try {
      await setOpsSettings({ [flag]: value });
      flash(
        "ok",
        value === null
          ? `${meta?.label ?? flag} deferring to environment`
          : `${meta?.label ?? flag} ${value ? "ON" : "OFF"}`,
      );
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  const OPTIONS: Array<{ id: string; value: boolean | null; label: string }> = [
    { id: "on", value: true, label: "ON" },
    { id: "off", value: false, label: "OFF" },
    { id: "env", value: null, label: "Defer" },
  ];

  return (
    <section className="panel" aria-label="Ops flags">
      <div className="section-label">Ops automation</div>
      <p className="section-sub">
        Toggle background jobs. Defer uses deployment environment variables.
      </p>
      {settings?.secret_key_insecure && (
        <p className="error-text">
          secret_key_insecure: SECRET_KEY is still the default{" "}
          <span className="mono">firebreak-secret</span>. Change it before
          enforcing RBAC in production.
        </p>
      )}
      {OPS_FLAGS.map((flag) => {
        const current = settings?.settings[flag.key];
        const effective = settings?.effective[flag.key];
        return (
          <div key={flag.key} className="admin-ops-flag">
            <div className="section-label">{flag.label}</div>
            <p className="section-sub">
              Effective now: <strong>{effective ? "ON" : "OFF"}</strong>.{" "}
              {flag.hint} Env: <span className="mono">{flag.env}</span>.
            </p>
            <div className="admin-radio-group">
              {OPTIONS.map((o) => {
                const selected =
                  (o.value === null && current === null) || current === o.value;
                return (
                  <button
                    key={o.id}
                    type="button"
                    className={`admin-radio${selected ? " admin-radio--active" : ""}`}
                    onClick={() => void apply(flag.key, o.value)}
                  >
                    <span className="admin-radio__title">
                      {flag.label} {o.label}
                    </span>
                    <span className="admin-radio__hint">
                      {o.value === null
                        ? `Use ${flag.env} from deployment.`
                        : o.value
                          ? `Force ${flag.label.toLowerCase()} enabled.`
                          : `Force ${flag.label.toLowerCase()} disabled.`}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </section>
  );
}

// --------------------------------------------------------------------------
// Authorized targets
// --------------------------------------------------------------------------
function TargetsTab({ flash }: { flash: FlashFn }) {
  const [rows, setRows] = useState<AuthorizedTargetRow[]>([]);
  const [form, setForm] = useState({ target: "", notes: "", expiry: "" });

  const load = useCallback(async () => {
    try {
      const res = await listAuthorizedTargets();
      setRows(res.targets ?? []);
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add() {
    const target = form.target.trim();
    if (!target) {
      flash("err", "Target is required");
      return;
    }
    try {
      await addAuthorizedTarget({
        target,
        notes: form.notes.trim() || undefined,
        expiry: form.expiry.trim() || undefined,
      });
      flash("ok", `Added ${target} (www + apex variants included)`);
      setForm({ target: "", notes: "", expiry: "" });
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  async function remove(target: string) {
    if (!window.confirm(`Remove authorized target "${target}"?`)) return;
    try {
      await deleteAuthorizedTarget(target);
      flash("ok", `Removed ${target}`);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  return (
    <>
      <section className="panel" aria-label="Add authorized target">
        <div className="section-label">Add authorized target</div>
        <p className="section-sub">
          Manage engagement scope without editing JSON by hand. Firebreak accepts
          apex and www variants for each host (http/https included).
        </p>
        <div className="admin-form">
          <div className="field">
            <label>Target / URL / app</label>
            <input
              value={form.target}
              onChange={(e) => setForm({ ...form, target: e.target.value })}
              placeholder="wks.agency or https://app.example.com"
            />
          </div>
          <div className="field">
            <label>Notes (optional)</label>
            <input
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Owner authorization ref"
            />
          </div>
          <div className="field">
            <label>Expiry ISO (optional)</label>
            <input
              value={form.expiry}
              onChange={(e) => setForm({ ...form, expiry: e.target.value })}
              placeholder="2099-12-31T23:59:59"
            />
          </div>
          <button type="button" className="btn btn--primary" onClick={() => void add()}>
            Add target
          </button>
        </div>
      </section>

      <section className="panel" aria-label="Authorized targets list">
        <div className="section-label">Authorized targets ({rows.length})</div>
        <table className="admin-table">
          <thead>
            <tr>
              <th>Target</th>
              <th>Notes</th>
              <th>Expiry</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.target}>
                <td className="mono">{row.target}</td>
                <td>{row.notes ?? "—"}</td>
                <td className="mono">{row.expiry ?? "—"}</td>
                <td>{row.authorized === false ? "revoked" : "active"}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => void remove(row.target)}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="empty-state">
                  No authorized targets yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </>
  );
}

// --------------------------------------------------------------------------
// Missions
// --------------------------------------------------------------------------
function MissionsTab({ flash }: { flash: FlashFn }) {
  const [rows, setRows] = useState<MissionSummaryRow[]>([]);

  const load = useCallback(async () => {
    try {
      const data = await listMissions(100);
      setRows(data.missions ?? []);
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<unknown>, label: string) {
    try {
      await fn();
      flash("ok", label);
      await load();
    } catch (err) {
      flash("err", errMsg(err));
    }
  }

  const isLive = (s?: string) =>
    !["SUCCESS", "FAILURE", "STOPPED", "REVOKED"].includes((s ?? "").toUpperCase());

  return (
    <section className="panel" aria-label="Missions admin">
      <div className="page-head">
        <div className="page-head__text">
          <div className="section-label">Missions ({rows.length})</div>
          <p className="section-sub">Restart, stop, or delete org missions.</p>
        </div>
        <button type="button" className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Target</th>
              <th>State</th>
              <th>Posture</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.task_id}>
                <td className="mono">{m.target || m.task_id}</td>
                <td>
                  <span className="mission-card__state">{m.state ?? "—"}</span>
                </td>
                <td>{m.posture ?? "—"}</td>
                <td className="admin-actions">
                  <button
                    type="button"
                    className="btn"
                    disabled={!isLive(m.state)}
                    onClick={() =>
                      void act(() => stopMission(m.task_id), `Stopped ${m.task_id}`)
                    }
                  >
                    Stop
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() =>
                      void act(
                        () => restartMission(m.task_id),
                        `Restarted ${m.task_id}`,
                      )
                    }
                  >
                    Restart
                  </button>
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => {
                      if (window.confirm(`Delete mission ${m.task_id}?`))
                        void act(
                          () => deleteMission(m.task_id),
                          `Deleted ${m.task_id}`,
                        );
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="empty-state">
                  No missions.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------
// Logs
// --------------------------------------------------------------------------
function LogsTab({ flash }: { flash: FlashFn }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await getAdminLogs(200);
      setEvents(data.events ?? []);
    } catch (err) {
      flash("err", errMsg(err));
    }
  }, [flash]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = filter
    ? events.filter(
        (e) =>
          (e.event_type ?? "").toLowerCase().includes(filter.toLowerCase()) ||
          (e.actor ?? "").toLowerCase().includes(filter.toLowerCase()),
      )
    : events;

  return (
    <section className="panel" aria-label="Audit logs">
      <div className="page-head">
        <div className="page-head__text">
          <div className="section-label">Audit logs</div>
          <p className="section-sub">Every action, who performed it, and when.</p>
        </div>
        <button type="button" className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      <div className="field" style={{ marginBottom: "1rem" }}>
        <label>Filter (event type or actor)</label>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="e.g. MISSION_STOP or admin"
        />
      </div>
      <div className="admin-table-wrap">
        <table className="admin-table admin-table--logs">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Actor</th>
              <th>Severity</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e, i) => (
              <tr key={`${e.timestamp}-${i}`}>
                <td className="mono admin-log-time">
                  {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                </td>
                <td className="mono">{e.event_type}</td>
                <td>
                  {e.actor || "system"}
                  {e.actor_role ? ` (${e.actor_role})` : ""}
                </td>
                <td>
                  <span
                    className={`badge ${
                      e.severity === "critical" || e.severity === "high"
                        ? "badge--err"
                        : "badge--ok"
                    }`}
                  >
                    {e.severity ?? "info"}
                  </span>
                </td>
                <td className="admin-log-detail mono">
                  {typeof e.data === "object"
                    ? JSON.stringify(e.data)
                    : String(e.data ?? "")}
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={5} className="empty-state">
                  No log events.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
