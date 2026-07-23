import { useMemo, useState } from "react";
import {
  AGGRESSIVE_PROMPTS,
  LIBRARY_MODES,
  PROMPT_CATEGORIES,
  TARGET_PROFILE_CATEGORIES,
  type AggressivePrompt,
  type LibraryMode,
  type OsintTargetProfile,
  type PromptCategory,
  targetProfileLabel,
} from "../lib/aggressivePrompts";
import { usePagination } from "../hooks/usePagination";
import { ListPagination } from "./ListPagination";

type Props = {
  disabled?: boolean;
  onSelect: (prompt: AggressivePrompt) => void;
};

const CATEGORY_ACCENT: Record<PromptCategory, string> = {
  full: "var(--prompt-full)",
  adaptive: "var(--prompt-adaptive)",
  web: "var(--prompt-web)",
  darkweb: "var(--prompt-darkweb)",
  intel: "var(--prompt-intel)",
  impact: "var(--prompt-impact)",
  creds: "var(--prompt-creds)",
  ad: "var(--prompt-ad)",
};

const TARGET_ACCENT: Record<OsintTargetProfile, string> = {
  username: "var(--target-username)",
  full_name: "var(--target-full-name)",
  email: "var(--target-email)",
  mobile: "var(--target-mobile)",
  social_url: "var(--target-social)",
  domain: "var(--target-domain)",
};

export function AggressivePromptDeck({ disabled, onSelect }: Props) {
  const [libraryMode, setLibraryMode] = useState<LibraryMode>("all");
  const [category, setCategory] = useState<PromptCategory | "all">("all");
  const [targetProfile, setTargetProfile] = useState<OsintTargetProfile | "all">("all");
  const [query, setQuery] = useState("");

  const modePool = useMemo(
    () => AGGRESSIVE_PROMPTS.filter((p) => {
      if (libraryMode === "host") return p.targetProfile === "host";
      if (libraryMode === "osint") return p.targetProfile !== "host";
      return true;
    }),
    [libraryMode],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return modePool.filter((p) => {
      if (libraryMode === "host" && category !== "all" && p.category !== category) {
        return false;
      }
      if (libraryMode === "osint" && targetProfile !== "all" && p.targetProfile !== targetProfile) {
        return false;
      }
      if (!q) return true;
      const blob = `${p.codename} ${p.title} ${p.hook} ${p.tools.join(" ")} ${p.prompt} ${targetProfileLabel(p.targetProfile)}`.toLowerCase();
      return blob.includes(q);
    });
  }, [category, libraryMode, modePool, query, targetProfile]);

  const promptsPage = usePagination(filtered, {
    pageSize: 6,
    pageSizeOptions: [6, 12, 20],
    resetKey: `${libraryMode}|${category}|${targetProfile}|${query}`,
  });

  const hostCount = AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile === "host").length;
  const osintCount = AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile !== "host").length;

  return (
    <div className="strike-library" aria-label="Aggressive prompt library">
      <header className="strike-library__hero">
        <div className="strike-library__hero-text">
          <p className="strike-library__eyebrow">Strike library</p>
          <h2 className="strike-library__title">Authorized aggressive playbooks</h2>
          <p className="strike-library__sub">
            {AGGRESSIVE_PROMPTS.length} operator prompts — pick a playbook, then send your
            authorized target in the next message.
          </p>
        </div>
        <div className="strike-library__badge" aria-hidden="true">
          <span className="strike-library__badge-ring" />
          <span className="strike-library__badge-core">AGGRO</span>
        </div>
      </header>

      <div className="strike-library__mode" role="tablist" aria-label="Strike library view">
        {LIBRARY_MODES.map((mode) => {
          const count =
            mode.id === "all"
              ? AGGRESSIVE_PROMPTS.length
              : mode.id === "host"
                ? hostCount
                : osintCount;
          return (
            <button
              key={mode.id}
              type="button"
              role="tab"
              aria-selected={libraryMode === mode.id}
              className={`strike-library__mode-btn${
                libraryMode === mode.id ? " strike-library__mode-btn--active" : ""
              }`}
              disabled={disabled}
              onClick={() => {
                setLibraryMode(mode.id);
                setCategory("all");
                setTargetProfile("all");
              }}
            >
              <span className="strike-library__mode-label">{mode.label}</span>
              <span className="strike-library__mode-blurb">{mode.blurb}</span>
              <span className="strike-library__tab-count">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="strike-library__toolbar">
        <label className="strike-library__search">
          <span className="sr-only">Filter prompts</span>
          <input
            type="search"
            placeholder="Filter codename, tools, tactic…"
            value={query}
            disabled={disabled}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {libraryMode !== "osint" ? (
          <div className="strike-library__tabs" role="tablist" aria-label="Tactic category">
            <button
              type="button"
              role="tab"
              aria-selected={category === "all"}
              className={`strike-library__tab${category === "all" ? " strike-library__tab--active" : ""}`}
              disabled={disabled}
              onClick={() => setCategory("all")}
            >
              All
              <span className="strike-library__tab-count">{modePool.length}</span>
            </button>
            {PROMPT_CATEGORIES.map((cat) => {
              const count = modePool.filter((p) => p.category === cat.id).length;
              if (count === 0) return null;
              return (
                <button
                  key={cat.id}
                  type="button"
                  role="tab"
                  aria-selected={category === cat.id}
                  className={`strike-library__tab strike-library__tab--${cat.id}${
                    category === cat.id ? " strike-library__tab--active" : ""
                  }`}
                  disabled={disabled}
                  onClick={() => setCategory(cat.id)}
                >
                  {cat.label}
                  <span className="strike-library__tab-count">{count}</span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="strike-library__tabs" role="tablist" aria-label="OSINT target profile">
            <button
              type="button"
              role="tab"
              aria-selected={targetProfile === "all"}
              className={`strike-library__tab${targetProfile === "all" ? " strike-library__tab--active" : ""}`}
              disabled={disabled}
              onClick={() => setTargetProfile("all")}
            >
              All OSINT
              <span className="strike-library__tab-count">{modePool.length}</span>
            </button>
            {TARGET_PROFILE_CATEGORIES.map((cat) => {
              const count = modePool.filter((p) => p.targetProfile === cat.id).length;
              return (
                <button
                  key={cat.id}
                  type="button"
                  role="tab"
                  aria-selected={targetProfile === cat.id}
                  className={`strike-library__tab strike-library__tab--target-${cat.id}${
                    targetProfile === cat.id ? " strike-library__tab--active" : ""
                  }`}
                  disabled={disabled}
                  onClick={() => setTargetProfile(cat.id)}
                >
                  {cat.label}
                  <span className="strike-library__tab-count">{count}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="strike-library__empty">No prompts match that filter.</p>
      ) : (
        <>
          <ul className="strike-library__grid">
            {promptsPage.items.map((prompt) => (
              <PromptCard
                key={prompt.id}
                prompt={prompt}
                disabled={disabled}
                onSelect={() => onSelect(prompt)}
              />
            ))}
          </ul>
          <ListPagination
            page={promptsPage.page}
            totalPages={promptsPage.totalPages}
            total={promptsPage.total}
            rangeStart={promptsPage.rangeStart}
            rangeEnd={promptsPage.rangeEnd}
            pageSize={promptsPage.pageSize}
            pageSizeOptions={promptsPage.pageSizeOptions}
            onPageChange={promptsPage.setPage}
            onPageSizeChange={promptsPage.setPageSize}
            label="Strike library pagination"
          />
        </>
      )}
    </div>
  );
}

function PromptCard({
  prompt,
  disabled,
  onSelect,
}: {
  prompt: AggressivePrompt;
  disabled?: boolean;
  onSelect: () => void;
}) {
  const accent =
    prompt.targetProfile === "host"
      ? CATEGORY_ACCENT[prompt.category]
      : TARGET_ACCENT[prompt.targetProfile];
  const catLabel =
    prompt.targetProfile === "host"
      ? (PROMPT_CATEGORIES.find((c) => c.id === prompt.category)?.label ?? prompt.category)
      : targetProfileLabel(prompt.targetProfile);

  return (
    <li>
      <button
        type="button"
        className={`strike-card strike-card--${prompt.category}`}
        disabled={disabled}
        style={{ "--strike-accent": accent } as React.CSSProperties}
        onClick={onSelect}
      >
        <span className="strike-card__rail" aria-hidden="true" />
        <div className="strike-card__head">
          <span className="strike-card__codename">{prompt.codename}</span>
          <span className="strike-card__cat">{catLabel}</span>
        </div>
        <h3 className="strike-card__title">{prompt.title}</h3>
        <p className="strike-card__hook">{prompt.hook}</p>
        <div className="strike-card__tools" aria-label="Tools">
          {prompt.tools.slice(0, 5).map((tool) => (
            <span key={tool} className="strike-card__tool">
              {tool}
            </span>
          ))}
          {prompt.tools.length > 5 && (
            <span className="strike-card__tool strike-card__tool--more">
              +{prompt.tools.length - 5}
            </span>
          )}
        </div>
        <span className="strike-card__cta">Deploy prompt →</span>
      </button>
    </li>
  );
}
