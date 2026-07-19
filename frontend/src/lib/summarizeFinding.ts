import type { ResultRow } from "../api/client";

export type SummaryStatus = "ok" | "partial" | "failed" | "skipped";

export type FindingSummary = {
  title: string;
  status: SummaryStatus;
  bullets: string[];
  openPorts?: string[];
  possibleIssues?: number;
  confirmedVulns?: number;
};

export type MissionSummaryData = {
  target: string;
  overall: "Running" | "Finished" | "Failed";
  openPorts: string[];
  possibleIssues: number;
  confirmedVulns: number;
  failedTools: number;
  impactProven: boolean;
  sessions: number;
  postExSucceeded: number;
  postExFailed: number;
  sentence: string;
};

export const PHASE_LABELS: Record<string, string> = {
  recon: "Reconnaissance",
  vulnerability_scan: "Vulnerability checks",
  exploitation: "Exploitation checks",
  credential: "Credential checks",
  proof_of_impact: "Proof of impact",
  access_gained: "Access gained",
  post_exploitation: "Post-exploitation",
};

const TOOL_TITLES: Record<string, string> = {
  masscan: "Port scan (masscan)",
  rustscan: "Port scan (rustscan)",
  nmap: "Port scan (nmap)",
  whatweb: "Website fingerprint (whatweb)",
  gobuster: "Directory discovery (gobuster)",
  theHarvester: "Public intel (theHarvester)",
  ffuf: "Web fuzzing (ffuf)",
  nuclei: "Vulnerability templates (nuclei)",
  nikto: "Web server check (nikto)",
  xsstrike: "XSS check (XSStrike)",
  sqlmap: "SQL injection check (sqlmap)",
  hydra: "Login guessing (hydra)",
  john: "Password cracking (john)",
  crackmapexec: "Network auth check (crackmapexec)",
  metasploit: "Impact check (Metasploit)",
};

const BANNER_EMAILS = new Set([
  "cmartorella@edge-security.com",
]);

const ANSI_RE = /\u001b\[[0-9;]*m/g;

export function stripAnsi(text: string): string {
  return text.replace(ANSI_RE, "");
}

function asObj(result: unknown): Record<string, unknown> {
  if (result && typeof result === "object") return result as Record<string, unknown>;
  return {};
}

function textBlob(result: unknown): string {
  const obj = asObj(result);
  const parts: string[] = [];
  for (const key of ["error", "raw_output", "message", "stdout", "stderr"]) {
    if (typeof obj[key] === "string") parts.push(obj[key] as string);
  }
  if (typeof result === "string") parts.push(result);
  return stripAnsi(parts.join("\n")).toLowerCase();
}

function isProxyReachabilityFailure(result: unknown): boolean {
  const obj = asObj(result);
  const blob = textBlob(result);
  const proxyOn =
    obj.proxy &&
    typeof obj.proxy === "object" &&
    Boolean((obj.proxy as Record<string, unknown>).enabled);
  const hints = [
    "timeout",
    "deadline exceeded",
    "ssl",
    "can't establish",
    "cannot establish",
    "unable to connect",
    "connection refused",
    "proxy",
  ];
  return Boolean(proxyOn || hints.some((h) => blob.includes(h)));
}

function extractPorts(result: unknown): string[] {
  const obj = asObj(result);
  const ports = obj.ports;
  if (!Array.isArray(ports)) return [];
  const out: string[] = [];
  for (const item of ports) {
    if (item == null) continue;
    if (typeof item === "string" || typeof item === "number") {
      out.push(String(item));
      continue;
    }
    if (typeof item === "object") {
      const p = (item as Record<string, unknown>).port;
      if (p != null) out.push(String(p));
    }
  }
  return [...new Set(out)];
}

function titleFor(tool: string): string {
  return TOOL_TITLES[tool] ?? `Check (${tool})`;
}

function summarizePorts(tool: string, result: unknown): FindingSummary {
  const ports = extractPorts(result);
  const obj = asObj(result);
  if (typeof obj.error === "string" && obj.error.trim()) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["This port scan did not finish successfully."],
      openPorts: [],
    };
  }
  if (ports.length === 0) {
    return {
      title: titleFor(tool),
      status: "ok",
      bullets: ["No open ports found."],
      openPorts: [],
    };
  }
  return {
    title: titleFor(tool),
    status: "ok",
    bullets: [`Open ports: ${ports.join(", ")}`],
    openPorts: ports,
  };
}

function summarizeHarvester(result: unknown): FindingSummary {
  const obj = asObj(result);
  if (typeof obj.error === "string" && obj.error.trim()) {
    return {
      title: titleFor("theHarvester"),
      status: "failed",
      bullets: ["Public information search did not finish."],
    };
  }
  const hosts = Array.isArray(obj.hosts)
    ? (obj.hosts as unknown[]).map(String)
    : [];
  const emails = Array.isArray(obj.emails)
    ? (obj.emails as unknown[])
        .map(String)
        .filter((e) => !BANNER_EMAILS.has(e.toLowerCase()))
    : [];
  const bullets: string[] = [];
  if (hosts.length) {
    bullets.push(
      `Found ${hosts.length} related hostname${hosts.length === 1 ? "" : "s"}.`,
    );
  }
  if (emails.length) {
    bullets.push(
      `Found ${emails.length} email address${emails.length === 1 ? "" : "es"}.`,
    );
  }
  if (!bullets.length) {
    bullets.push("No public hostnames or emails found.");
  }
  return {
    title: titleFor("theHarvester"),
    status: "ok",
    bullets,
  };
}

function proxyFail(tool: string): FindingSummary {
  return {
    title: titleFor(tool),
    status: "failed",
    bullets: ["Couldn't reach the site through the proxy."],
  };
}

function summarizeHttpTool(tool: string, result: unknown): FindingSummary {
  const obj = asObj(result);
  const blob = textBlob(result);

  if (tool === "nikto") {
    if (
      blob.includes("unknown option") ||
      blob.includes("-help") ||
      blob.includes("requires a value")
    ) {
      return {
        title: titleFor(tool),
        status: "failed",
        bullets: ["Web check didn't run correctly."],
      };
    }
    const issues = Array.isArray(obj.issues) ? obj.issues : [];
    if (issues.length && !blob.includes("unknown option")) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: [`Reported ${issues.length} possible web issue(s).`],
        possibleIssues: issues.length,
      };
    }
  }

  if (tool === "sqlmap") {
    if (obj.vulnerable === true) {
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: ["Possible SQL injection was confirmed."],
        confirmedVulns: 1,
      };
    }
    if (isProxyReachabilityFailure(result) || blob.includes("ssl")) {
      return proxyFail(tool);
    }
    return {
      title: titleFor(tool),
      status: "ok",
      bullets: ["No SQL injection confirmed."],
    };
  }

  if (tool === "nuclei") {
    const findings = Array.isArray(obj.findings) ? obj.findings : [];
    if (findings.length > 0) {
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: [`Found ${findings.length} template match(es).`],
        confirmedVulns: findings.length,
        possibleIssues: findings.length,
      };
    }
    if (isProxyReachabilityFailure(result) || (!blob && obj.proxy)) {
      // empty output with proxy often means unreachable
      if (!blob.trim() && obj.proxy) return proxyFail(tool);
    }
    if (typeof obj.error === "string" && obj.error.trim()) {
      return {
        title: titleFor(tool),
        status: "failed",
        bullets: ["Vulnerability template scan did not finish."],
      };
    }
    return {
      title: titleFor(tool),
      status: "ok",
      bullets: ["No vulnerability template matches found."],
    };
  }

  if (tool === "ffuf") {
    const results = Array.isArray(obj.results) ? obj.results : [];
    if (results.length > 0) {
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: [`Found ${results.length} interesting path(s).`],
        possibleIssues: results.length,
      };
    }
    if (blob.includes("errors:") || isProxyReachabilityFailure(result)) {
      return proxyFail(tool);
    }
  }

  if (tool === "xsstrike") {
    if (blob.includes("unable to connect") || isProxyReachabilityFailure(result)) {
      return proxyFail(tool);
    }
    const findings = Array.isArray(obj.findings) ? obj.findings : [];
    if (findings.length && !blob.includes("unable to connect")) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: ["XSS check reported possible issues."],
        possibleIssues: 1,
      };
    }
  }

  if (tool === "whatweb" || tool === "gobuster") {
    if (isProxyReachabilityFailure(result) || typeof obj.error === "string") {
      if (isProxyReachabilityFailure(result) || textBlob(result).includes("timeout")) {
        return proxyFail(tool);
      }
    }
    if (tool === "whatweb" && blob.includes("ssl")) return proxyFail(tool);
    if (tool === "gobuster" && typeof obj.error === "string") return proxyFail(tool);
  }

  if (typeof obj.error === "string" && obj.error.trim()) {
    if (isProxyReachabilityFailure(result)) return proxyFail(tool);
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["This check did not finish successfully."],
    };
  }

  if (isProxyReachabilityFailure(result) && (blob.includes("ssl") || blob.includes("timeout") || blob.includes("unable"))) {
    return proxyFail(tool);
  }

  return {
    title: titleFor(tool),
    status: "ok",
    bullets: ["Check finished with no clear issues reported."],
  };
}

function summarizeCred(tool: string, result: unknown): FindingSummary {
  const obj = asObj(result);
  if (obj.skipped === true) {
    const raw = typeof obj.raw_output === "string" ? stripAnsi(obj.raw_output) : "";
    return {
      title: titleFor(tool),
      status: "skipped",
      bullets: [
        raw.toLowerCase().includes("hash")
          ? "Skipped (no password hashes available)."
          : "Skipped for this run.",
      ],
    };
  }
  if (typeof obj.error === "string" && obj.error.toLowerCase().includes("timed out")) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Login guessing timed out before finishing."],
    };
  }
  if (typeof obj.error === "string" && obj.error.trim()) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Credential check did not finish successfully."],
    };
  }
  const creds = Array.isArray(obj.credentials) ? obj.credentials : [];
  const cracked = Array.isArray(obj.cracked) ? obj.cracked : [];
  if (creds.length || cracked.length) {
    return {
      title: titleFor(tool),
      status: "ok",
      bullets: ["Possible credentials were found."],
      possibleIssues: creds.length + cracked.length,
    };
  }
  return {
    title: titleFor(tool),
    status: "ok",
    bullets: ["No credentials found."],
  };
}

function extractSessions(result: unknown): unknown[] {
  const obj = asObj(result);
  return Array.isArray(obj.sessions) ? obj.sessions : [];
}

function isPostModule(module: string): boolean {
  return module.toLowerCase().includes("/post/") || module.toLowerCase().startsWith("post/");
}

function postModuleWording(module: string): string | null {
  const lower = module.toLowerCase();
  if (lower.includes("hashdump") || lower.includes("mimikatz")) {
    return "Credential harvesting attempted.";
  }
  if (lower.includes("persistence")) {
    return "Persistence mechanism attempted.";
  }
  return null;
}

function summarizeMetasploit(result: unknown): FindingSummary {
  const obj = asObj(result);
  const module = typeof obj.module === "string" ? obj.module : "";
  const sessions = extractSessions(result);
  const code = typeof obj.code === "string" ? obj.code : "";
  const status = typeof obj.status === "string" ? obj.status : "";
  const isPost = isPostModule(module);

  if (code === "rpc_error" || (typeof obj.error === "string" && obj.error.trim())) {
    const bullets =
      code === "rpc_error"
        ? ["Exploitation service unavailable."]
        : ["Exploitation could not finish successfully."];
    return {
      title: titleFor("metasploit"),
      status: "failed",
      bullets,
    };
  }

  if (isPost) {
    const postWording = postModuleWording(module);
    if (status === "completed") {
      return {
        title: titleFor("metasploit"),
        status: "ok",
        bullets: [postWording ?? "Post-exploitation module completed."],
      };
    }
    if (status === "attempted") {
      return {
        title: titleFor("metasploit"),
        status: "partial",
        bullets: [
          postWording ?? "Post-exploitation module attempted; outcome unconfirmed.",
        ],
      };
    }
    return {
      title: titleFor("metasploit"),
      status: "partial",
      bullets: ["Could not confirm the post-exploitation outcome."],
    };
  }

  const bullets: string[] = [];
  if (sessions.length > 0) {
    bullets.push("Access gained — session opened.");
  } else {
    bullets.push("Could not prove impact.");
  }

  return {
    title: titleFor("metasploit"),
    status: sessions.length > 0 ? "ok" : "partial",
    bullets,
  };
}

export function summarizeFinding(tool: string, result: unknown): FindingSummary {
  const normalized = tool === "theharvester" ? "theHarvester" : tool;

  if (["masscan", "rustscan", "nmap"].includes(normalized)) {
    return summarizePorts(normalized, result);
  }
  if (normalized === "theHarvester") {
    return summarizeHarvester(result);
  }
  if (["hydra", "john", "crackmapexec"].includes(normalized)) {
    return summarizeCred(normalized, result);
  }
  if (normalized === "metasploit") {
    return summarizeMetasploit(result);
  }
  if (
    [
      "whatweb",
      "gobuster",
      "ffuf",
      "nuclei",
      "nikto",
      "xsstrike",
      "sqlmap",
    ].includes(normalized)
  ) {
    return summarizeHttpTool(normalized, result);
  }

  const obj = asObj(result);
  if (obj.skipped === true) {
    return {
      title: titleFor(normalized),
      status: "skipped",
      bullets: ["Skipped for this run."],
    };
  }
  if (typeof obj.error === "string" && obj.error.trim()) {
    return {
      title: titleFor(normalized),
      status: "failed",
      bullets: ["This check did not finish successfully."],
    };
  }
  return {
    title: titleFor(normalized),
    status: "ok",
    bullets: ["Finished."],
  };
}

export function summarizeMission(
  rows: ResultRow[],
  state: string | undefined,
  target: string,
): MissionSummaryData {
  const upper = (state ?? "").toUpperCase();
  let overall: MissionSummaryData["overall"] = "Finished";
  if (["PENDING", "STARTED", "RUNNING"].includes(upper)) overall = "Running";
  else if (upper === "FAILURE") overall = "Failed";

  const portSet = new Set<string>();
  let possibleIssues = 0;
  let confirmedVulns = 0;
  let failedTools = 0;
  let impactProven = false;
  let sessions = 0;
  let postExSucceeded = 0;
  let postExFailed = 0;

  for (const row of rows) {
    const s = summarizeFinding(row.tool, row.result);
    for (const p of s.openPorts ?? []) portSet.add(p);
    possibleIssues += s.possibleIssues ?? 0;
    confirmedVulns += s.confirmedVulns ?? 0;
    if (s.status === "failed") failedTools += 1;

    if (row.tool === "metasploit") {
      const obj = asObj(row.result);
      const rowSessions = extractSessions(row.result);
      if (rowSessions.length > 0) {
        impactProven = true;
        sessions = Math.max(sessions, rowSessions.length);
      } else if (obj.vulnerable === true && rowSessions.length > 0) {
        impactProven = true;
      }

      const module = typeof obj.module === "string" ? obj.module : "";
      if (isPostModule(module)) {
        if (s.status === "failed") postExFailed += 1;
        else if (s.status === "ok") postExSucceeded += 1;
      }
    }
  }

  const openPorts = [...portSet].sort((a, b) => Number(a) - Number(b) || a.localeCompare(b));
  const parts: string[] = [];
  if (openPorts.length) {
    parts.push(`Found open port${openPorts.length === 1 ? "" : "s"} ${openPorts.join(", ")}`);
  } else if (rows.length) {
    parts.push("No open ports were reported");
  }
  if (confirmedVulns) {
    parts.push(`${confirmedVulns} confirmed vulnerability match${confirmedVulns === 1 ? "" : "es"}`);
  } else if (possibleIssues) {
    parts.push(`${possibleIssues} possible issue${possibleIssues === 1 ? "" : "s"} to review`);
  } else {
    parts.push("no confirmed vulnerabilities");
  }
  if (failedTools) {
    parts.push(
      `${failedTools} tool${failedTools === 1 ? "" : "s"} failed (often proxy or connectivity)`,
    );
  }
  if (impactProven) {
    parts.push(
      `access gained (${sessions} session${sessions === 1 ? "" : "s"})`,
    );
  }
  if (postExSucceeded || postExFailed) {
    parts.push(
      `post-exploitation: ${postExSucceeded} succeeded, ${postExFailed} failed`,
    );
  }

  let sentence = parts.join("; ") + ".";
  sentence = sentence.charAt(0).toUpperCase() + sentence.slice(1);

  return {
    target,
    overall,
    openPorts,
    possibleIssues,
    confirmedVulns,
    failedTools,
    impactProven,
    sessions,
    postExSucceeded,
    postExFailed,
    sentence,
  };
}

export function statusLabel(status: SummaryStatus): string {
  switch (status) {
    case "ok":
      return "Worked";
    case "partial":
      return "Needs attention";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
  }
}
