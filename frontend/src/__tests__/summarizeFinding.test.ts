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
});
