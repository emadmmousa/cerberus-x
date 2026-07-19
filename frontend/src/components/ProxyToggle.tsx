import { useEffect, useState } from "react";
import { getProxyStatus } from "../api/client";

type Props = {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  protocol: "http" | "https" | "socks5h";
  onProtocolChange: (protocol: "http" | "https" | "socks5h") => void;
  disabled?: boolean;
};

export function ProxyToggle({
  enabled,
  onChange,
  protocol,
  onProtocolChange,
  disabled = false,
}: Props) {
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    getProxyStatus()
      .then((data) => setConfigured(data.configured))
      .catch(() => setConfigured(false));
  }, []);

  return (
    <div className="panel">
      <div className="panel__title">Proxy Routing</div>
      <div className="toggle-row">
        <label className="toggle" aria-label="Enable proxy routing">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
          />
          <span className="toggle__track">
            <span className="toggle__thumb" />
          </span>
        </label>
        <span>Route via worker proxy</span>
        {configured === true && (
          <span className="badge badge--ok">Worker configured</span>
        )}
        {configured === false && (
          <span className="badge badge--warn">Not configured</span>
        )}
      </div>
      {enabled && (
        <div className="field" style={{ marginTop: "0.75rem", maxWidth: 240 }}>
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
    </div>
  );
}
