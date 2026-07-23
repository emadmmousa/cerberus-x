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
  attack: "Attack phase",
};

const TOOL_TITLES: Record<string, string> = {
  masscan: "Port scan (masscan)",
  rustscan: "Port scan (rustscan)",
  nmap: "Port scan (nmap)",
  whatweb: "Website fingerprint (whatweb)",
  httpx: "HTTP probe (httpx)",
  gobuster: "Directory discovery (gobuster)",
  theHarvester: "Public intel (theHarvester)",
  subfinder: "Subdomain scrape (subfinder)",
  gau: "Archive URL scrape (gau)",
  sherlock: "Username scrape (sherlock)",
  ffuf: "Web fuzzing (ffuf)",
  nuclei: "Vulnerability templates (nuclei)",
  nikto: "Web server check (nikto)",
  xsstrike: "XSS check (XSStrike)",
  sqlmap: "SQL injection check (sqlmap)",
  hydra: "Login guessing (hydra)",
  john: "Password cracking (john)",
  crackmapexec: "Network auth check (crackmapexec)",
  metasploit: "Impact check (Metasploit)",
  phase: "Phase orchestration",
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

function proxyMeta(result: unknown): Record<string, unknown> | null {
  const obj = asObj(result);
  if (!obj.proxy || typeof obj.proxy !== "object") return null;
  return obj.proxy as Record<string, unknown>;
}

function proxyNote(result: unknown): string {
  const meta = proxyMeta(result);
  return typeof meta?.note === "string" ? meta.note.toLowerCase() : "";
}

function isProxyEnabled(result: unknown): boolean {
  return Boolean(proxyMeta(result)?.enabled);
}

function hasProxyUpstreamFailure(result: unknown): boolean {
  const meta = proxyMeta(result);
  // After auto-fallback to direct, note may still mention Oxylabs — do not
  // treat successful/failed direct runs as "couldn't reach through proxy".
  if (meta?.mode === "direct_fallback") return false;
  const note = proxyNote(result);
  if (!note) return false;
  return (
    note.includes("unreachable") ||
    note.includes("timeout") ||
    note.includes("timed out") ||
    note.includes("gaierror") ||
    note.includes("connect") ||
    note.includes("empty response")
  );
}

function hasReachabilityFailureText(result: unknown): boolean {
  const blob = textBlob(result);
  const hints = [
    "timeout",
    "deadline exceeded",
    "ssl session is not started",
    "can't establish",
    "cannot establish",
    "unable to connect",
    "connection refused",
    "context deadline exceeded",
  ];
  return hints.some((h) => blob.includes(h));
}

/** True only when failure evidence points at proxy/connectivity — not merely proxy.enabled. */
function isProxyReachabilityFailure(result: unknown): boolean {
  if (hasProxyUpstreamFailure(result)) return true;
  return isProxyEnabled(result) && hasReachabilityFailureText(result);
}

function reachabilityFail(result: unknown, tool: string): FindingSummary {
  if (hasProxyUpstreamFailure(result) || (isProxyEnabled(result) && proxyNote(result))) {
    return proxyFail(tool);
  }
  const blob = textBlob(result);
  if (blob.includes("ssl")) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Couldn't complete a secure connection to the site."],
    };
  }
  // Prefer explicit connect failures over proxy-note "TimeoutError" noise.
  if (blob.includes("unable to connect") || blob.includes("couldn't connect")) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Couldn't connect to the site."],
    };
  }
  if (blob.includes("timeout") || blob.includes("deadline")) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Connection timed out before the check finished."],
    };
  }
  return {
    title: titleFor(tool),
    status: "failed",
    bullets: ["Couldn't connect to the site."],
  };
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
    const blob = textBlob(result);
    if (
      tool === "nmap" &&
      (blob.includes("filtered") || blob.includes("ignored states"))
    ) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: ["Couldn't confirm open ports (responses filtered)."],
        openPorts: [],
      };
    }
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
  const targetHost = String(obj.target ?? "")
    .toLowerCase()
    .replace(/^www\./, "");
  const hosts = Array.isArray(obj.hosts)
    ? (obj.hosts as unknown[])
        .map(String)
        .filter((h) => {
          const normalized = h.toLowerCase().replace(/^www\./, "");
          return normalized !== targetHost && normalized !== "";
        })
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

function sqlmapReachabilityFailure(result: unknown): boolean {
  if (isProxyReachabilityFailure(result)) return true;
  const blob = textBlob(result);
  return (
    /\bssl session is not started\b/i.test(blob) ||
    /\bssl error\b/i.test(blob) ||
    /\bssl handshake\b/i.test(blob) ||
    /\bunable to connect\b/i.test(blob) ||
    /\bcouldn't connect\b/i.test(blob) ||
    /\bconnection refused\b/i.test(blob)
  );
}

function sqlmapRanInjectionTests(blob: string): boolean {
  return (
    /testing if the target url/i.test(blob) ||
    /testing for sql injection/i.test(blob) ||
    /testing '/i.test(blob) ||
    /sql injection point/i.test(blob) ||
    /parameter '/i.test(blob) ||
    /parameters:/i.test(blob) ||
    /appears to be injectable/i.test(blob) ||
    /is vulnerable/i.test(blob) ||
    /target url is not injectable/i.test(blob) ||
    /not injectable/i.test(blob) ||
    /testing connection to the target/i.test(blob) ||
    /heuristic \(basic\) test shows/i.test(blob)
  );
}

function sqlmapNoInjectionSurface(result: unknown): boolean {
  const obj = asObj(result);
  if (obj.no_injection_surface === true) return true;
  const blob = textBlob(result);
  if (
    /no usable links found/i.test(blob) ||
    /no injection point/i.test(blob) ||
    /no parameter\(s\) found/i.test(blob) ||
    /does not appear to be dynamic/i.test(blob)
  ) {
    return true;
  }
  const crawled =
    /starting crawler/i.test(blob) ||
    /searching for links with depth/i.test(blob) ||
    /normalize crawling results/i.test(blob);
  return crawled && !sqlmapRanInjectionTests(blob);
}

/** True when sqlmap exited without testing an injectable parameter. */
export function isSqlmapInconclusive(result: unknown): boolean {
  const obj = asObj(result);
  if (obj.vulnerable === true) return false;
  return sqlmapNoInjectionSurface(result);
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
    // Nikto wrappers often put banner/metadata lines in `issues`; count OSVDB-style hits.
    const realIssues = issues.filter((line) => {
      const s = String(line);
      return (
        /\[\d{5,}\]/.test(s) ||
        /OSVDB/i.test(s) ||
        /Retrieved .+ header/i.test(s) ||
        /\+ ERROR:/i.test(s)
      );
    });
    const timedOut = /maximum execution time/i.test(blob);
    if (realIssues.length && !blob.includes("unknown option")) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: [
          `Reported ${realIssues.length} possible web issue(s).`,
          ...(timedOut ? ["Scan stopped early (time limit)."] : []),
        ],
        possibleIssues: realIssues.length,
      };
    }
    if (timedOut) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: ["Scan stopped early (time limit) with no clear findings."],
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
    if (sqlmapReachabilityFailure(result)) {
      return reachabilityFail(result, tool);
    }
    const noSurface = sqlmapNoInjectionSurface(result);
    const wafBlocked = obj.waf_blocked === true;
    const note = typeof obj.note === "string" ? obj.note.trim() : "";
    if (noSurface || wafBlocked || obj.partial === true) {
      const crawlOnly =
        /searching for links with depth/i.test(textBlob(result)) &&
        !sqlmapRanInjectionTests(textBlob(result));
      const bullets = [
        note ||
          (crawlOnly
            ? "Crawler finished but sqlmap never reached an injectable parameter — SQLi check inconclusive."
            : noSurface
              ? "No injectable parameters or forms found — SQLi check inconclusive."
              : "SQL injection scan finished without a testable injection point."),
        wafBlocked
          ? "Target may be WAF/CDN blocked; enable proxy/evasion and crawl deeper."
          : "Try katana/ffuf to discover parameterized endpoints before re-running sqlmap.",
      ];
      return {
        title: titleFor(tool),
        status: "partial",
        bullets,
      };
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
      const timedOut =
        obj.partial === true ||
        (typeof obj.error === "string" && /timed out/i.test(obj.error));
      return {
        title: titleFor(tool),
        status: timedOut ? "partial" : "ok",
        bullets: timedOut
          ? [
              `Found ${findings.length} template match(es) before the time limit.`,
              "Scan stopped early (time limit).",
            ]
          : [`Found ${findings.length} template match(es).`],
        confirmedVulns: findings.length,
        possibleIssues: findings.length,
      };
    }
    if (isProxyReachabilityFailure(result)) {
      return reachabilityFail(result, tool);
    }
    if (typeof obj.error === "string" && /timed out/i.test(obj.error)) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: ["Vulnerability template scan stopped at the time limit."],
      };
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
      bullets: [
        "No vulnerability template matches found.",
        "An empty result does not prove the target is clean — WAF/CDN challenges can block template output.",
      ],
    };
  }

  if (tool === "ffuf") {
    const results = Array.isArray(obj.results) ? obj.results : [];
    if (results.length > 0) {
      const timedOut = obj.timed_out === true || /maximum running time/i.test(blob);
      return {
        title: titleFor(tool),
        status: timedOut ? "partial" : "ok",
        bullets: timedOut
          ? [
              `Found ${results.length} interesting path(s) before the time limit.`,
              "Rerun with a smaller wordlist or higher rate for full coverage.",
            ]
          : [`Found ${results.length} interesting path(s).`],
      };
    }
    if (obj.stalled === true || /stalled under CDN/i.test(blob)) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: [
          "Web fuzzing stalled under CDN/WAF rate limits.",
          "Directory results from gobuster are still usable.",
        ],
      };
    }
    if (
      obj.timed_out === true ||
      obj.partial === true ||
      /maximum running time/i.test(blob)
    ) {
      const prog = blob.match(/progress:\s*\[(\d+)\/(\d+)\]/i);
      const done = prog ? parseInt(prog[1], 10) : 0;
      return {
        title: titleFor(tool),
        status: "partial",
        bullets:
          done > 0
            ? [
                "Web fuzzing hit the time limit with partial progress.",
                "Rerun with a smaller wordlist or higher rate for full coverage.",
              ]
            : ["Web fuzzing stopped at the time limit with no parsed paths."],
      };
    }
    if (
      isProxyReachabilityFailure(result) ||
      /\b(unable to connect|couldn't connect|connection refused)\b/i.test(blob)
    ) {
      return reachabilityFail(result, tool);
    }
  }

  if (tool === "xsstrike") {
    if (
      blob.includes("unable to connect") ||
      blob.includes("invalid literal for int") ||
      (typeof obj.error === "string" && obj.error.toLowerCase().includes("failed to connect")) ||
      isProxyReachabilityFailure(result)
    ) {
      return reachabilityFail(result, tool);
    }
    const findings = Array.isArray(obj.findings) ? obj.findings : [];
    const realFindings = findings.filter((line) => {
      const s = String(line);
      return /Payload:|Vulnerable/i.test(s) && !/Unable to connect/i.test(s);
    });
    if (realFindings.length) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: ["XSS check reported possible issues."],
        possibleIssues: 1,
      };
    }
    const reflections = findings.some((line) => /Reflections found:\s*[1-9]/i.test(String(line)));
    const waf = findings.find((line) => /WAF detected/i.test(String(line)));
    if (reflections || waf || /No vectors were crafted/i.test(blob)) {
      const bullets: string[] = [];
      if (waf) bullets.push(String(waf).replace(/^\[[^\]]+\]\s*/, ""));
      if (reflections) bullets.push("Parameter reflection seen; no exploitable vector crafted.");
      else if (/No vectors were crafted/i.test(blob)) {
        bullets.push("No exploitable XSS vectors crafted.");
      }
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: bullets.length ? bullets : ["XSS check finished with no confirmed vector."],
      };
    }
  }

  if (tool === "whatweb" || tool === "gobuster") {
    if (isProxyReachabilityFailure(result)) {
      return reachabilityFail(result, tool);
    }
    if (tool === "whatweb" && blob.includes("ssl")) {
      return reachabilityFail(result, tool);
    }
    if (tool === "gobuster" && typeof obj.error === "string") {
      return reachabilityFail(result, tool);
    }
    if (tool === "whatweb") {
      const raw = stripAnsi(typeof obj.raw_output === "string" ? obj.raw_output : blob);
      const techs = Array.isArray(obj.technologies) ? obj.technologies : [];
      const wafBlocked = obj.waf_blocked === true;
      const note = typeof obj.note === "string" ? obj.note.trim() : "";
      const httpStatus = typeof obj.http_status === "string" ? obj.http_status : "";
      const vendor =
        typeof obj.waf_vendor === "string" && obj.waf_vendor.trim()
          ? obj.waf_vendor.trim()
          : "WAF";
      const expired =
        obj.partial === true ||
        /ERROR Opening/i.test(raw) ||
        /execution expired/i.test(raw) ||
        /timed?\s*out/i.test(raw);

      if (wafBlocked) {
        const bullets = [
          `${vendor} challenge detected${httpStatus ? ` (${httpStatus})` : ""} — app fingerprint limited.`,
          techs.length > 0
            ? `Edge signals only: ${techs.slice(0, 3).join(", ")}.`
            : "Enable proxy/evasion for deeper stack detection.",
          note || "Downstream scans (nuclei, ffuf) may return empty until bypassed.",
        ];
        return {
          title: titleFor(tool),
          status: "partial",
          bullets,
        };
      }

      if (techs.length > 0) {
        return {
          title: titleFor(tool),
          status: expired ? "partial" : "ok",
          bullets: expired
            ? [
                `Partial fingerprint: ${techs.slice(0, 4).join(", ")}.`,
                "Scan stopped early (timeout).",
              ]
            : [`Stack signals: ${techs.slice(0, 4).join(", ")}.`],
        };
      }
      if (expired) {
        return {
          title: titleFor(tool),
          status: "partial",
          bullets: [
            "Website fingerprint hit a timeout before collecting stack signals.",
            "Later web checks (nuclei, ffuf) may still succeed.",
          ],
        };
      }
      const stack: string[] = [];
      if (/Microsoft-IIS/i.test(raw)) stack.push("Microsoft IIS");
      if (/ASP\.?NET/i.test(raw)) stack.push("ASP.NET");
      if (/Bootstrap/i.test(raw)) stack.push("Bootstrap");
      if (/JQuery/i.test(raw)) stack.push("jQuery");
      if (!stack.length && !raw.trim()) {
        return {
          title: titleFor(tool),
          status: "failed",
          bullets: ["Website fingerprint returned no data."],
        };
      }
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: stack.length
          ? [`Stack signals: ${stack.slice(0, 4).join(", ")}.`]
          : ["Website fingerprint collected."],
      };
    }
    if (tool === "gobuster") {
      const dirs = Array.isArray(obj.directories) ? obj.directories : [];
      const timeoutHeavy =
        (blob.match(/context deadline exceeded/gi) || []).length >= 5 ||
        (blob.match(/Client\.Timeout exceeded/gi) || []).length >= 5;
      if (dirs.length === 0 && timeoutHeavy) {
        return {
          title: titleFor(tool),
          status: "partial",
          bullets: [
            "Directory scan hit many timeouts (often HTTP hijack or rate limits).",
            "Prefer HTTPS www targets; empty result is not proof nothing exists.",
          ],
        };
      }
      if (dirs.length === 0) {
        return {
          title: titleFor(tool),
          status: "ok",
          bullets: ["No interesting directories reported from the wordlist."],
        };
      }
      // Discovered paths are recon signal, not a vulnerability — keep status ok
      // even when proxy fell back to direct.
      return {
        title: titleFor(tool),
        status: "ok",
        bullets: [`Found ${dirs.length} path(s).`],
      };
    }
  }

  if (typeof obj.error === "string" && obj.error.trim()) {
    if (tool === "phase" && obj.partial === true) {
      return {
        title: titleFor(tool),
        status: "partial",
        bullets: [
          "This phase hit the orchestrator time limit.",
          "Individual tool results below may still be usable.",
        ],
      };
    }
    if (isProxyReachabilityFailure(result)) return reachabilityFail(result, tool);
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["This check did not finish successfully."],
    };
  }

  if (isProxyReachabilityFailure(result)) {
    return reachabilityFail(result, tool);
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
      status: "partial",
      bullets: ["Login guessing stopped at the time limit; no credentials found."],
    };
  }
  if (typeof obj.error === "string" && obj.error.trim()) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Credential check did not finish successfully."],
    };
  }
  const blob = textBlob(result);
  if (
    tool === "hydra" &&
    (/could not connect/i.test(blob) ||
      /socket error/i.test(blob) ||
      /disconnected/i.test(blob) ||
      /connection refused/i.test(blob))
  ) {
    return {
      title: titleFor(tool),
      status: "failed",
      bullets: ["Could not reach the login service (SSH/host closed the connection)."],
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

  if (code === "invalid_module" || /invalid module/i.test(typeof obj.error === "string" ? obj.error : "")) {
    return {
      title: titleFor("metasploit"),
      status: "failed",
      bullets: [
        module
          ? `Metasploit module not installed: ${module}.`
          : "Metasploit module not installed in this environment.",
        "Update Metasploit or pick a module that exists on the RPC worker.",
      ],
    };
  }

  if (code === "rpc_error" || (typeof obj.error === "string" && obj.error.trim())) {
    const err = typeof obj.error === "string" ? obj.error.trim() : "";
    const bullets =
      code === "rpc_error"
        ? err
          ? [`Exploitation service unavailable: ${err}.`]
          : ["Exploitation service unavailable."]
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
      `${failedTools} tool${failedTools === 1 ? "" : "s"} failed`,
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
