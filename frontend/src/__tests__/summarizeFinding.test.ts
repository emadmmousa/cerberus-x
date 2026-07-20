import { describe, it, expect } from "vitest";
import {
  summarizeFinding,
  summarizeMission,
  stripAnsi,
  PHASE_LABELS,
} from "../lib/summarizeFinding";
import type { ResultRow } from "../api/client";

describe("stripAnsi", () => {
  it("removes ansi color codes", () => {
    expect(stripAnsi("\u001b[1m\u001b[31mERROR\u001b[0m hi")).toBe("ERROR hi");
  });
});

describe("PHASE_LABELS", () => {
  it("maps phase keys to friendly names", () => {
    expect(PHASE_LABELS.recon).toBe("Reconnaissance");
    expect(PHASE_LABELS.vulnerability_scan).toBe("Vulnerability checks");
    expect(PHASE_LABELS.proof_of_impact).toBe("Proof of impact");
    expect(PHASE_LABELS.access_gained).toBe("Access gained");
    expect(PHASE_LABELS.post_exploitation).toBe("Post-exploitation");
  });
});

describe("summarizeFinding", () => {
  it("lists open ports for nmap", () => {
    const s = summarizeFinding("nmap", {
      tool: "nmap",
      ports: [
        { port: "80", state: "open" },
        { port: "443", state: "open" },
      ],
    });
    expect(s.status).toBe("ok");
    expect(s.title).toMatch(/port scan/i);
    expect(s.bullets.some((b) => b.includes("80") && b.includes("443"))).toBe(
      true,
    );
  });

  it("reports no open ports", () => {
    const s = summarizeFinding("masscan", { tool: "masscan", ports: [] });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ")).toMatch(/no open ports/i);
  });

  it("marks nmap filtered empty results as partial", () => {
    const s = summarizeFinding("nmap", {
      tool: "nmap",
      ports: [],
      raw_output:
        "All 65535 scanned ports on takwene.com are in ignored states.\nNot shown: 65535 filtered tcp ports (no-response)",
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/filtered|confirm/);
    expect(s.bullets.join(" ").toLowerCase()).not.toMatch(/no open ports found/);
  });

  it("explains proxy timeout for gobuster", () => {
    const s = summarizeFinding("gobuster", {
      tool: "gobuster",
      error: 'context deadline exceeded (Client.Timeout exceeded while awaiting headers)',
      proxy: {
        enabled: true,
        mode: "local_proxy",
        note: "oxylabs upstream unreachable: TimeoutError",
      },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/proxy|reach|timeout/);
  });

  it("does not blame the proxy when proxy is only enabled metadata", () => {
    const s = summarizeFinding("nuclei", {
      tool: "nuclei",
      findings: [],
      raw_output: "",
      proxy: { enabled: true, protocol: "http" },
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/no vulnerability/);
    expect(s.bullets.join(" ").toLowerCase()).not.toMatch(/proxy/);
  });

  it("uses a connection message for ssl failures without a proxy note", () => {
    const s = summarizeFinding("sqlmap", {
      tool: "sqlmap",
      vulnerable: false,
      raw_output: "can't establish SSL connection",
      proxy: { enabled: true, protocol: "http" },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/secure connection|ssl|connect/);
    expect(s.bullets.join(" ")).not.toBe("Couldn't reach the site through the proxy.");
  });

  it("keeps nikto option failures distinct from proxy failures", () => {
    const s = summarizeFinding("nikto", {
      tool: "nikto",
      issues: ["+ requires a value"],
      raw_output: "Unknown option: header\n-Help",
      proxy: {
        enabled: true,
        note: "oxylabs upstream unreachable: TimeoutError",
      },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/didn.?t run|incorrectly/);
    expect(s.bullets.join(" ").toLowerCase()).not.toMatch(/proxy/);
  });

  it("handles empty nuclei findings as no issues", () => {
    const s = summarizeFinding("nuclei", {
      tool: "nuclei",
      findings: [],
      raw_output: "scan completed",
      proxy: { enabled: true },
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/no vulnerability/);
  });
  it("detects nikto help-text failure", () => {
    const s = summarizeFinding("nikto", {
      tool: "nikto",
      issues: ["+ requires a value"],
      raw_output: "Unknown option: header\n-Help",
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/didn.?t run|incorrectly|failed/);
  });

  it("counts only real nikto findings, not banner lines", () => {
    const s = summarizeFinding("nikto", {
      tool: "nikto",
      issues: [
        "+ Target IP:          1.2.3.4",
        "+ Server: Microsoft-IIS/10.0",
        "+ [999986] /: Retrieved x-powered-by header: ASP.NET.",
        "+ ERROR: Host maximum execution time of 60 seconds reached",
      ],
      raw_output: "ERROR: Host maximum execution time of 60 seconds reached",
    });
    expect(s.status).toBe("partial");
    expect(s.possibleIssues).toBe(2);
    expect(s.bullets.join(" ")).toMatch(/2 possible|time limit/i);
  });

  it("surfaces whatweb stack instead of empty ok", () => {
    const s = summarizeFinding("whatweb", {
      tool: "whatweb",
      raw_output: "https://www.example.com [200 OK] ASP_NET, Microsoft-IIS/10.0, Bootstrap",
      proxy: { enabled: false, mode: "direct_fallback", note: "oxylabs upstream unreachable: TimeoutError" },
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ")).toMatch(/IIS|ASP\.NET/i);
  });

  it("marks whatweb execution expired as failed", () => {
    const s = summarizeFinding("whatweb", {
      tool: "whatweb",
      raw_output: "ERROR Opening: https://www.takwene.com - execution expired",
      proxy: { enabled: false, mode: "direct_fallback" },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/timed out/);
  });

  it("marks hydra ssh disconnect as failed", () => {
    const s = summarizeFinding("hydra", {
      tool: "hydra",
      credentials: [],
      raw_output: "[ERROR] could not connect to ssh://34.72.42.51:22 - Socket error: disconnected",
      proxy: { enabled: true, mode: "local_proxy" },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/could not reach|ssh/);
  });

  it("marks gobuster empty+timeouts as partial", () => {
    const s = summarizeFinding("gobuster", {
      tool: "gobuster",
      directories: [],
      raw_output: "context deadline exceeded\n".repeat(6),
      proxy: { enabled: false, mode: "direct_fallback" },
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/timeout/);
  });

  it("reports xsstrike connect failure without calling it a timeout", () => {
    const s = summarizeFinding("xsstrike", {
      tool: "xsstrike",
      findings: ["Unable to connect to the target."],
      raw_output: "[!!] Unable to connect to the target.\nValueError: invalid literal for int()",
      error: "xsstrike failed to connect or crashed while probing the target",
      proxy: {
        enabled: false,
        mode: "direct_fallback",
        note: "oxylabs upstream unreachable: TimeoutError",
      },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/connect/);
    expect(s.bullets.join(" ").toLowerCase()).not.toMatch(/timed out/);
  });

  it("summarizes successful xsstrike reflection without vector", () => {
    const s = summarizeFinding("xsstrike", {
      tool: "xsstrike",
      findings: [
        "[-] WAF detected: ASP.NET RequestValidationMode (Microsoft)",
        "[!] Reflections found: 1",
        "[-] No vectors were crafted.",
      ],
      raw_output: "WAF detected\nReflections found: 1\nNo vectors were crafted.",
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ")).toMatch(/ASP\.NET|reflection|vector/i);
  });

  it("counts theHarvester hosts and ignores banner email", () => {
    const s = summarizeFinding("theHarvester", {
      tool: "theHarvester",
      emails: ["cmartorella@edge-security.com"],
      hosts: ["a.example.com", "b.example.com"],
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ")).toMatch(/2 related hostname/i);
    expect(s.bullets.join(" ")).not.toMatch(/cmartorella/i);
  });

  it("does not count the target hostname as related intel", () => {
    const s = summarizeFinding("theHarvester", {
      tool: "theHarvester",
      target: "takwene.com",
      emails: ["cmartorella@edge-security.com"],
      hosts: ["takwene.com"],
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/no public hostnames|no public/);
    expect(s.bullets.join(" ")).not.toMatch(/related hostname/i);
  });

  it("does not blame proxy after direct_fallback", () => {
    const s = summarizeFinding("ffuf", {
      tool: "ffuf",
      results: [{ url: "https://example.com/admin", status: 200 }],
      proxy: {
        enabled: false,
        requested: true,
        mode: "direct_fallback",
        note: "oxylabs upstream unreachable: TimeoutError; fell back to direct",
      },
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ").toLowerCase()).not.toMatch(/proxy/);
  });

  it("marks john skipped", () => {
    const s = summarizeFinding("john", {
      tool: "john",
      skipped: true,
      raw_output: "No local hash file provided; john was skipped",
    });
    expect(s.status).toBe("skipped");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/skip|hash/);
  });

  it("falls back for unknown tools without dumping json", () => {
    const s = summarizeFinding("obscuretool", { foo: 1, bar: { nested: true } });
    expect(s.bullets.join(" ")).not.toMatch(/"foo"/);
    expect(s.bullets.length).toBeGreaterThan(0);
  });

  it("summarizes metasploit session success", () => {
    const s = summarizeFinding("metasploit", {
      module: "exploit/multi/http/apache_path_traversal",
      sessions: [{ id: "42", type: "meterpreter" }],
      vulnerable: true,
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.some((b) => /session|access/i.test(b))).toBe(true);
  });

  it("summarizes metasploit rpc failure", () => {
    const s = summarizeFinding("metasploit", {
      error: "connection refused",
      code: "rpc_error",
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ")).toMatch(/unavailable|could not|failed/i);
  });

  it("summarizes metasploit job timeout as failure", () => {
    const s = summarizeFinding("metasploit", {
      error: "Metasploit job timed out",
      code: "job_timeout",
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ")).toMatch(/timed out|could not|failed/i);
  });

  it("summarizes metasploit with no impact proof", () => {
    const s = summarizeFinding("metasploit", {
      module: "exploit/multi/http/apache_path_traversal",
      sessions: [],
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ")).toMatch(/could not prove impact/i);
  });

  it("summarizes metasploit hashdump post module as attempted", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/gather/hashdump",
      sessions: [],
      status: "attempted",
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ")).toMatch(/credential|hash|attempted/i);
  });

  it("summarizes metasploit persistence post module as attempted", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/manage/persistence_exe",
      sessions: [],
      status: "attempted",
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ")).toMatch(/persistence|attempted/i);
  });

  it("summarizes confirmed post module completion as ok", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/gather/hashdump",
      sessions: [],
      status: "completed",
    });
    expect(s.status).toBe("ok");
    expect(s.bullets.join(" ")).toMatch(/credential|hash/i);
  });

  it("does not treat a retained post session as post-ex success", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/gather/hashdump",
      sessions: [{ id: "42", type: "meterpreter" }],
    });
    expect(s.status).toBe("partial");
  });
});

describe("summarizeMission", () => {
  it("aggregates ports and failures", () => {
    const rows: ResultRow[] = [
      {
        target: "t.com",
        phase: "recon",
        tool: "nmap",
        timestamp: "1",
        result: { ports: [{ port: "80" }, { port: "443" }] },
      },
      {
        target: "t.com",
        phase: "recon",
        tool: "gobuster",
        timestamp: "2",
        result: { error: "context deadline exceeded", proxy: { enabled: true } },
      },
    ];
    const m = summarizeMission(rows, "RUNNING", "t.com");
    expect(m.openPorts).toEqual(expect.arrayContaining(["80", "443"]));
    expect(m.failedTools).toBe(1);
    expect(m.sentence.toLowerCase()).toMatch(/port|proxy|reach|fail/);
  });

  it("rolls up metasploit sessions and post-ex counts", () => {
    const rows: ResultRow[] = [
      {
        target: "t.com",
        phase: "proof_of_impact",
        tool: "metasploit",
        timestamp: "1",
        result: {
          module: "exploit/multi/http/apache_path_traversal",
          sessions: [{ id: "42", type: "meterpreter" }],
          vulnerable: true,
        },
      },
      {
        target: "t.com",
        phase: "post_exploitation",
        tool: "metasploit",
        timestamp: "2",
        result: {
          module: "post/windows/gather/hashdump",
          sessions: [],
          status: "attempted",
        },
      },
      {
        target: "t.com",
        phase: "post_exploitation",
        tool: "metasploit",
        timestamp: "3",
        result: {
          module: "post/windows/gather/credentials/mimikatz",
          error: "module failed",
          code: "rpc_error",
        },
      },
    ];
    const m = summarizeMission(rows, "SUCCESS", "t.com");
    expect(m.impactProven).toBe(true);
    expect(m.sessions).toBe(1);
    expect(m.postExSucceeded).toBe(0);
    expect(m.postExFailed).toBe(1);
    expect(m.sentence.toLowerCase()).toMatch(/session|impact|access/);
  });
});
