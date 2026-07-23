import { useEffect, useState } from "react";
import {
  deleteMarketplace,
  getEditionStatus,
  getAiLabStatus,
  getMarketplace,
  getScaffolds,
  registerMarketplace,
  type PackagingStatus,
} from "../api/client";
import type { AiLabSectionId } from "../lib/aiLabSections";
import { aiLabSectionById } from "../lib/aiLabSections";
import { ManagedHostingPanel } from "./ManagedHostingPanel";
import { ScaffoldHealthPanel } from "./ScaffoldHealthPanel";
import { ScaffoldMarketplacePanel } from "./ScaffoldMarketplacePanel";
import { TrainingCorpusPanel } from "./TrainingCorpusPanel";

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
  catalog?: Array<{
    id: string;
    label?: string;
    category?: string;
    tasks?: string[];
    notes?: string;
    model?: string;
  }>;
  categories?: Array<{ id: string; label?: string; count?: number }>;
  registered?: Array<{ id: string; model?: string; base_url?: string }>;
};

type Props = {
  section: AiLabSectionId;
  disabled?: boolean;
};

function SectionHead({ section }: { section: AiLabSectionId }) {
  const meta = aiLabSectionById(section);
  return (
    <div className="admin-section-head">
      <div>
        <h2 className="admin-section-head__title">{meta.label}</h2>
        <p className="admin-section-head__lede">{meta.description}</p>
      </div>
    </div>
  );
}

export function AiLabPanel({ section, disabled = false }: Props) {
  const [status, setStatus] = useState<AiLabStatus | null>(null);
  const [health, setHealth] = useState<HealthRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState<MarketplaceState | null>(null);
  const [packaging, setPackaging] = useState<PackagingStatus | null>(null);
  const [regMsg, setRegMsg] = useState<string | null>(null);
  const [regId, setRegId] = useState("");
  const [regModel, setRegModel] = useState("");
  const [regUrl, setRegUrl] = useState("");
  const [regCost, setRegCost] = useState("0");

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
      getMarketplace().catch(() => null),
      getEditionStatus().catch(() => null),
    ])
      .then(([st, sc, mk, ed]) => {
        if (cancelled) return;
        setStatus(st as AiLabStatus);
        setHealth((sc as { health?: HealthRow[] }).health ?? []);
        if (mk) setMarket(mk as MarketplaceState);
        if (ed) setPackaging(ed as PackagingStatus);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [section]);

  async function refreshPackaging() {
    try {
      const data = await getEditionStatus();
      setPackaging(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
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

  return (
    <div className="panel admin-panel arsenal" aria-label={aiLabSectionById(section).label}>
      <SectionHead section={section} />
      {error && <p className="error-text">{error}</p>}

      {section === "scaffolds" && (
        <ScaffoldHealthPanel
          status={status}
          health={health}
          error={error}
          onRefresh={() => void reloadScaffolds().catch(() => null)}
        />
      )}

      {section === "marketplace" && (
        <ScaffoldMarketplacePanel
          market={market}
          disabled={disabled}
          registerForm={{
            id: regId,
            model: regModel,
            url: regUrl,
            cost: regCost,
            message: regMsg,
          }}
          onRegisterField={(field, value) => {
            if (field === "id") setRegId(value);
            if (field === "model") setRegModel(value);
            if (field === "url") setRegUrl(value);
            if (field === "cost") setRegCost(value);
          }}
          onRegister={() => void registerScaffold()}
          onUnregister={(id) => void unregisterScaffold(id)}
          onRefresh={() => void reloadScaffolds().catch(() => null)}
        />
      )}

      {section === "hosting" && (
        <ManagedHostingPanel
          packaging={packaging}
          loading={!packaging}
          onRefresh={() => void refreshPackaging()}
        />
      )}

      {section === "dataset" && <TrainingCorpusPanel disabled={disabled} />}
    </div>
  );
}
