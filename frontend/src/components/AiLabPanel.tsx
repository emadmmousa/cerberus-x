import { useEffect, useState } from "react";
import {
  contributeDataset,
  deleteMarketplace,
  getDatasetExamples,
  getEditionStatus,
  getAiLabStatus,
  getMarketplace,
  getScaffolds,
  registerMarketplace,
  apiFetch,
} from "../api/client";

type AiLabStatus = {
  model?: string;
  base_model?: string;
  multi_scaffold?: boolean;
  cost_route?: boolean;
  scaffolds?: Array<{ id: string; model: string; enabled?: boolean }>;
  waves?: Record<string, boolean>;
  edition?: { edition?: string };
  sso?: { ready?: boolean; preferred?: string | null };
};

type HealthRow = {
  id: string;
  model?: string;
  ok?: boolean;
  latency_ms?: number;
  latency_ema_ms?: number;
  cost_per_1k?: number;
  error?: string;
};

type MarketplaceState = {
  count?: number;
  can_register?: boolean;
  catalog?: Array<{ id: string; label?: string }>;
  registered?: Array<{ id: string; model?: string; base_url?: string }>;
};

type HostingState = {
  enabled?: boolean;
  control_plane_url?: string | null;
};

type ContribExample = {
  id: string;
  label: string;
  prompt: string;
  response: string;
  posture?: string;
};

type BulkRow = ContribExample & { checked: boolean };

export function AiLabPanel({ disabled = false }: { disabled?: boolean }) {
  const [status, setStatus] = useState<AiLabStatus | null>(null);
  const [health, setHealth] = useState<HealthRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [contribMsg, setContribMsg] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [examples, setExamples] = useState<ContribExample[]>([]);
  const [guidance, setGuidance] = useState<string>("");
  const [examplePosture, setExamplePosture] = useState<string>("");
  const [market, setMarket] = useState<MarketplaceState | null>(null);
  const [hosting, setHosting] = useState<HostingState | null>(null);
  const [hbMsg, setHbMsg] = useState<string | null>(null);
  const [regMsg, setRegMsg] = useState<string | null>(null);
  const [regId, setRegId] = useState("");
  const [regModel, setRegModel] = useState("");
  const [regUrl, setRegUrl] = useState("");
  const [regCost, setRegCost] = useState("0");
  const [bulk, setBulk] = useState<BulkRow[]>([]);
  const [bulkMsg, setBulkMsg] = useState<string | null>(null);

  function reloadScaffolds() {
    return Promise.all([
      getAiLabStatus(),
      getScaffolds(),
      getMarketplace().catch(() => null),
    ]).then(([st, sc, mk]) => {
      setStatus(st as AiLabStatus);
      setHealth((sc.health as HealthRow[]) ?? []);
      if (mk) setMarket(mk as MarketplaceState);
    });
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getAiLabStatus(),
      getScaffolds(),
      getDatasetExamples(examplePosture || undefined, 50).catch(() => null),
      getMarketplace().catch(() => null),
      getEditionStatus().catch(() => null),
    ])
      .then(([st, sc, ex, mk, ed]) => {
        if (cancelled) return;
        setStatus(st as AiLabStatus);
        setHealth((sc.health as HealthRow[]) ?? []);
        if (ex) {
          setExamples((ex.examples as ContribExample[]) ?? []);
          setGuidance(ex.guidance ?? "");
        }
        if (mk) setMarket(mk as MarketplaceState);
        const hostingBlock = (ed as { managed_hosting?: HostingState } | null)
          ?.managed_hosting;
        if (hostingBlock) setHosting(hostingBlock);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [examplePosture]);

  async function pingControlPlane() {
    setHbMsg(null);
    try {
      const res = await apiFetch("/api/edition/heartbeat", { method: "POST" });
      const data = (await res.json()) as {
        skipped?: boolean;
        reason?: string;
        ok?: boolean;
        status?: number;
        error?: string;
      };
      if (data.skipped) {
        setHbMsg(data.reason || "heartbeat skipped");
        return;
      }
      setHbMsg(
        data.ok
          ? `Control plane OK (${data.status ?? 200})`
          : `Control plane error: ${data.error || data.status || "failed"}`,
      );
    } catch (err: unknown) {
      setHbMsg(err instanceof Error ? err.message : String(err));
    }
  }

  async function unregisterScaffold(id: string) {
    setRegMsg(null);
    try {
      await deleteMarketplace(id);
      setRegMsg(`Removed ${id}`);
      await reloadScaffolds();
    } catch (err: unknown) {
      setRegMsg(err instanceof Error ? err.message : String(err));
    }
  }

  async function registerScaffold() {
    setRegMsg(null);
    try {
      const data = await registerMarketplace({
        id: regId.trim(),
        model: regModel.trim(),
        base_url: regUrl.trim(),
        cost_per_1k: Number(regCost) || 0,
        label: regId.trim(),
      });
      setRegMsg(
        `Registered ${(data.scaffold as { id?: string } | undefined)?.id ?? regId}`,
      );
      setRegId("");
      setRegModel("");
      setRegUrl("");
      setRegCost("0");
      await reloadScaffolds();
    } catch (err: unknown) {
      setRegMsg(err instanceof Error ? err.message : String(err));
    }
  }

  function loadExample(id: string) {
    const row = examples.find((e) => e.id === id);
    if (!row) return;
    setPrompt(row.prompt);
    setResponse(row.response);
    setContribMsg(`Loaded example: ${row.label}`);
  }

  function loadAllExamples() {
    const rows = examples.map((e) => ({ ...e, checked: true }));
    setBulk(rows);
    setBulkMsg(`Bulk: ${rows.length}/${rows.length} ready`);
  }

  async function submitAll() {
    const rows = bulk.filter(
      (b) => b.checked && b.prompt.trim() && b.response.trim(),
    );
    let saved = 0;
    const errors: string[] = [];
    for (const row of rows) {
      try {
        await contributeDataset({
          prompt: row.prompt,
          response: row.response,
          posture: examplePosture || row.posture || "balanced",
          license: "CC-BY-4.0",
          contributor: "mission-control",
        });
        saved += 1;
        setBulkMsg(`Saved ${saved}/${rows.length}`);
      } catch (err: unknown) {
        errors.push(
          `${row.id}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
    setBulkMsg(
      errors.length
        ? `Saved ${saved}/${rows.length}; errors: ${errors.join("; ")}`
        : `Saved ${saved}/${rows.length}`,
    );
  }

  async function submitContribution() {
    setContribMsg(null);
    try {
      const data = await contributeDataset({
        prompt,
        response,
        posture: examplePosture || "balanced",
        license: "CC-BY-4.0",
        contributor: "mission-control",
      });
      setContribMsg(
        data.persisted
          ? `Saved under CC-BY · id ${(data.record as { id?: string } | undefined)?.id}`
          : "Accepted (not persisted to disk)",
      );
      setPrompt("");
      setResponse("");
    } catch (err: unknown) {
      setContribMsg(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="panel arsenal" aria-label="AI Lab">
      <div className="arsenal__head">
        <div>
          <div className="arsenal__title">AI Lab model</div>
          <p className="arsenal__note">
            {status?.model ?? "…"} ← {status?.base_model ?? "…"}
            {status?.multi_scaffold ? " · multi-scaffold on" : " · single scaffold"}
            {status?.cost_route ? " · cost-route on" : ""}
            {status?.edition?.edition ? ` · ${status.edition.edition}` : ""}
            {status?.sso?.ready
              ? ` · SSO (${status.sso.preferred ?? "on"})`
              : " · SSO off"}
          </p>
        </div>
        <button
          type="button"
          className="btn"
          style={{ fontSize: "0.75rem", padding: "0.15rem 0.45rem" }}
          onClick={() => void reloadScaffolds().catch(() => null)}
        >
          Refresh
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <ul className="arsenal__list">
        {health.map((h) => (
          <li key={h.id} title={h.error || h.model}>
            <span className="arsenal__name">{h.id}</span>
            <span
              className={`arsenal__mark arsenal__mark--${h.ok ? "ready" : "missing"}`}
            >
              {h.ok
                ? `ok ${h.latency_ema_ms ?? h.latency_ms ?? "?"}ms · $${Number(h.cost_per_1k ?? 0).toFixed(3)}/1k`
                : "down"}
            </span>
          </li>
        ))}
        {!health.length && !error && (
          <li>
            <span className="arsenal__note">No scaffolds registered yet</span>
          </li>
        )}
      </ul>
      {status?.waves && (
        <p className="arsenal__summary">
          Waves:{" "}
          {Object.entries(status.waves)
            .filter(([, v]) => v)
            .map(([k]) => k.replace(/^w/, "W"))
            .join(" · ")}
        </p>
      )}
      {market && (
        <p className="arsenal__note">
          Marketplace: {market.count ?? 0} recipes
          {market.can_register ? " · register enabled (Pro)" : " · catalog (community)"}
        </p>
      )}
      {market?.registered && market.registered.length > 0 && (
        <ul className="arsenal__list" aria-label="Registered scaffolds">
          {market.registered.map((r) => (
            <li key={r.id}>
              <span className="arsenal__name">{r.id}</span>
              {market.can_register && !disabled && (
                <button
                  type="button"
                  className="btn"
                  style={{ fontSize: "0.7rem", padding: "0.1rem 0.35rem" }}
                  onClick={() => void unregisterScaffold(r.id)}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {market?.can_register && !disabled && (
        <div className="arsenal__note" style={{ marginTop: "0.35rem" }}>
          <div className="arsenal__title" style={{ fontSize: "0.85rem" }}>
            Register scaffold (Pro)
          </div>
          <div className="field" style={{ marginTop: "0.25rem" }}>
            <label htmlFor="reg-id">id</label>
            <input
              id="reg-id"
              value={regId}
              onChange={(e) => setRegId(e.target.value)}
              placeholder="my-vllm"
            />
            <label htmlFor="reg-model">model</label>
            <input
              id="reg-model"
              value={regModel}
              onChange={(e) => setRegModel(e.target.value)}
              placeholder="qwen2.5:14b"
            />
            <label htmlFor="reg-url">base_url</label>
            <input
              id="reg-url"
              value={regUrl}
              onChange={(e) => setRegUrl(e.target.value)}
              placeholder="http://vllm:8000/v1"
            />
            <label htmlFor="reg-cost">cost_per_1k</label>
            <input
              id="reg-cost"
              value={regCost}
              onChange={(e) => setRegCost(e.target.value)}
              placeholder="0"
            />
          </div>
          <button
            type="button"
            className="btn"
            style={{ marginTop: "0.35rem" }}
            disabled={!regId.trim() || !regModel.trim() || !regUrl.trim()}
            onClick={() => void registerScaffold()}
          >
            Register
          </button>
          {regMsg && <p className="arsenal__note">{regMsg}</p>}
        </div>
      )}
      {hosting && (
        <div className="arsenal__note" style={{ marginTop: "0.35rem" }}>
          Managed hosting:{" "}
          {hosting.enabled
            ? hosting.control_plane_url || "enabled (no control plane URL)"
            : "off"}
          {hosting.enabled && (
            <button
              type="button"
              className="btn"
              style={{ marginLeft: "0.5rem" }}
              onClick={() => void pingControlPlane()}
            >
              Ping control plane
            </button>
          )}
          {hbMsg && <span> · {hbMsg}</span>}
        </div>
      )}
      {!disabled && (
        <div className="arsenal__note" style={{ marginTop: "0.75rem" }}>
          <div className="arsenal__title" style={{ fontSize: "0.85rem" }}>
            Dataset contribute
          </div>
          <p className="arsenal__note">
            {guidance ||
              "Authorized prompt → ideal response pairs for fine-tuning (CC-BY)."}
          </p>
          <div className="field" style={{ marginTop: "0.35rem" }}>
            <label htmlFor="contrib-posture">Example posture</label>
            <select
              id="contrib-posture"
              value={examplePosture}
              onChange={(e) => setExamplePosture(e.target.value)}
            >
              <option value="">All postures</option>
              <option value="aggressive">Aggressive (top 50)</option>
              <option value="defensive">Defensive (top 50)</option>
              <option value="balanced">Balanced (top 50)</option>
            </select>
            {examples.length > 0 && (
              <>
                <label htmlFor="contrib-example">
                  Load example ({examples.length} ready-made)
                </label>
                <select
                  id="contrib-example"
                  defaultValue=""
                  size={Math.min(12, Math.max(6, Math.min(examples.length, 12)))}
                  onChange={(e) => {
                    if (e.target.value) loadExample(e.target.value);
                    e.target.value = "";
                  }}
                  style={{ minHeight: "10rem" }}
                >
                  <option value="">Choose an example…</option>
                  {examples.map((ex) => (
                    <option key={ex.id} value={ex.id}>
                      {ex.label}
                    </option>
                  ))}
                </select>
                <div style={{ marginTop: "0.35rem", display: "flex", gap: "0.35rem" }}>
                  <button
                    type="button"
                    className="btn"
                    disabled={examples.length === 0}
                    onClick={loadAllExamples}
                  >
                    Load all (posture)
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={bulk.filter((b) => b.checked).length === 0}
                    onClick={() => void submitAll()}
                  >
                    Submit all (CC-BY)
                  </button>
                </div>
                {bulk.length > 0 && (
                  <ul
                    className="arsenal__list"
                    aria-label="Bulk examples"
                    style={{ marginTop: "0.35rem" }}
                  >
                    {bulk.map((row) => (
                      <li key={row.id}>
                        <label style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={(e) =>
                              setBulk((prev) =>
                                prev.map((b) =>
                                  b.id === row.id
                                    ? { ...b, checked: e.target.checked }
                                    : b,
                                ),
                              )
                            }
                          />
                          <span className="arsenal__name">{row.label}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
                {bulkMsg && <p className="arsenal__note">{bulkMsg}</p>}
              </>
            )}
          </div>
          <textarea
            aria-label="contribute prompt"
            placeholder="e.g. Authorized recon on https://lab.example. Suggest next phase JSON."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            style={{ width: "100%", marginTop: "0.35rem" }}
          />
          <textarea
            aria-label="contribute response"
            placeholder='e.g. {"phase_name":"ai_recon","tools":[{"tool":"nmap"}],"stop":false}'
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            rows={3}
            style={{ width: "100%", marginTop: "0.35rem" }}
          />
          <button
            type="button"
            className="btn"
            style={{ marginTop: "0.35rem" }}
            disabled={!prompt.trim() || !response.trim()}
            onClick={() => void submitContribution()}
          >
            Submit (CC-BY)
          </button>
          {contribMsg && <p className="arsenal__note">{contribMsg}</p>}
        </div>
      )}
    </div>
  );
}
