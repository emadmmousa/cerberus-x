import { useEffect, useMemo, useState } from "react";
import { contributeDataset, getDatasetExamples } from "../api/client";
import {
  corpusExamplePreview,
  corpusLicenseLabel,
  corpusPostureHint,
  corpusPostureIcon,
  corpusPostureLabel,
  filterCorpusExamples,
  type CorpusExample,
  type CorpusPosture,
} from "../lib/aiLabBranding";
import { usePagination } from "../hooks/usePagination";
import { ListPagination } from "./ListPagination";

type BulkRow = CorpusExample & { checked: boolean };

type Props = {
  disabled?: boolean;
};

const POSTURE_FILTERS: Array<{ id: CorpusPosture; label: string }> = [
  { id: "", label: "All lenses" },
  { id: "aggressive", label: "Offensive Lens" },
  { id: "defensive", label: "Defensive Lens" },
  { id: "balanced", label: "Balanced Lens" },
];

export function TrainingCorpusPanel({ disabled = false }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [examples, setExamples] = useState<CorpusExample[]>([]);
  const [guidance, setGuidance] = useState("");
  const [licenseDefault, setLicenseDefault] = useState("CC-BY-4.0");
  const [posture, setPosture] = useState<CorpusPosture>("");
  const [query, setQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [contribMsg, setContribMsg] = useState<string | null>(null);

  const [bulk, setBulk] = useState<BulkRow[]>([]);
  const [bulkMsg, setBulkMsg] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (disabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDatasetExamples(posture || undefined, 50)
      .then((data) => {
        if (cancelled) return;
        setExamples((data.examples ?? []) as CorpusExample[]);
        setGuidance(data.guidance ?? "");
        setLicenseDefault((data as { license_default?: string }).license_default ?? "CC-BY-4.0");
        setExpandedId(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [disabled, posture, refreshKey]);

  const filteredExamples = useMemo(
    () => filterCorpusExamples(examples, query),
    [examples, query],
  );

  const examplePage = usePagination(filteredExamples, {
    pageSize: 8,
    pageSizeOptions: [8, 16, 32],
  });

  const bulkPage = usePagination(bulk, {
    pageSize: 10,
    pageSizeOptions: [10, 25, 50],
  });

  const bulkSelected = bulk.filter((row) => row.checked).length;
  const postureCounts = useMemo(() => {
    const counts = { aggressive: 0, defensive: 0, balanced: 0 };
    for (const row of examples) {
      const key = (row.posture ?? "").toLowerCase();
      if (key === "aggressive" || key === "defensive" || key === "balanced") {
        counts[key] += 1;
      }
    }
    return counts;
  }, [examples]);

  function loadExample(row: CorpusExample) {
    setPrompt(row.prompt);
    setResponse(row.response);
    setContribMsg(`Loaded into editor · ${row.label}`);
  }

  function loadAllExamples() {
    const rows = examples.map((row) => ({ ...row, checked: true }));
    setBulk(rows);
    setBulkMsg(`Bulk queue · ${rows.length} examples staged`);
  }

  async function submitAll() {
    const rows = bulk.filter(
      (row) => row.checked && row.prompt.trim() && row.response.trim(),
    );
    let saved = 0;
    const errors: string[] = [];
    for (const row of rows) {
      try {
        await contributeDataset({
          prompt: row.prompt,
          response: row.response,
          posture: posture || row.posture || "balanced",
          license: licenseDefault,
          contributor: "mission-control",
        });
        saved += 1;
        setBulkMsg(`Publishing · ${saved}/${rows.length} contributed`);
      } catch (err: unknown) {
        errors.push(`${row.id}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    setBulkMsg(
      errors.length
        ? `Published ${saved}/${rows.length} · ${errors.join("; ")}`
        : `Published ${saved}/${rows.length} to Training Corpus`,
    );
  }

  async function submitContribution() {
    setContribMsg(null);
    try {
      const data = await contributeDataset({
        prompt,
        response,
        posture: posture || "balanced",
        license: licenseDefault,
        contributor: "mission-control",
      });
      setContribMsg(
        data.persisted
          ? `Contributed under ${corpusLicenseLabel(licenseDefault)} · id ${(data.record as { id?: string } | undefined)?.id}`
          : "Accepted · not persisted to disk",
      );
      setPrompt("");
      setResponse("");
    } catch (err: unknown) {
      setContribMsg(err instanceof Error ? err.message : String(err));
    }
  }

  if (disabled) {
    return (
      <div className="corpus-panel" aria-label="Training corpus">
        <p className="corpus-panel__message">
          Operator access is required to contribute to the Training Corpus.
        </p>
      </div>
    );
  }

  return (
    <div className="corpus-panel" aria-label="Training corpus">
      <div className="corpus-panel__head">
        <div>
          <h3 className="corpus-panel__title">Training Corpus</h3>
          <p className="corpus-panel__lede">
            {guidance ||
              "Authorized mission prompt → response pairs for Model Forge fine-tuning."}
          </p>
        </div>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => setRefreshKey((value) => value + 1)}
        >
          Refresh
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}
      {loading && !examples.length && (
        <p className="corpus-panel__message">Loading seed library…</p>
      )}

      <div className="corpus-panel__stats">
        <div className="corpus-panel__stat">
          <span className="corpus-panel__stat-value">{examples.length}</span>
          <span className="corpus-panel__stat-label">Ready examples</span>
        </div>
        <div className="corpus-panel__stat">
          <span className="corpus-panel__stat-value">{corpusPostureLabel(posture)}</span>
          <span className="corpus-panel__stat-label">Active lens</span>
        </div>
        <div className="corpus-panel__stat">
          <span className="corpus-panel__stat-value">{corpusLicenseLabel(licenseDefault)}</span>
          <span className="corpus-panel__stat-label">Contribution license</span>
        </div>
        <div className="corpus-panel__stat">
          <span className="corpus-panel__stat-value">{bulkSelected || "—"}</span>
          <span className="corpus-panel__stat-label">Bulk queue</span>
        </div>
      </div>

      <section className="corpus-panel__section" aria-label="Seed library">
        <div className="corpus-panel__section-head">
          <div>
            <span className="corpus-panel__section-label">Seed library</span>
            <span className="corpus-panel__section-hint">{corpusPostureHint(posture)}</span>
          </div>
          <input
            type="search"
            className="corpus-panel__search"
            placeholder="Search examples, prompts, responses…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search training examples"
          />
        </div>

        <div className="corpus-panel__filters" role="group" aria-label="Filter by training lens">
          {POSTURE_FILTERS.map((filter) => (
            <button
              key={filter.id || "all"}
              type="button"
              className={`corpus-panel__filter${
                posture === filter.id ? " corpus-panel__filter--active" : ""
              }`}
              onClick={() => setPosture(filter.id)}
            >
              {filter.label}
              {filter.id && postureCounts[filter.id] > 0 && ` (${postureCounts[filter.id]})`}
            </button>
          ))}
        </div>

        <div className="corpus-panel__toolbar">
          <button
            type="button"
            className="btn btn--sm"
            disabled={examples.length === 0}
            onClick={loadAllExamples}
          >
            Stage all for lens
          </button>
          <button
            type="button"
            className="btn btn--sm"
            disabled={bulkSelected === 0}
            onClick={() => void submitAll()}
          >
            Publish selected
          </button>
        </div>

        {filteredExamples.length === 0 && !loading ? (
          <p className="corpus-panel__empty">No seed examples match this lens or search.</p>
        ) : (
          <>
            <ul className="corpus-panel__example-list">
              {examplePage.items.map((row) => {
                const expanded = expandedId === row.id;
                return (
                  <li
                    key={row.id}
                    className={`corpus-panel__example${
                      expanded ? " corpus-panel__example--expanded" : ""
                    }`}
                  >
                    <div className="corpus-panel__example-main">
                      <span className="corpus-panel__example-icon" aria-hidden="true">
                        {corpusPostureIcon(row.posture)}
                      </span>
                      <div className="corpus-panel__example-copy">
                        <div className="corpus-panel__example-title">{row.label}</div>
                        <div className="corpus-panel__example-sub mono">{row.id}</div>
                        <div className="corpus-panel__example-meta">
                          <span className="corpus-panel__chip">
                            {corpusPostureLabel(row.posture)}
                          </span>
                          <span className="corpus-panel__chip">
                            {corpusExamplePreview(row.prompt, 72)}
                          </span>
                        </div>
                      </div>
                      <div className="corpus-panel__example-actions">
                        <button
                          type="button"
                          className="corpus-panel__toggle"
                          onClick={() => setExpandedId(expanded ? null : row.id)}
                        >
                          {expanded ? "Collapse" : "Inspect"}
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => loadExample(row)}
                        >
                          Load into editor
                        </button>
                      </div>
                    </div>
                    {expanded && (
                      <dl className="corpus-panel__detail-grid">
                        <div>
                          <dt>Mission prompt</dt>
                          <dd className="mono corpus-panel__detail-wide">{row.prompt}</dd>
                        </div>
                        <div>
                          <dt>Ideal response</dt>
                          <dd className="mono corpus-panel__detail-wide">{row.response}</dd>
                        </div>
                        <div>
                          <dt>Training lens</dt>
                          <dd>{corpusPostureLabel(row.posture)}</dd>
                        </div>
                        <div>
                          <dt>Example id</dt>
                          <dd className="mono">{row.id}</dd>
                        </div>
                      </dl>
                    )}
                  </li>
                );
              })}
            </ul>
            <ListPagination
              page={examplePage.page}
              totalPages={examplePage.totalPages}
              total={examplePage.total}
              rangeStart={examplePage.rangeStart}
              rangeEnd={examplePage.rangeEnd}
              pageSize={examplePage.pageSize}
              pageSizeOptions={examplePage.pageSizeOptions}
              onPageChange={examplePage.setPage}
              onPageSizeChange={examplePage.setPageSize}
              label="Seed library pagination"
            />
          </>
        )}
      </section>

      {bulk.length > 0 && (
        <section className="corpus-panel__section" aria-label="Bulk publish queue">
          <div className="corpus-panel__section-head">
            <div>
              <span className="corpus-panel__section-label">Bulk publish queue</span>
              <span className="corpus-panel__section-hint">
                Review staged examples before publishing to the corpus
              </span>
            </div>
          </div>
          <ul className="corpus-panel__bulk-list">
            {bulkPage.items.map((row) => (
              <li key={row.id} className="corpus-panel__bulk-row">
                <label className="corpus-panel__bulk-label">
                  <input
                    type="checkbox"
                    checked={row.checked}
                    onChange={(e) =>
                      setBulk((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, checked: e.target.checked } : item,
                        ),
                      )
                    }
                  />
                  <span className="corpus-panel__bulk-name">{row.label}</span>
                  <span className="corpus-panel__bulk-meta">
                    {corpusPostureLabel(row.posture)}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <ListPagination
            page={bulkPage.page}
            totalPages={bulkPage.totalPages}
            total={bulkPage.total}
            rangeStart={bulkPage.rangeStart}
            rangeEnd={bulkPage.rangeEnd}
            pageSize={bulkPage.pageSize}
            pageSizeOptions={bulkPage.pageSizeOptions}
            onPageChange={bulkPage.setPage}
            onPageSizeChange={bulkPage.setPageSize}
            label="Bulk queue pagination"
          />
          {bulkMsg && <p className="corpus-panel__message">{bulkMsg}</p>}
        </section>
      )}

      <section className="corpus-panel__section" aria-label="Contribute training pair">
        <div className="corpus-panel__section-head">
          <div>
            <span className="corpus-panel__section-label">Contribute pair</span>
            <span className="corpus-panel__section-hint">
              Submit authorized planner JSON, hardening advice, or safe refusal patterns
            </span>
          </div>
        </div>
        <div className="corpus-panel__form">
          <label className="corpus-panel__field">
            <span>Mission prompt</span>
            <textarea
              aria-label="Mission prompt"
              placeholder="e.g. Authorized recon on https://lab.example. Suggest next phase JSON."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={4}
            />
          </label>
          <label className="corpus-panel__field">
            <span>Ideal response</span>
            <textarea
              aria-label="Ideal response"
              placeholder='e.g. {"phase_name":"ai_recon","tools":[{"tool":"nmap"}],"stop":false}'
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              rows={4}
            />
          </label>
          <div className="corpus-panel__form-actions">
            <span className="corpus-panel__form-note">
              Published under {corpusLicenseLabel(licenseDefault)} ·{" "}
              {corpusPostureLabel(posture || "balanced")}
            </span>
            <button
              type="button"
              className="btn"
              disabled={!prompt.trim() || !response.trim()}
              onClick={() => void submitContribution()}
            >
              Contribute to corpus
            </button>
          </div>
          {contribMsg && <p className="corpus-panel__message">{contribMsg}</p>}
        </div>
      </section>
    </div>
  );
}
