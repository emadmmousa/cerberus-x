import {
  BREACH_VAULT_PRODUCT,
  LEAK_RADAR_PRODUCT,
} from "./breachIntelBranding";
import type { OsintTargetKind } from "./osintTargets";

/** Curated aggressive mission prompts for the chat Strike Library. */

export type PromptCategory =
  | "full"
  | "web"
  | "darkweb"
  | "creds"
  | "ad"
  | "impact"
  | "adaptive"
  | "intel";

/** OSINT seed the operator supplies in the message after picking a deck. */
export type OsintTargetProfile = OsintTargetKind;

/** Host pentest vs person/domain OSINT profiles. */
export type TargetProfile = "host" | OsintTargetProfile;

export type LibraryMode = "all" | "host" | "osint";

export type AggressivePrompt = {
  id: string;
  codename: string;
  title: string;
  hook: string;
  category: PromptCategory;
  /** Primary target the operator sends in the follow-up message. */
  targetProfile: TargetProfile;
  tools: string[];
  posture: "aggressive";
  /** Message sent to the chat agent when the operator selects this card. */
  prompt: string;
  /** True when the mission must stay OSINT-only (no vuln/exploit tools). */
  osintOnly?: boolean;
};

export const PROMPT_CATEGORIES: {
  id: PromptCategory;
  label: string;
  blurb: string;
}[] = [
  { id: "full", label: "Full strike", blurb: "End-to-end authorized engagements" },
  { id: "adaptive", label: "Adaptive hunt", blurb: "Never stop until impact" },
  { id: "web", label: "Web assault", blurb: "Discovery → vuln → exploit" },
  { id: "darkweb", label: "Dark web", blurb: "Onion + leak OSINT" },
  { id: "intel", label: "Recon & OSINT", blurb: "Surface mapping" },
  { id: "impact", label: "Proof of impact", blurb: "SQLi, XSS, RCE" },
  { id: "creds", label: "Credentials", blurb: "Spray, crack, harvest" },
  { id: "ad", label: "AD & lateral", blurb: "SMB, BloodHound, relay" },
];

export const TARGET_PROFILE_CATEGORIES: {
  id: OsintTargetProfile;
  label: string;
  blurb: string;
}[] = [
  { id: "username", label: "Usernames", blurb: "Handles, @mentions, account IDs" },
  { id: "full_name", label: "Full name", blurb: "Person-centric intelligence" },
  { id: "email", label: "Email address", blurb: "Harvest, breach, exposure" },
  { id: "mobile", label: "Phone number", blurb: "Leak & mention correlation" },
  { id: "social_url", label: "Social media", blurb: "Profile URLs & platforms" },
  { id: "domain", label: "Domain names", blurb: "DNS, subs, archives, surface" },
];

export const LIBRARY_MODES: { id: LibraryMode; label: string; blurb: string }[] = [
  { id: "all", label: "All strikes", blurb: "Host pentest + OSINT decks" },
  { id: "host", label: "Host strikes", blurb: "Hostname, URL, infrastructure" },
  { id: "osint", label: "OSINT by target", blurb: "Username, email, domain, …" },
];

export const AGGRESSIVE_PROMPTS: AggressivePrompt[] = [
  {
    id: "osint-username",
    codename: "HANDLE TRACE",
    title: "Username OSINT sweep",
    hook: "Sherlock, archives, dark web + breach match on @handle.",
    category: "intel",
    targetProfile: "username",
    osintOnly: true,
    tools: ["sherlock", "gau", "darkweb", "breach_intel"],
    posture: "aggressive",
    prompt:
      "OSINT-only on an authorized username: sherlock for public profile scrape, gau for archived URLs, darkweb mention search, and breach_intel. Report handle exposure — no port scans or exploitation.",
  },
  {
    id: "osint-full-name",
    codename: "PERSON FILE",
    title: "Full-name intelligence",
    hook: "Dark web, breach DB, public harvest for a person.",
    category: "darkweb",
    targetProfile: "full_name",
    osintOnly: true,
    tools: ["darkweb", "breach_intel", "theharvester"],
    posture: "aggressive",
    prompt:
      "OSINT-only on an authorized full name (any language): darkweb --method full for underground mentions, breach_intel for credential exposure, theharvester for public footprint. No vuln scans or exploitation.",
  },
  {
    id: "osint-email",
    codename: "INBOX SHADOW",
    title: "Email exposure hunt",
    hook: "Harvest, breach vault, dark-web paste correlation.",
    category: "creds",
    targetProfile: "email",
    osintOnly: true,
    tools: ["theharvester", "breach_intel", "darkweb", "gau"],
    posture: "aggressive",
    prompt:
      `OSINT-only on an authorized email: theharvester, breach_intel (${BREACH_VAULT_PRODUCT}/${LEAK_RADAR_PRODUCT}), darkweb leak_hunt, and gau archive scrape. Report exposures only — no credential attacks.`,
  },
  {
    id: "osint-mobile",
    codename: "DIGIT GHOST",
    title: "Phone number leak hunt",
    hook: "Breach DB + underground mention correlation.",
    category: "darkweb",
    targetProfile: "mobile",
    osintOnly: true,
    tools: ["breach_intel", "darkweb"],
    posture: "aggressive",
    prompt:
      "OSINT-only on an authorized mobile number: breach_intel lookup and darkweb mention/paste search. Report matching leaks — no SMishing or exploitation.",
  },
  {
    id: "osint-social",
    codename: "PROFILE MIRROR",
    title: "Social profile recon",
    hook: "Live probe, tech stack, crawl linked surface from profile URL.",
    category: "intel",
    targetProfile: "social_url",
    osintOnly: true,
    tools: ["httpx", "whatweb", "katana", "sherlock"],
    posture: "aggressive",
    prompt:
      "OSINT-only on an authorized social profile URL: httpx and whatweb fingerprint, katana crawl for linked assets, sherlock for cross-platform handle hints. No exploitation.",
  },
  {
    id: "osint-domain",
    codename: "DOMAIN GLASS",
    title: "Domain surface map",
    hook: "Passive subs, DNS, archives, harvest, HTTP probe.",
    category: "intel",
    targetProfile: "domain",
    osintOnly: true,
    tools: ["subfinder", "amass", "dnsx", "gau", "httpx", "theharvester"],
    posture: "aggressive",
    prompt:
      "OSINT-only on an authorized domain: subfinder, amass, dnsx, gau, httpx, and theharvester. Map public attack surface — no port scanning or exploitation.",
  },
  {
    id: "full-arsenal",
    codename: "DARK ARSENAL",
    title: "Complete dark arsenal",
    hook: "All wrappers — recon through post-ex until findings.",
    category: "full",
    targetProfile: "host",
    tools: ["rustscan", "nuclei", "sqlmap", "metasploit", "darkweb"],
    posture: "aggressive",
    prompt:
      "Plan a full aggressive red-team using the complete dark arsenal (recon, dark web OSINT, discovery, vuln scan, creds, AD helpers, proof-of-impact). Don't stop until confirmed vulnerabilities.",
  },
  {
    id: "execute-until-vuln",
    codename: "NO MERCY",
    title: "Hunt until confirmed vulns",
    hook: "Adaptive rotation + novel tool invention on failure.",
    category: "adaptive",
    targetProfile: "host",
    tools: ["nuclei", "ffuf", "sqlmap", "xsstrike", "metasploit"],
    posture: "aggressive",
    prompt:
      "Execute adaptive attack — deep surface study, profile-matched tools, rotate through every allowlisted scanner, invent novel wrappers if standard tools fail. Hunt until confirmed findings.",
  },
  {
    id: "web-killchain",
    codename: "SILK ROAD",
    title: "Web kill chain",
    hook: "whatweb → ffuf/gobuster → nuclei → sqlmap → xsstrike.",
    category: "web",
    targetProfile: "host",
    tools: ["whatweb", "ffuf", "gobuster", "nuclei", "sqlmap", "xsstrike"],
    posture: "aggressive",
    prompt:
      "Design and execute an aggressive web kill chain: fingerprint stack, directory fuzz, nuclei CVE pass, then sqlmap and xsstrike for proof-of-impact.",
  },
  {
    id: "darkweb-full",
    codename: "BLACK MIRROR",
    title: "Dark web OSINT sweep",
    hook: "Onion search, leak hunt, paste monitor, Tor probes.",
    category: "darkweb",
    targetProfile: "full_name",
    osintOnly: true,
    tools: ["darkweb", "theharvester", "breach_intel"],
    posture: "aggressive",
    prompt:
      "Run OSINT only: darkweb --method full (onion search, leak hunt, breach correlate, forum/market mentions, Tor hidden-service probes), theharvester, and breach_intel. Scrape public/hidden sources and report leak matches. Do not run vuln scans or exploitation.",
  },
  {
    id: "darkweb-leaks",
    codename: "GHOST LEAK",
    title: "Leak & breach correlate",
    hook: "Credential dumps, paste sites, underground mentions.",
    category: "darkweb",
    targetProfile: "email",
    osintOnly: true,
    tools: ["darkweb", "breach_intel"],
    posture: "aggressive",
    prompt:
      `OSINT leak hunt — darkweb leak_hunt, paste_monitor, breach_correlate, credential_dump_search, plus breach_intel ${BREACH_VAULT_PRODUCT}/${LEAK_RADAR_PRODUCT} lookup. Report matching exposures only; no credential attacks.`,
  },
  {
    id: "osint-surface",
    codename: "GLASS HOUSE",
    title: "OSINT surface map",
    hook: "Public harvest, hidden-web scrape, breach DB match.",
    category: "intel",
    targetProfile: "domain",
    osintOnly: true,
    tools: [
      "theharvester",
      "subfinder",
      "gau",
      "sherlock",
      "katana",
      "httpx",
      "whatweb",
      "darkweb",
      "breach_intel",
    ],
    posture: "aggressive",
    prompt:
      `OSINT-only: run the full scrape stack — theharvester, subfinder, gau, sherlock, katana, httpx, whatweb, darkweb, and breach_intel (${BREACH_VAULT_PRODUCT}/${LEAK_RADAR_PRODUCT}). Produce an intelligence report — no port scans or exploitation.`,
  },
  {
    id: "cve-strike",
    codename: "ZERO DAY",
    title: "CVE & KEV strike",
    hook: "nuclei critical/high + metasploit module chain.",
    category: "impact",
    targetProfile: "host",
    tools: ["nuclei", "metasploit"],
    posture: "aggressive",
    prompt:
      "Aggressive CVE hunt: nuclei with critical/high/KEV/RCE tags, then chain matching metasploit modules for any confirmed CVE or open service ports.",
  },
  {
    id: "sqli-impact",
    codename: "SQL STORM",
    title: "SQLi proof-of-impact",
    hook: "BEUSTQ, forms crawl, level 5 / risk 3.",
    category: "impact",
    targetProfile: "host",
    tools: ["sqlmap"],
    posture: "aggressive",
    prompt:
      "Prove SQL injection impact: sqlmap with --technique=BEUSTQ, --forms, --crawl=3, --level=5, --risk=3 until DB access or clear negative.",
  },
  {
    id: "xss-strike",
    codename: "SCRIPT KIDDIE",
    title: "XSS assault",
    hook: "Reflected and stored probes on live params.",
    category: "impact",
    targetProfile: "host",
    tools: ["xsstrike", "ffuf"],
    posture: "aggressive",
    prompt:
      "Run aggressive XSS testing: ffuf for params/endpoints, then xsstrike on discovered inputs. Report exploitable reflected/stored cases.",
  },
  {
    id: "waf-bypass",
    codename: "SMOKE SCREEN",
    title: "WAF evasion assault",
    hook: "Aggressive evasion on ffuf, sqlmap, nuclei.",
    category: "web",
    targetProfile: "host",
    tools: ["ffuf", "sqlmap", "nuclei"],
    posture: "aggressive",
    prompt:
      "The target sits behind a WAF/CDN. Plan aggressive WAF evasion: slower httpx/curl probes, ffuf with -ac, sqlmap with tamper/evasion, nuclei misconfig tags — don't blind flood.",
  },
  {
    id: "api-assault",
    codename: "RESTLESS",
    title: "API & GraphQL assault",
    hook: "ffuf API paths, nuclei, sqlmap on JSON surfaces.",
    category: "web",
    targetProfile: "host",
    tools: ["ffuf", "nuclei", "sqlmap"],
    posture: "aggressive",
    prompt:
      "Aggressive API engagement: discover /api, /graphql, swagger paths with ffuf, nuclei API templates, sqlmap on JSON/REST parameters.",
  },
  {
    id: "wordpress",
    codename: "WP CRACK",
    title: "WordPress stack assault",
    hook: "WP nuclei templates, gobuster, sqlmap.",
    category: "web",
    targetProfile: "host",
    tools: ["nuclei", "gobuster", "sqlmap", "nikto"],
    posture: "aggressive",
    prompt:
      "WordPress (or CMS) assault: whatweb confirm, gobuster wp-content paths, nuclei WP/CVE templates, nikto, sqlmap on login/search forms.",
  },
  {
    id: "iis-aspnet",
    codename: "BLUE SCREEN",
    title: "IIS / ASP.NET assault",
    hook: "nikto, nuclei, sqlmap, metasploit for IIS stack.",
    category: "web",
    targetProfile: "host",
    tools: ["nikto", "nuclei", "sqlmap", "metasploit"],
    posture: "aggressive",
    prompt:
      "IIS/ASP.NET assault: nikto + nuclei IIS/CVE checks, sqlmap on forms, metasploit modules for observed services — push to proof-of-impact.",
  },
  {
    id: "cred-storm",
    codename: "BRUTE FORCE",
    title: "Credential storm",
    hook: "theharvester emails + hydra online brute.",
    category: "creds",
    targetProfile: "email",
    tools: ["theharvester", "hydra", "john"],
    posture: "aggressive",
    prompt:
      "Credential assault: theharvester for emails/users, hydra on SSH/HTTP login forms with rockyou-style wordlists, note hashes for john offline crack.",
  },
  {
    id: "ad-path",
    codename: "DOMAIN DOMINANCE",
    title: "AD path & takeover",
    hook: "crackmapexec, bloodhound, impacket secrets.",
    category: "ad",
    targetProfile: "host",
    tools: ["crackmapexec", "bloodhound", "impacket"],
    posture: "aggressive",
    prompt:
      "Active Directory assault: crackmapexec SMB enum/spray, bloodhound path collection, impacket secretsdump when creds exist — map path to DA.",
  },
  {
    id: "lateral-responder",
    codename: "POISON IVY",
    title: "LLMNR poison & lateral",
    hook: "responder relay + crackmapexec + metasploit.",
    category: "ad",
    targetProfile: "host",
    tools: ["responder", "crackmapexec", "metasploit"],
    posture: "aggressive",
    prompt:
      "Lateral movement plan for internal networks: responder LLMNR/NBT-NS capture, crackmapexec pass-the-hash spray, metasploit for relay/exploit modules on captured creds.",
  },
  {
    id: "postex-peas",
    codename: "ROOT KIT",
    title: "Post-ex privesc enum",
    hook: "linpeas / winpeas after initial access.",
    category: "impact",
    targetProfile: "host",
    tools: ["linpeas", "winpeas", "sliver"],
    posture: "aggressive",
    prompt:
      "We have shell access. Plan post-ex: linpeas or winpeas privesc enum, sliver C2 staging for persistence testing, recommend escalation paths.",
  },
  {
    id: "metasploit-chain",
    codename: "MSF CHAIN",
    title: "Metasploit exploit chain",
    hook: "Port/CVE mapped modules + payload strategy.",
    category: "impact",
    targetProfile: "host",
    tools: ["metasploit", "nmap"],
    posture: "aggressive",
    prompt:
      "Build metasploit exploit chain from nmap/nuclei findings: pick full module paths, set payload/LHOST strategy, execute proof-of-impact modules only.",
  },
  {
    id: "fast-recon",
    codename: "LIGHTNING",
    title: "Lightning recon pass",
    hook: "rustscan + masscan + whatweb in parallel.",
    category: "intel",
    targetProfile: "host",
    tools: ["rustscan", "masscan", "whatweb"],
    posture: "aggressive",
    prompt:
      "Fast aggressive recon: parallel rustscan, masscan bounded ports, whatweb -a 3. Summarize open services and recommend the single best next strike.",
  },
  {
    id: "invent-tools",
    codename: "FORGE",
    title: "Invent novel wrappers",
    hook: "When arsenal fails, forge custom curl/ffuf probes.",
    category: "adaptive",
    targetProfile: "host",
    tools: ["curl", "ffuf", "custom"],
    posture: "aggressive",
    prompt:
      "Adaptive engagement: if standard tools fail, invent novel firebreak-tool wrappers (real binaries, creative args) and register them in the mission plan.",
  },
];

export function promptsByCategory(category: PromptCategory | "all"): AggressivePrompt[] {
  if (category === "all") return AGGRESSIVE_PROMPTS;
  return AGGRESSIVE_PROMPTS.filter((p) => p.category === category);
}

export function promptsByTargetProfile(profile: OsintTargetProfile | "all"): AggressivePrompt[] {
  if (profile === "all") {
    return AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile !== "host");
  }
  return AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile === profile);
}

export function promptsByLibraryMode(mode: LibraryMode): AggressivePrompt[] {
  if (mode === "all") return AGGRESSIVE_PROMPTS;
  if (mode === "host") return AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile === "host");
  return AGGRESSIVE_PROMPTS.filter((p) => p.targetProfile !== "host");
}

export function targetProfileLabel(profile: TargetProfile): string {
  if (profile === "host") return "Host";
  return TARGET_PROFILE_CATEGORIES.find((row) => row.id === profile)?.label ?? profile;
}
