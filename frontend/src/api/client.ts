import { apiFetch, apiJson, ApiError } from "./http";
import type { ChatAgentConfig } from "../lib/chatAgentOptions";

export { ApiError, apiFetch };

export type RunRequest = {
  target: string;
  use_proxy?: boolean;
  proxy_protocol?: "http" | "https" | "socks5h";
  evasion?: "low" | "medium" | "high" | "aggressive" | "off";
  ai_mode?: boolean;
  nl_goal?: string;
  confirm_high_risk?: boolean;
  posture?: "balanced" | "aggressive" | "defensive";
  playbook?: string;
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
  org_id?: string;
  ai?: {
    goal?: string;
    mode?: string;
    posture?: string;
    hardening?: Array<{ title?: string; detail?: string; severity?: string }>;
    steps?: Array<{
      phase_name?: string;
      reason?: string;
      source?: string;
      parallel?: boolean;
      stop?: boolean;
      tools?: Array<{ tool: string; args?: string[] }>;
      consensus?: {
        candidates?: number;
        confidence?: number;
        sources?: Array<string | null>;
        mode?: string;
      };
    }>;
  };
};

export type MissionSummaryRow = {
  task_id: string;
  target?: string;
  state?: string;
  ai_mode?: boolean;
  posture?: string;
  org_id?: string;
  nl_goal?: string;
  error?: string;
};

export type WorkerReadiness = {
  status: "ready" | "stale" | "unreachable";
  expected_count: number;
  missing_tasks: string[];
  message?: string;
};

export type ResultRow = {
  target: string;
  phase: string;
  tool: string;
  result: unknown;
  timestamp: string | number;
  job_id?: string | null;
};

export type ProxyStatus = { configured: boolean };

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

export type ToolCatalogEntry = {
  name: string;
  category: string;
  risk: string;
  maturity: string;
  description: string;
  binaries?: string[];
};

export type ToolsCatalogResponse = {
  count: number;
  wired_count: number;
  note?: string;
  tools: ToolCatalogEntry[];
};

export type ToolsHealthResponse = {
  task_id: string;
  state: string;
  result?: {
    count: number;
    ready: number;
    missing: number;
    tools: Array<{
      name: string;
      category?: string;
      risk?: string;
      maturity?: string;
      description?: string;
      ready: boolean;
      status: string;
      detail?: string;
    }>;
  };
  error?: string;
};

export type RbacMe = {
  authenticated: boolean;
  user?: string | null;
  role: string;
  org_id: string;
  auth_method?: string | null;
  rbac_enforce: boolean;
  enforce?: boolean;
  edition?: Record<string, unknown>;
  service_role_header?: boolean;
  packaging?: Record<string, unknown>;
  sso?: Record<string, unknown>;
};

export type UserProfile = {
  username?: string | null;
  role?: string | null;
  org_id?: string | null;
  org_name?: string | null;
  auth_method?: string | null;
  disabled?: boolean;
  has_password?: boolean;
  created_at?: number | null;
  updated_at?: number | null;
  can_edit_username?: boolean;
  can_edit_password?: boolean;
  can_edit_org_name?: boolean;
  managed_externally?: boolean;
};

export type UsernameCheckResult = {
  available: boolean;
  username: string;
  reason?: string;
};

export type ProfileUpdateBody = {
  current_password: string;
  username?: string;
  new_password?: string;
  org_name?: string;
};

export type AuthStatus = {
  authenticated?: boolean;
  user?: string;
  role?: string;
  org_id?: string;
  auth_method?: string;
};

export type OidcStatus = {
  configured?: boolean;
  provider?: string;
  login_path?: string;
  domain?: string | null;
  client_id_set?: boolean;
  missing?: string[];
};

export async function runPlaybook(body: RunRequest): Promise<RunResponse> {
  return apiJson<RunResponse>("/api/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listMissions(limit = 50): Promise<{
  count: number;
  org_id: string;
  missions: MissionSummaryRow[];
}> {
  return apiJson(`/api/missions?limit=${limit}`);
}

export async function getWorkerReadiness(): Promise<WorkerReadiness> {
  return apiJson<WorkerReadiness>("/api/workers/readiness");
}

export async function getStatus(taskId: string): Promise<TaskStatus> {
  return apiJson<TaskStatus>(`/status/${encodeURIComponent(taskId)}`);
}

export async function getResults(
  target: string,
  jobId?: string | null,
): Promise<ResultRow[]> {
  const params = new URLSearchParams({ target });
  if (jobId) params.set("job_id", jobId);
  return apiJson<ResultRow[]>(`/results?${params.toString()}`);
}

export async function getProxyStatus(): Promise<ProxyStatus> {
  return apiJson<ProxyStatus>("/api/proxy/status");
}

export async function getProxySettings(): Promise<ProxySettings> {
  return apiJson<ProxySettings>("/api/proxy/settings");
}

export async function putProxySettings(
  body: ProxySettingsPut,
): Promise<ProxySettings> {
  return apiJson<ProxySettings>("/api/proxy/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export type ProxyTestResult = {
  ok: boolean;
  note?: string | null;
  host?: string;
  port?: number;
  username?: string;
};

export async function testProxySettings(): Promise<ProxyTestResult> {
  const res = await apiFetch("/api/proxy/test", { method: "POST" });
  const data = (await res.json()) as ProxyTestResult;
  if (!res.ok && data?.note == null && !("ok" in data)) {
    throw new ApiError(res.status, "proxy test failed");
  }
  return data;
}

export async function getPlaybook(path?: string): Promise<PlaybookSummary> {
  const q = path ? `?playbook=${encodeURIComponent(path)}` : "";
  return apiJson<PlaybookSummary>(`/api/playbook${q}`);
}

export type PlaybookCatalogEntry = {
  id: string;
  path: string;
  name: string;
  description?: string;
  phase_count?: number;
  recommended_for?: string[];
};

export async function listPlaybooks(
  posture?: string,
): Promise<{ playbooks: PlaybookCatalogEntry[]; recommended?: string | null }> {
  const q = posture ? `?posture=${encodeURIComponent(posture)}` : "";
  return apiJson(`/api/playbooks${q}`);
}

export async function getHardeningReport(jobId: string): Promise<{
  recommendations: Array<{ title?: string; detail?: string; severity?: string }>;
  markdown?: string;
  posture?: string;
}> {
  return apiJson(`/api/missions/${encodeURIComponent(jobId)}/hardening`);
}

export async function getToolsCatalog(): Promise<ToolsCatalogResponse> {
  return apiJson<ToolsCatalogResponse>("/api/tools");
}

export async function getToolsHealth(
  taskId?: string | null,
): Promise<ToolsHealthResponse> {
  const url = taskId
    ? `/api/tools/health?task_id=${encodeURIComponent(taskId)}`
    : "/api/tools/health";
  return apiJson<ToolsHealthResponse>(url);
}

export async function getRbacMe(skipAuthRedirect = true): Promise<RbacMe> {
  return apiJson<RbacMe>("/api/rbac/me", { skipAuthRedirect });
}

export async function getAuthStatus(): Promise<AuthStatus> {
  return apiJson<AuthStatus>("/auth/status", { skipAuthRedirect: true });
}

export async function getOidcStatus(): Promise<OidcStatus> {
  return apiJson<OidcStatus>("/api/oidc/status", { skipAuthRedirect: true });
}

export async function localLogin(
  username: string,
  password: string,
): Promise<{ status: string; user: string; role?: string }> {
  return apiJson("/auth/local/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
    skipAuthRedirect: true,
  });
}

export async function localSignup(
  username: string,
  password: string,
  org?: string,
): Promise<{ status: string; user: string; role?: string; org_id?: string }> {
  return apiJson("/auth/local/signup", {
    method: "POST",
    body: JSON.stringify({ username, password, org }),
    skipAuthRedirect: true,
  });
}

export async function logoutSession(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST", skipAuthRedirect: true });
}

export async function getProfile(): Promise<UserProfile> {
  return apiJson<UserProfile>("/api/profile/me");
}

export async function checkUsernameAvailable(username: string): Promise<UsernameCheckResult> {
  const params = new URLSearchParams({ username });
  return apiJson<UsernameCheckResult>(`/api/profile/username/check?${params.toString()}`);
}

export async function updateProfile(body: ProfileUpdateBody): Promise<UserProfile> {
  return apiJson<UserProfile>("/api/profile", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function getAiLabStatus(): Promise<Record<string, unknown>> {
  return apiJson("/api/ai-lab/status");
}

export async function getEditionStatus(): Promise<PackagingStatus> {
  return apiJson<PackagingStatus>("/api/edition/status");
}

export type ManagedHostingConfig = {
  enabled?: boolean;
  app_base_url?: string;
  control_plane_url?: string | null;
  health_callback_path?: string;
  tenant_header?: string;
};

export type SsoPackagingStatus = {
  ready?: boolean;
  preferred?: string | null;
  auth0?: {
    configured?: boolean;
    domain_set?: boolean;
    client_id_set?: boolean;
    missing?: string[];
    login_path?: string;
    callback_url?: string;
  };
  oidc?: {
    configured?: boolean;
    issuer?: string;
    client_id_set?: boolean;
  };
};

export type PackagingStatus = {
  edition?: string;
  features?: Record<string, boolean | string>;
  sso?: SsoPackagingStatus;
  managed_hosting?: ManagedHostingConfig;
  notes?: string;
};

export type HeartbeatResult = {
  ok?: boolean;
  skipped?: boolean;
  reason?: string;
  status?: number;
  url?: string;
  error?: string;
  response?: string;
  payload?: Record<string, unknown>;
};

export async function getEditionHeartbeatPayload(): Promise<{ payload: Record<string, unknown> }> {
  return apiJson("/api/edition/heartbeat");
}

export async function sendEditionHeartbeat(): Promise<HeartbeatResult> {
  return apiJson("/api/edition/heartbeat", { method: "POST" });
}

export async function getAdminSession(): Promise<RbacMe> {
  return apiJson<RbacMe>("/api/admin/session");
}

export async function getBlackboard(missionId: string): Promise<{
  keys: string[];
  items: Array<Record<string, unknown>>;
  org_id?: string;
}> {
  return apiJson(`/api/blackboard/${encodeURIComponent(missionId)}`);
}

export async function getAuditRecent(limit = 40): Promise<{
  count: number;
  events: Array<Record<string, unknown>>;
}> {
  return apiJson(`/api/audit/recent?limit=${limit}`);
}

export async function getScaffolds(): Promise<Record<string, unknown>> {
  return apiJson("/api/scaffolds");
}

export async function getMarketplace(): Promise<Record<string, unknown>> {
  return apiJson("/api/scaffolds/marketplace");
}

export async function registerMarketplace(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiJson("/api/scaffolds/marketplace", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteMarketplace(id: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/scaffolds/marketplace/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function getDatasetExamples(
  posture?: string,
  limit = 50,
): Promise<{
  examples: Array<Record<string, unknown>>;
  guidance?: string;
  count?: number;
  posture?: string | null;
  limit?: number;
}> {
  const params = new URLSearchParams();
  if (posture) params.set("posture", posture);
  params.set("limit", String(limit));
  return apiJson(`/api/dataset/examples?${params}`);
}

export async function contributeDataset(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiJson("/api/dataset/contribute", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- Admin console ---
export type AdminUser = {
  username: string;
  role: string;
  org_id: string;
  auth_method: string;
  disabled: boolean;
  has_password: boolean;
  created_at?: number;
  updated_at?: number;
};

export type AdminOrg = {
  id: string;
  name: string;
  user_count?: number;
  created_at?: number;
};

export type AdminSettings = {
  settings: {
    rbac_enforce: boolean | null;
    edition: string | null;
    auth_methods: Record<string, boolean>;
    auto_scale: boolean | null;
    auto_train: boolean | null;
    learning_tick: boolean | null;
  };
  effective: {
    rbac_enforce: boolean;
    edition: string;
    auto_scale: boolean;
    auto_train: boolean;
    learning_tick: boolean;
  };
  secret_key_insecure?: boolean;
  options: { editions: string[]; roles: string[]; auth_methods: string[] };
  sso: {
    ready?: boolean;
    preferred?: string | null;
    auth0?: { configured?: boolean };
    oidc?: { configured?: boolean };
  };
};

export type AuditEvent = {
  timestamp?: string;
  event_type?: string;
  severity?: string;
  actor?: string;
  actor_role?: string;
  actor_org?: string;
  source_ip?: string;
  data?: unknown;
};

export async function listAdminUsers(): Promise<AdminUser[]> {
  const d = await apiJson<{ users: AdminUser[] }>("/api/admin/users");
  return d.users;
}

export async function createAdminUser(body: {
  username: string;
  password?: string;
  role: string;
  org_id: string;
  auth_method?: string;
}): Promise<AdminUser> {
  const d = await apiJson<{ user: AdminUser }>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return d.user;
}

export async function updateAdminUser(
  username: string,
  body: Partial<{
    role: string;
    org_id: string;
    auth_method: string;
    disabled: boolean;
    password: string;
  }>,
): Promise<AdminUser> {
  const d = await apiJson<{ user: AdminUser }>(
    `/api/admin/users/${encodeURIComponent(username)}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
  return d.user;
}

export async function deleteAdminUser(username: string): Promise<void> {
  await apiJson(`/api/admin/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
  });
}

export async function listAdminOrgs(): Promise<AdminOrg[]> {
  const d = await apiJson<{ orgs: AdminOrg[] }>("/api/admin/orgs");
  return d.orgs;
}

export async function createAdminOrg(body: {
  id: string;
  name?: string;
}): Promise<AdminOrg> {
  const d = await apiJson<{ org: AdminOrg }>("/api/admin/orgs", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return d.org;
}

export async function updateAdminOrg(
  id: string,
  body: { name: string },
): Promise<AdminOrg> {
  const d = await apiJson<{ org: AdminOrg }>(
    `/api/admin/orgs/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
  return d.org;
}

export async function deleteAdminOrg(id: string): Promise<void> {
  await apiJson(`/api/admin/orgs/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function associateUserOrg(
  id: string,
  username: string,
): Promise<AdminUser> {
  const d = await apiJson<{ user: AdminUser }>(
    `/api/admin/orgs/${encodeURIComponent(id)}/associate`,
    { method: "POST", body: JSON.stringify({ username }) },
  );
  return d.user;
}

export async function getAdminSettings(): Promise<AdminSettings> {
  return apiJson<AdminSettings>("/api/admin/settings");
}

export async function setRbacEnforce(
  enforce: boolean | null,
): Promise<AdminSettings["settings"]> {
  const d = await apiJson<{ settings: AdminSettings["settings"] }>(
    "/api/admin/settings/rbac",
    { method: "PUT", body: JSON.stringify({ enforce }) },
  );
  return d.settings;
}

export async function setEdition(
  edition: string | null,
): Promise<AdminSettings["settings"]> {
  const d = await apiJson<{ settings: AdminSettings["settings"] }>(
    "/api/admin/settings/edition",
    { method: "PUT", body: JSON.stringify({ edition }) },
  );
  return d.settings;
}

export async function setAuthMethod(
  method: string,
  enabled: boolean,
): Promise<AdminSettings["settings"]> {
  const d = await apiJson<{ settings: AdminSettings["settings"] }>(
    "/api/admin/settings/auth",
    { method: "PUT", body: JSON.stringify({ method, enabled }) },
  );
  return d.settings;
}

export async function setOpsSettings(body: {
  auto_scale?: boolean | null;
  auto_train?: boolean | null;
  learning_tick?: boolean | null;
}): Promise<AdminSettings["settings"]> {
  const d = await apiJson<{ settings: AdminSettings["settings"] }>(
    "/api/admin/settings/ops",
    { method: "PUT", body: JSON.stringify(body) },
  );
  return d.settings;
}

export async function stopMission(id: string): Promise<Record<string, unknown>> {
  return apiJson(`/api/admin/missions/${encodeURIComponent(id)}/stop`, {
    method: "POST",
  });
}

export async function restartMission(
  id: string,
): Promise<{ task_id: string; restarted_from: string }> {
  return apiJson(`/api/admin/missions/${encodeURIComponent(id)}/restart`, {
    method: "POST",
  });
}

export async function deleteMission(id: string): Promise<void> {
  await apiJson(`/api/admin/missions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function editMission(
  id: string,
  body: Partial<{ nl_goal: string; posture: string; target: string }>,
): Promise<Record<string, unknown>> {
  return apiJson(`/api/admin/missions/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function getAdminLogs(
  limit = 100,
  filters: { event_type?: string; actor?: string } = {},
): Promise<{ count: number; events: AuditEvent[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (filters.event_type) params.set("event_type", filters.event_type);
  if (filters.actor) params.set("actor", filters.actor);
  return apiJson(`/api/admin/logs?${params}`);
}

// --- Mission chat agent ---
export type MissionPlanPhase = {
  name: string;
  parallel?: boolean;
  tools: Array<{ tool: string; args?: string[] }>;
};

export type MissionProposal = {
  target: string;
  posture: string;
  nl_goal: string;
  stealth?: string | null;
  ready: boolean;
  auto_execute?: boolean;
  missing?: string[];
  osint_seeds?: Array<{ kind: string; value: string; display?: string }>;
  plan?: {
    phases: MissionPlanPhase[];
    new_tools?: Array<{
      name: string;
      binary: string;
      args_template: string[];
      description?: string;
      risk?: string;
    }>;
    tool_names?: string[];
  };
};

export type ChatMessage = {
  role: string;
  content: string;
  ts?: number;
  thinking_content?: string;
  proposal?: MissionProposal;
  mission_card?: { task_id: string; target: string; state?: string };
};

export type MissionChatThread = {
  id: string;
  org_id: string;
  messages: ChatMessage[];
  draft: MissionProposal | null;
  mission_ids: string[];
};

export type ChatAgentOptionsPayload = {
  deep_think?: boolean;
  web_search?: boolean;
  model?: string;
  posture?: string;
  attachments?: Array<{ name: string; content: string; type?: string }>;
};

export type { ChatAgentConfig };
export type ChatAgentConfigResponse = ChatAgentConfig;

export async function getChatAgentConfig(): Promise<ChatAgentConfig> {
  return apiJson("/api/chat/config");
}

export async function createMissionChat(): Promise<{ chat_id: string }> {
  return apiJson("/api/chat/missions", { method: "POST", body: "{}" });
}

export async function getMissionChat(chatId: string): Promise<MissionChatThread> {
  return apiJson(`/api/chat/missions/${encodeURIComponent(chatId)}`);
}

export async function postMissionChatMessage(
  chatId: string,
  content: string,
  options?: ChatAgentOptionsPayload,
): Promise<{
  reply: string;
  proposal: MissionProposal;
  draft: MissionProposal | null;
  messages: ChatMessage[];
  mission_launched?: {
    task_id: string;
    target: string;
    state: string;
    registered_tools?: string[];
  } | null;
  launch_error?: string | null;
}> {
  return apiJson(`/api/chat/missions/${encodeURIComponent(chatId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, options }),
  });
}

export type CustomToolDraft = {
  name: string;
  binary: string;
  args_template: string[];
  description?: string;
  risk?: string;
  category?: string;
};

export type ChatStreamHandlers = {
  onDelta: (text: string) => void;
  onDone: (payload: {
    reply: string;
    proposal: MissionProposal | null;
    draft: MissionProposal | null;
    toolProposal: CustomToolDraft | null;
    messages: ChatMessage[];
    mission_launched?: {
      task_id: string;
      target: string;
      state: string;
      registered_tools?: string[];
    } | null;
    launch_error?: string | null;
  }) => void;
  onError?: (message: string) => void;
  signal?: AbortSignal;
};

/**
 * Stream an assistant reply token-by-token over SSE. Falls back to throwing on
 * transport errors so the caller can degrade to the non-streaming endpoint.
 */
export async function streamMissionChatMessage(
  chatId: string,
  content: string,
  handlers: ChatStreamHandlers,
  options?: ChatAgentOptionsPayload,
): Promise<void> {
  const res = await apiFetch(
    `/api/chat/missions/${encodeURIComponent(chatId)}/stream`,
    {
      method: "POST",
      body: JSON.stringify({ content, options }),
      skipAuthRedirect: true,
      signal: handlers.signal,
    },
  );
  if (!res.ok || !res.body) {
    throw new ApiError(res.status, "stream failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleEvent = (block: string) => {
    const line = block
      .split("\n")
      .find((l) => l.startsWith("data:"));
    if (!line) return;
    const raw = line.slice(5).trim();
    if (!raw) return;
    let evt: Record<string, unknown>;
    try {
      evt = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return;
    }
    if (typeof evt.delta === "string") {
      handlers.onDelta(evt.delta);
    } else if (evt.done) {
      handlers.onDone({
        reply: String(evt.reply ?? ""),
        proposal: (evt.proposal as MissionProposal) ?? null,
        draft: (evt.draft as MissionProposal) ?? null,
        toolProposal: (evt.tool_proposal as CustomToolDraft) ?? null,
        messages: (evt.messages as ChatMessage[]) ?? [],
        mission_launched:
          (evt.mission_launched as {
            task_id: string;
            target: string;
            state: string;
            registered_tools?: string[];
          } | null) ?? null,
        launch_error: typeof evt.launch_error === "string" ? evt.launch_error : null,
      });
    } else if (typeof evt.error === "string") {
      handlers.onError?.(evt.error);
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      handleEvent(block);
    }
  }
  if (buffer.trim()) handleEvent(buffer);
}

export async function dismissMissionChatDraft(
  chatId: string,
): Promise<{ ok: boolean }> {
  return apiJson(`/api/chat/missions/${encodeURIComponent(chatId)}/dismiss`, {
    method: "POST",
    body: "{}",
  });
}

export async function launchMissionChat(
  chatId: string,
  body: Record<string, unknown> = {},
): Promise<{
  task_id: string;
  target: string;
  state: string;
  messages: ChatMessage[];
}> {
  return apiJson(`/api/chat/missions/${encodeURIComponent(chatId)}/launch`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type CustomTool = CustomToolDraft & {
  enabled: boolean;
  created_by?: string | null;
  created_at?: number | null;
};

export async function listCustomTools(): Promise<{
  count: number;
  tools: CustomTool[];
}> {
  return apiJson(`/api/tools/custom`);
}

export async function registerCustomTool(
  tool: CustomToolDraft,
): Promise<{ ok: boolean; tool: CustomTool }> {
  return apiJson(`/api/tools/custom`, {
    method: "POST",
    body: JSON.stringify(tool),
  });
}

export async function deleteCustomTool(
  name: string,
): Promise<{ ok: boolean; removed: string }> {
  return apiJson(`/api/tools/custom/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export type AuthorizedTargetRow = {
  target: string;
  host?: string;
  kind?: string;
  value?: string;
  authorized?: boolean;
  expiry?: string | null;
  notes?: string | null;
  added_at?: string | null;
};

export async function listAuthorizedTargets(): Promise<{
  count: number;
  targets: AuthorizedTargetRow[];
}> {
  return apiJson("/api/authorized-targets");
}

export async function addAuthorizedTarget(body: {
  target: string;
  kind?: string;
  notes?: string;
  expiry?: string;
  authorized?: boolean;
}): Promise<{ ok: boolean; target: AuthorizedTargetRow }> {
  return apiJson("/api/authorized-targets", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteAuthorizedTarget(
  target: string,
): Promise<{ ok: boolean; removed: string }> {
  return apiJson(`/api/authorized-targets/${encodeURIComponent(target)}`, {
    method: "DELETE",
  });
}

export type BreachProviderBlock = {
  configured: boolean;
  available: boolean;
  product?: string;
  account?: Record<string, unknown>;
};

export type BreachProviderStatus = {
  enabled: boolean;
  ready: boolean;
  breach_vault: BreachProviderBlock;
  leak_radar: BreachProviderBlock;
};

export async function fetchBreachIntelStatus(): Promise<BreachProviderStatus> {
  return apiJson("/api/osint/breach/status");
}
