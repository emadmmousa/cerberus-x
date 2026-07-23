import { describe, expect, it } from "vitest";
import { formatResultBlockForCopy } from "../components/ResultCard";

describe("formatResultBlockForCopy", () => {
  it("includes summary bullets and technical json", () => {
    const text = formatResultBlockForCopy(
      {
        target: "example.com",
        phase: "recon",
        tool: "nmap",
        result: { open_ports: [443] },
        timestamp: "2026-07-22T10:00:00.000Z",
      },
      {
        title: "Port scan",
        status: "ok",
        bullets: ["443/tcp open", "1 port found"],
      },
      { open_ports: [443] },
    );

    expect(text).toContain("Port scan");
    expect(text).toContain("Status: Worked");
    expect(text).toContain("Tool: nmap");
    expect(text).toContain("- 443/tcp open");
    expect(text).toContain('"open_ports"');
  });

  it("uses custom badge label when provided", () => {
    const text = formatResultBlockForCopy(
      {
        target: "example.com",
        phase: "vuln",
        tool: "sqlmap",
        result: { partial: true },
        timestamp: 1,
      },
      {
        title: "SQL injection check",
        status: "partial",
        bullets: ["No injectable parameters found."],
      },
      { partial: true },
      "Inconclusive",
    );

    expect(text).toContain("Status: Inconclusive");
  });
});
