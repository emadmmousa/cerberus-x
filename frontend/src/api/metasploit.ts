export type MsfModule = {
  type?: string;
  name?: string;
  [key: string]: unknown;
};

async function parseError(res: Response): Promise<string> {
  const data = await res.json().catch(() => ({}));
  return (data as { error?: string }).error ?? `HTTP ${res.status}`;
}

export async function msfHealth(): Promise<unknown> {
  const res = await fetch("/api/metasploit/health");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function searchModules(
  query: string,
  moduleType?: string,
): Promise<MsfModule[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (moduleType) params.set("type", moduleType);
  const res = await fetch(`/api/metasploit/modules?${params.toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { modules?: MsfModule[] };
  return data.modules ?? [];
}

export async function loadModule(type: string, name: string): Promise<unknown> {
  const res = await fetch(
    `/api/metasploit/modules/${encodeURIComponent(type)}/${encodeURIComponent(name)}`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function runModule(
  type: string,
  name: string,
  options: Record<string, unknown>,
): Promise<unknown> {
  const res = await fetch("/api/metasploit/modules/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, name, options }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listJobs(): Promise<unknown> {
  const res = await fetch("/api/metasploit/jobs");
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { jobs?: unknown };
  return data.jobs ?? data;
}

export async function stopJob(jobId: string): Promise<unknown> {
  const res = await fetch(
    `/api/metasploit/jobs/${encodeURIComponent(jobId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listSessions(): Promise<unknown> {
  const res = await fetch("/api/metasploit/sessions");
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { sessions?: unknown };
  return data.sessions ?? data;
}

export async function sessionCommand(
  sessionId: string,
  command: string,
): Promise<unknown> {
  const res = await fetch(
    `/api/metasploit/sessions/${encodeURIComponent(sessionId)}/command`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function closeSession(sessionId: string): Promise<unknown> {
  const res = await fetch(
    `/api/metasploit/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
