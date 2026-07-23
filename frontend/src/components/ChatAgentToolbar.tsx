import { useEffect, useRef, useState } from "react";
import {
  loadChatOptions,
  POSTURE_LABELS,
  saveChatOptions,
  type ChatAgentConfig,
  type ChatAgentOptions,
  type ChatAttachment,
  type ChatPosture,
} from "../lib/chatAgentOptions";

type Props = {
  config: ChatAgentConfig | null;
  options: ChatAgentOptions;
  disabled?: boolean;
  hideDeepThink?: boolean;
  onChange: (next: ChatAgentOptions) => void;
};

export function ChatAgentToolbar({ config, options, disabled, hideDeepThink = false, onChange }: Props) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [attachError, setAttachError] = useState<string | null>(null);

  useEffect(() => {
    saveChatOptions(options);
  }, [options]);

  function patch(partial: Partial<ChatAgentOptions>) {
    onChange({ ...options, ...partial });
  }

  function onFilesSelected(files: FileList | null) {
    if (!files?.length) return;
    const limits = config?.attachment_limits ?? { max_files: 3, max_bytes: 96000 };
    const next = [...options.attachments];
    setAttachError(null);

    Array.from(files).forEach((file) => {
      if (next.length >= limits.max_files) {
        setAttachError(`Max ${limits.max_files} files`);
        return;
      }
      if (file.size > limits.max_bytes) {
        setAttachError(`${file.name} too large`);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const content = String(reader.result ?? "");
        const row: ChatAttachment = {
          name: file.name,
          content,
          type: file.type || "text/plain",
        };
        patch({ attachments: [...options.attachments, row] });
      };
      reader.readAsText(file);
    });
  }

  const models = config?.models?.length
    ? config.models
    : [{ id: options.model || "firebreak", label: "Firebreak" }];
  const modelValue = options.model || config?.default_model || models[0]?.id || "firebreak";

  return (
    <div className="chat-toolbar" aria-label="Chat agent controls">
      <div className="chat-toolbar__row">
        {!hideDeepThink && (
          <button
            type="button"
            className={`chat-tool chat-tool--think${options.deepThink ? " chat-tool--on" : ""}`}
            disabled={disabled}
            aria-pressed={options.deepThink}
            title="Deep-think — extended reasoning (slower)"
            onClick={() => patch({ deepThink: !options.deepThink })}
          >
            <span className="chat-tool__icon" aria-hidden="true">
              🧠
            </span>
            <span className="chat-tool__label">Deep think</span>
          </button>
        )}

        <button
          type="button"
          className={`chat-tool chat-tool--attach${options.attachments.length ? " chat-tool--on" : ""}`}
          disabled={disabled}
          title="Attach text files for context"
          onClick={() => fileRef.current?.click()}
        >
          <span className="chat-tool__icon" aria-hidden="true">
            📎
          </span>
          <span className="chat-tool__label">Attach</span>
          {options.attachments.length > 0 && (
            <span className="chat-tool__badge">{options.attachments.length}</span>
          )}
        </button>
        <input
          ref={fileRef}
          type="file"
          className="sr-only"
          multiple
          accept=".txt,.md,.json,.yaml,.yml,.csv,.log,.xml,.html,.py,.js,.ts,.env,.conf,.cfg,text/*"
          onChange={(e) => {
            onFilesSelected(e.target.files);
            e.target.value = "";
          }}
        />

        <button
          type="button"
          className={`chat-tool chat-tool--search${options.webSearch ? " chat-tool--on" : ""}`}
          disabled={disabled}
          aria-pressed={options.webSearch}
          title="Search the web and inject results into context"
          onClick={() => patch({ webSearch: !options.webSearch })}
        >
          <span className="chat-tool__icon" aria-hidden="true">
            🌐
          </span>
          <span className="chat-tool__label">Web search</span>
        </button>

        <button
          type="button"
          className={`chat-tool chat-tool--proxy${options.useProxy ? " chat-tool--on" : ""}`}
          disabled={disabled}
          aria-pressed={options.useProxy}
          title="Route scans through your configured residential proxy"
          onClick={() => patch({ useProxy: !options.useProxy })}
        >
          <span className="chat-tool__icon" aria-hidden="true">
            ⇄
          </span>
          <span className="chat-tool__label">Proxy</span>
        </button>

        <button
          type="button"
          className={`chat-tool chat-tool--autorun${options.autoRun ? " chat-tool--on" : ""}`}
          disabled={disabled}
          aria-pressed={options.autoRun}
          title="Auto Run — launch a ready plan on execute intent without a confirm click (authorized targets only)"
          onClick={() =>
            patch(
              options.autoRun
                ? { autoRun: false, alwaysRun: false }
                : { autoRun: true },
            )
          }
        >
          <span className="chat-tool__icon" aria-hidden="true">
            ⚡
          </span>
          <span className="chat-tool__label">Auto Run</span>
        </button>

        <button
          type="button"
          className={`chat-tool chat-tool--alwaysrun${options.alwaysRun ? " chat-tool--on" : ""}`}
          disabled={disabled}
          aria-pressed={options.alwaysRun}
          title="Always Run — auto-launch every ready plan, including plan-only requests (authorized targets only)"
          onClick={() =>
            patch(
              options.alwaysRun
                ? { alwaysRun: false }
                : { alwaysRun: true, autoRun: true },
            )
          }
        >
          <span className="chat-tool__icon" aria-hidden="true">
            ⏩
          </span>
          <span className="chat-tool__label">Always Run</span>
        </button>

        <label className="chat-tool chat-tool--model">
          <span className="chat-tool__icon" aria-hidden="true">
            ◈
          </span>
          <span className="sr-only">Model</span>
          <select
            value={modelValue}
            disabled={disabled}
            onChange={(e) => patch({ model: e.target.value })}
            aria-label="Model"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>

        <div
          className="chat-power"
          role="group"
          aria-label="Engagement power (posture)"
        >
          <span className="chat-power__label">Power</span>
          {(config?.postures ?? [
            { id: "defensive" as const, label: "Defensive", power: 1 },
            { id: "balanced" as const, label: "Balanced", power: 2 },
            { id: "aggressive" as const, label: "Aggressive", power: 3 },
          ]).map((p) => (
            <button
              key={p.id}
              type="button"
              className={`chat-power__seg chat-power__seg--${p.id}${
                options.posture === p.id ? " chat-power__seg--active" : ""
              }`}
              disabled={disabled}
              aria-pressed={options.posture === p.id}
              title={p.label}
              onClick={() => patch({ posture: p.id as ChatPosture })}
            >
              {POSTURE_LABELS[p.id as ChatPosture]}
            </button>
          ))}
        </div>
      </div>

      {options.attachments.length > 0 && (
        <ul className="chat-toolbar__attachments">
          {options.attachments.map((file) => (
            <li key={file.name}>
              <span className="mono">{file.name}</span>
              <button
                type="button"
                className="chat-toolbar__remove"
                disabled={disabled}
                aria-label={`Remove ${file.name}`}
                onClick={() =>
                  patch({
                    attachments: options.attachments.filter((a) => a.name !== file.name),
                  })
                }
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {attachError && <p className="chat-toolbar__hint">{attachError}</p>}

      {config && (!config.llm_configured || config.llm_reachable === false) && (
        <p className="chat-toolbar__hint">
          {!config.llm_configured
            ? "LLM not configured — replies may use heuristics only."
            : "LLM unreachable — check Ollama is running, then refresh."}
        </p>
      )}

      {!config && (
        <p className="chat-toolbar__hint chat-toolbar__hint--muted">
          Loading agent config…
        </p>
      )}

      {(options.deepThink ||
        options.webSearch ||
        options.useProxy ||
        options.autoRun ||
        options.alwaysRun) && (
        <div className="chat-toolbar__active-tags">
          {options.deepThink && <span className="chat-tag">Deep think</span>}
          {options.webSearch && <span className="chat-tag">Web search</span>}
          {options.useProxy && <span className="chat-tag">Proxy</span>}
          {options.alwaysRun ? (
            <span className="chat-tag chat-tag--run">Always Run</span>
          ) : (
            options.autoRun && <span className="chat-tag chat-tag--run">Auto Run</span>
          )}
          <span className="chat-tag chat-tag--posture">{options.posture}</span>
        </div>
      )}
    </div>
  );
}

export function useChatAgentOptions(initial?: Partial<ChatAgentOptions>) {
  const [options, setOptions] = useState<ChatAgentOptions>(() => ({
    ...loadChatOptions(),
    ...initial,
  }));
  return [options, setOptions] as const;
}
