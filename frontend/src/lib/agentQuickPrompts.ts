/** Short one-tap prompts for the agent empty state. Target is supplied in the next message. */

export const AGENT_QUICK_PROMPTS: { label: string; prompt: string }[] = [
  {
    label: "Cerberus begin",
    prompt: "Cerberus begin",
  },
  {
    label: "Full red-team strike",
    prompt:
      "Plan and execute a full authorized red-team — recon, vuln hunt, and adaptive attack until confirmed findings.",
  },
  {
    label: "Database access hunt",
    prompt:
      "Get into the database. Rotate SQLi methods and invent new probes until data access is proven.",
  },
  {
    label: "Web surface assault",
    prompt:
      "Deep study the web surface (CDN-aware), then ffuf, nuclei, and sqlmap. Keep trying new tools on failure.",
  },
  {
    label: "OSINT + leak match",
    prompt:
      "Run OSINT only: theharvester, subfinder, gau, sherlock, katana, httpx, whatweb, darkweb, and breach_intel. Scrape public/hidden sources and report leak matches. Do not run vuln scans or exploitation.",
  },
];
