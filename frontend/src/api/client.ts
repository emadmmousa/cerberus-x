export type RunRequest = {
  target: string;
  use_proxy?: boolean;
  proxy_protocol?: "http" | "https" | "socks5h";
  evasion?: "low" | "medium" | "high" | "aggressive" | "off";
  ai_mode?: boolean;
  nl_goal?: string;
  confirm_high_risk?: boolean;
};

export type RunResponse = {
  task_id: string;
  target: string;
  state: string;
  ai_mode?: boolean;
};

export type TaskStatus = {
  task_id: string;
  state: string;
  target?: string;
  phases?: Array<{ phase: string; task_id?: string; error?: string; reason?: string }>;
  results?: Record<string, unknown>;
  error?: string;
  info?: unknown;
  use_proxy?: boolean;
  proxy_protocol?: string;
  ai_mode?: boolean;
  nl_goal?: string;
  ai?: {
    goal?: string;
    mode?: string;
    steps?: Array<{ phase_name?: string; reason?: string; source?: string }>;
  };
};

export type ResultRow = {
  target: string;
  phase: string;
  tool: string;
  result: unknown;
  timestamp: string | number;
  job_id?: string | null;
};

export type ProxyStatus = {
  configured: boolean;
};

export type ProxySettings = {
  configured: boolean;
  source: "redis" | "env" | "none" | string;
  username: string;
  password_set: boolean;
  host: string;
  port: number | null;
  protocol: "http" | "https" | "socks5h" | string;
  proxy_url_redacted: string;
  ok?: boolean;
  redis?: { ok: boolean; error?: string };
  env?: { ok: boolean; error?: string };
  k8s?: { ok: boolean; error?: string };
  error?: string;
};

export type ProxySettingsPut = {
  proxy_url?: string;
  username?: string;
  password?: string;
  host?: string;
  port?: number;
  protocol?: "http" | "https" | "socks5h";
};

export type PlaybookPhase = {
  name: string;
  tools: string[];
  parallel: boolean;
  depends_on: string[];
  when?: string | null;
};

export type PlaybookSummary = {
  name?: string;
  evasion?: string;
  phases: PlaybookPhase[];
};

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const data = JSON.parse(text) as { error?: string };
    return data.error ?? text;
  } catch {
    return text || `HTTP ${res.status}`;
  }
}

export async function runPlaybook(body: RunRequest): Promise<RunResponse> {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<RunResponse>;
}

export async function getStatus(taskId: string): Promise<TaskStatus> {
  const res = await fetch(`/status/${encodeURIComponent(taskId)}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TaskStatus>;
}

export async function getResults(
  target: string,
  jobId?: string | null,
): Promise<ResultRow[]> {
  const params = new URLSearchParams({ target });
  if (jobId) params.set("job_id", jobId);
  const res = await fetch(`/results?${params.toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ResultRow[]>;
}

export async function getProxyStatus(): Promise<ProxyStatus> {
  const res = await fetch("/api/proxy/status");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ProxyStatus>;
}

export async function getProxySettings(): Promise<ProxySettings> {
  const res = await fetch("/api/proxy/settings");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ProxySettings>;
}

export async function putProxySettings(
  body: ProxySettingsPut,
): Promise<ProxySettings> {
  const res = await fetch("/api/proxy/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ProxySettings>;
}

export type ProxyTestResult = {
  ok: boolean;
  note?: string | null;
  host?: string;
  port?: number;
  username?: string;
};

export async function testProxySettings(): Promise<ProxyTestResult> {
  const res = await fetch("/api/proxy/test", { method: "POST" });
  const data = (await res.json()) as ProxyTestResult;
  if (!res.ok && data?.note == null && !("ok" in data)) {
    throw new Error(await parseError(res));
  }
  return data;
}

export async function getPlaybook(): Promise<PlaybookSummary> {
  const res = await fetch("/api/playbook");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<PlaybookSummary>;
}
