import { useEffect, useState } from "react";
import {
  getProxySettings,
  getProxyStatus,
  putProxySettings,
  testProxySettings,
  type ProxySettings,
} from "../api/client";

const OXYLABS_PRESETS = [
  {
    id: "residential",
    label: "Oxylabs residential",
    host: "pr.oxylabs.io",
    port: "7777",
    hint: "Username must be customer-… (proxy user, not dashboard email)",
  },
  {
    id: "datacenter",
    label: "Oxylabs datacenter",
    host: "dc.oxylabs.io",
    port: "8000",
    hint: "Username must be user-… (proxy user from Oxylabs dashboard)",
  },
  {
    id: "isp",
    label: "Oxylabs ISP",
    host: "isp.oxylabs.io",
    port: "8000",
    hint: "Username must be user-… (proxy user from Oxylabs dashboard)",
  },
  {
    id: "iproyal",
    label: "IPRoyal residential",
    host: "geo.iproyal.com",
    port: "12321",
    hint: "Use IPRoyal proxy username/password from the dashboard (not your login email)",
  },
] as const;

type Props = {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  protocol: "http" | "https" | "socks5h";
  onProtocolChange: (protocol: "http" | "https" | "socks5h") => void;
  disabled?: boolean;
};

const PASSWORD_MASK = "••••••••";

function parseProxyUrl(raw: string): {
  username: string;
  password: string;
  host: string;
  port: number;
  protocol: "http" | "https" | "socks5h";
} {
  const url = new URL(raw.trim());
  const protocol = url.protocol.replace(":", "") as "http" | "https" | "socks5h";
  if (!["http", "https", "socks5h"].includes(protocol)) {
    throw new Error(`unsupported protocol: ${protocol}`);
  }
  if (!url.username) throw new Error("proxy URL missing username");
  if (!url.password) throw new Error("proxy URL missing password");
  if (!url.hostname) throw new Error("proxy URL missing host");
  return {
    username: decodeURIComponent(url.username),
    password: decodeURIComponent(url.password),
    host: url.hostname,
    port: url.port ? Number(url.port) : 7777,
    protocol,
  };
}

export function ProxyToggle({
  enabled,
  onChange,
  protocol,
  onProtocolChange,
  disabled = false,
}: Props) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [open, setOpen] = useState(false);
  const [proxyUrl, setProxyUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [passwordSet, setPasswordSet] = useState(false);
  const [host, setHost] = useState("pr.oxylabs.io");
  const [port, setPort] = useState("7777");
  const [credProtocol, setCredProtocol] = useState<"http" | "https" | "socks5h">(
    "http",
  );
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [saveResult, setSaveResult] = useState<ProxySettings | null>(null);

  const refreshConfigured = () => {
    getProxyStatus()
      .then((data) => setConfigured(data.configured))
      .catch(() => setConfigured(false));
  };

  useEffect(() => {
    refreshConfigured();
    getProxySettings()
      .then((data) => {
        setUsername(data.username || "");
        setHost(data.host || "pr.oxylabs.io");
        setPort(String(data.port ?? 7777));
        if (
          data.protocol === "http" ||
          data.protocol === "https" ||
          data.protocol === "socks5h"
        ) {
          setCredProtocol(data.protocol);
        }
        setPasswordSet(Boolean(data.password_set));
        setPassword(data.password_set ? PASSWORD_MASK : "");
        setPasswordTouched(false);
      })
      .catch(() => {
        /* ignore — form stays empty */
      });
  }, []);

  const onParseUrl = () => {
    setMessage(null);
    try {
      const parsed = parseProxyUrl(proxyUrl);
      setUsername(parsed.username);
      setPassword(parsed.password);
      setPasswordTouched(true);
      setHost(parsed.host);
      setPort(String(parsed.port));
      setCredProtocol(parsed.protocol);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Invalid proxy URL");
    }
  };

  const applyPreset = (id: (typeof OXYLABS_PRESETS)[number]["id"]) => {
    const preset = OXYLABS_PRESETS.find((p) => p.id === id);
    if (!preset) return;
    setHost(preset.host);
    setPort(preset.port);
    setCredProtocol("http");
    setMessage(preset.hint);
  };

  const onTest = async () => {
    setTesting(true);
    setMessage(null);
    try {
      const result = await testProxySettings();
      if (result.ok) {
        setMessage(
          `Upstream OK${result.username ? ` as ${result.username}` : ""} @ ${result.host}:${result.port}`,
        );
      } else {
        setMessage(result.note || "Upstream probe failed");
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Probe failed");
    } finally {
      setTesting(false);
    }
  };

  const onSave = async () => {
    setSaving(true);
    setMessage(null);
    setSaveResult(null);
    try {
      const body: {
        username: string;
        password?: string;
        host: string;
        port: number;
        protocol: "http" | "https" | "socks5h";
      } = {
        username: username.trim(),
        host: host.trim(),
        port: Number(port),
        protocol: credProtocol,
      };
      if (passwordTouched && password && password !== PASSWORD_MASK) {
        body.password = password;
      } else if (!passwordSet) {
        body.password = password;
      } else {
        body.password = "";
      }
      const result = await putProxySettings(body);
      setSaveResult(result);
      setConfigured(Boolean(result.configured));
      setPasswordSet(true);
      setPassword(PASSWORD_MASK);
      setPasswordTouched(false);
      setProxyUrl("");
      const parts = [
        result.redis?.ok ? "runtime: saved" : "runtime: failed",
        result.env?.ok ? ".env: updated" : `.env: ${result.env?.error ?? "unavailable"}`,
        result.k8s?.ok
          ? "k8s: updated"
          : `k8s: ${result.k8s?.error ?? "unavailable"}`,
      ];
      setMessage(parts.join(" · "));
      getProxyStatus()
        .then((data) => {
          if (data.configured) setConfigured(true);
        })
        .catch(() => undefined);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="options-block">
      <label className="toggle-row options-block__toggle">
        <span className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            aria-label="Proxy"
          />
          <span className="toggle__track">
            <span className="toggle__thumb" />
          </span>
        </span>
        <span>
          <strong>Proxy</strong>
          <span className="options-block__hint"> Route through worker</span>
        </span>
        {configured === true && (
          <span className="badge badge--ok">Ready</span>
        )}
        {configured === false && (
          <span className="badge badge--warn">Not set</span>
        )}
      </label>
      {enabled && (
        <div className="field options-block__body" style={{ maxWidth: 240 }}>
          <label htmlFor="proxy-protocol">Protocol</label>
          <select
            id="proxy-protocol"
            value={protocol}
            onChange={(e) =>
              onProtocolChange(e.target.value as "http" | "https" | "socks5h")
            }
            disabled={disabled}
          >
            <option value="http">http</option>
            <option value="https">https</option>
            <option value="socks5h">socks5h</option>
          </select>
        </div>
      )}

      <div className="proxy-settings">
        <button
          type="button"
          className="btn"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? "Hide proxy settings" : "Proxy settings"}
        </button>

        {open && (
          <div className="proxy-settings__body">
            <p className="proxy-settings__msg muted">
              Save upstream proxy credentials (Oxylabs, IPRoyal, etc.). Workers
              route tools through a local forwarder on{" "}
              <code>127.0.0.1:18080</code> — secrets never appear in tool argv
              or the browser.
            </p>
            <div className="row" style={{ marginBottom: "0.75rem" }}>
              {OXYLABS_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className="btn"
                  onClick={() => applyPreset(preset.id)}
                  disabled={disabled || saving}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="field">
              <label htmlFor="proxy-url">Full proxy URL</label>
              <div className="row" style={{ marginBottom: 0 }}>
                <input
                  id="proxy-url"
                  type="text"
                  value={proxyUrl}
                  onChange={(e) => setProxyUrl(e.target.value)}
                  placeholder="http://user:pass@pr.oxylabs.io:7777"
                  disabled={disabled || saving}
                  autoComplete="off"
                />
                <button
                  type="button"
                  className="btn"
                  onClick={onParseUrl}
                  disabled={disabled || saving || !proxyUrl.trim()}
                >
                  Parse URL
                </button>
              </div>
            </div>

            <div className="row">
              <div className="field" style={{ maxWidth: 140 }}>
                <label htmlFor="cred-protocol">Protocol</label>
                <select
                  id="cred-protocol"
                  value={credProtocol}
                  onChange={(e) =>
                    setCredProtocol(
                      e.target.value as "http" | "https" | "socks5h",
                    )
                  }
                  disabled={disabled || saving}
                >
                  <option value="http">http</option>
                  <option value="https">https</option>
                  <option value="socks5h">socks5h</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="proxy-host">Host</label>
                <input
                  id="proxy-host"
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  disabled={disabled || saving}
                  autoComplete="off"
                />
              </div>
              <div className="field" style={{ maxWidth: 120 }}>
                <label htmlFor="proxy-port">Port</label>
                <input
                  id="proxy-port"
                  type="text"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  disabled={disabled || saving}
                  autoComplete="off"
                />
              </div>
            </div>

            <div className="row">
              <div className="field">
                <label htmlFor="proxy-username">Username</label>
                <input
                  id="proxy-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={disabled || saving}
                  autoComplete="off"
                />
              </div>
              <div className="field">
                <label htmlFor="proxy-password">Password</label>
                <input
                  id="proxy-password"
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setPasswordTouched(true);
                  }}
                  onFocus={() => {
                    if (!passwordTouched && password === PASSWORD_MASK) {
                      setPassword("");
                      setPasswordTouched(true);
                    }
                  }}
                  disabled={disabled || saving}
                  autoComplete="new-password"
                  placeholder={passwordSet ? "Leave blank to keep" : ""}
                />
              </div>
            </div>

            <div className="row">
              <button
                type="button"
                className="btn btn--primary"
                onClick={onSave}
                disabled={disabled || saving || !username.trim() || !host.trim()}
              >
                {saving ? "Saving…" : "Save credentials"}
              </button>
              <button
                type="button"
                className="btn"
                onClick={onTest}
                disabled={disabled || saving || testing}
              >
                {testing ? "Testing…" : "Test upstream"}
              </button>
            </div>

            {message && (
              <p className="proxy-settings__msg" role="status">
                {message}
              </p>
            )}
            {saveResult?.proxy_url_redacted && (
              <p className="proxy-settings__msg muted">
                Active: {saveResult.proxy_url_redacted}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export { parseProxyUrl };
