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

  it("explains proxy timeout for gobuster", () => {
    const s = summarizeFinding("gobuster", {
      tool: "gobuster",
      error: 'context deadline exceeded (Client.Timeout exceeded while awaiting headers)',
      proxy: { enabled: true, mode: "local_proxy" },
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/proxy|reach|timeout/);
  });

  it("says sqlmap found no injection", () => {
    const s = summarizeFinding("sqlmap", {
      tool: "sqlmap",
      vulnerable: false,
      raw_output: "can't establish SSL connection",
    });
    expect(s.status).toBe("failed");
    expect(s.bullets.join(" ").toLowerCase()).toMatch(/couldn|reach|proxy|ssl|connect/);
  });

  it("handles empty nuclei findings as no issues", () => {
    const s = summarizeFinding("nuclei", {
      tool: "nuclei",
      findings: [],
      raw_output: "",
      proxy: { enabled: true },
    });
    expect(["ok", "failed"]).toContain(s.status);
    expect(s.bullets.length).toBeGreaterThan(0);
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

  it("summarizes metasploit with no impact proof", () => {
    const s = summarizeFinding("metasploit", {
      module: "exploit/multi/http/apache_path_traversal",
      sessions: [],
    });
    expect(s.status).toBe("partial");
    expect(s.bullets.join(" ")).toMatch(/could not prove impact/i);
  });

  it("summarizes metasploit hashdump post module", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/gather/hashdump",
      sessions: [{ id: "42", type: "meterpreter" }],
      vulnerable: true,
    });
    expect(s.bullets.join(" ")).toMatch(/credential|hash/i);
  });

  it("summarizes metasploit persistence post module", () => {
    const s = summarizeFinding("metasploit", {
      module: "post/windows/manage/persistence_exe",
      sessions: [{ id: "42", type: "meterpreter" }],
      vulnerable: true,
    });
    expect(s.bullets.join(" ")).toMatch(/persistence/i);
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
          sessions: [{ id: "42", type: "meterpreter" }],
          vulnerable: true,
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
    expect(m.postExSucceeded).toBe(1);
    expect(m.postExFailed).toBe(1);
    expect(m.sentence.toLowerCase()).toMatch(/session|impact|access/);
  });
});
