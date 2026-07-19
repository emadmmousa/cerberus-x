export type RunRequest = {
  target: string;
  use_proxy?: boolean;
  proxy_protocol?: "http" | "https" | "socks5h";
  evasion?: "low" | "medium" | "high" | "aggressive" | "off";
};

export type RunResponse = {
  task_id: string;
  target: string;
  state: string;
};

export type TaskStatus = {
  task_id: string;
  state: string;
  target?: string;
  phases?: Array<{ phase: string; task_id?: string; error?: string }>;
  results?: Record<string, unknown>;
  error?: string;
  info?: unknown;
  use_proxy?: boolean;
  proxy_protocol?: string;
};

export type ResultRow = {
  target: string;
  phase: string;
  tool: string;
  result: unknown;
  timestamp: string | number;
};

export type ProxyStatus = {
  configured: boolean;
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

export async function getResults(target: string): Promise<ResultRow[]> {
  const res = await fetch(`/results?target=${encodeURIComponent(target)}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ResultRow[]>;
}

export async function getProxyStatus(): Promise<ProxyStatus> {
  const res = await fetch("/api/proxy/status");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<ProxyStatus>;
}

export async function getPlaybook(): Promise<PlaybookSummary> {
  const res = await fetch("/api/playbook");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<PlaybookSummary>;
}
