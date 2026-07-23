"""Builtin cyber-security scaffold catalog for the AI Lab marketplace.

Each entry is an OpenAI-compatible recipe (model routing target). Wire live
endpoints via env, Pro marketplace registration, or dedicated Modelfiles.
"""

from __future__ import annotations

import os
from typing import Any

# Display order for AI Lab grouping.
SCAFFOLD_CATEGORIES: tuple[str, ...] = (
    "Core platform",
    "Reconnaissance & OSINT",
    "Network & infrastructure",
    "Web application security",
    "Vulnerability assessment",
    "Exploitation & offensive",
    "Post-exploitation & lateral movement",
    "Cloud & container security",
    "Identity & access",
    "Defensive & blue team",
    "Threat intelligence",
    "Malware & reverse engineering",
    "Mobile, IoT & embedded",
    "Wireless & physical",
    "Compliance & GRC",
    "ICS / OT",
    "AI / ML security",
    "Cryptography & PKI",
    "Forensics & incident response",
    "Purple team & orchestration",
    "Commercial LLM providers",
)


def _entry(
    id: str,
    label: str,
    *,
    category: str,
    tasks: list[str] | None = None,
    model: str | None = None,
    base_url_hint: str = "http://ollama:11434/v1",
    license: str = "Apache-2.0",
    notes: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": id,
        "label": label,
        "kind": "openai_compatible",
        "model": model or f"firebreak-{id}",
        "base_url_hint": base_url_hint,
        "tasks": tasks or ["plan", "decide"],
        "license": license,
        "source": "builtin",
        "category": category,
    }
    if notes:
        row["notes"] = notes
    return row


def _cyber_scaffolds() -> list[dict[str, Any]]:
    ollama = "http://ollama:11434/v1"
    openai = "https://api.openai.com/v1"
    anthropic = "https://api.anthropic.com/v1"
    groq = "https://api.groq.com/openai/v1"
    together = "https://api.together.xyz/v1"
    openrouter = "https://openrouter.ai/api/v1"

    return [
        # --- Reconnaissance & OSINT ---
        _entry("osint-collector", "OSINT collector", category="Reconnaissance & OSINT", tasks=["plan", "recon", "summarize"], notes="Harvest public intel, breaches, and org footprint."),
        _entry("subdomain-enum", "Subdomain enumerator", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Amass, subfinder, crt.sh style enumeration."),
        _entry("dns-recon", "DNS recon specialist", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Zone transfers, DNSSEC, SPF/DMARC, dangling records."),
        _entry("passive-recon", "Passive recon analyst", category="Reconnaissance & OSINT", tasks=["plan", "recon", "decide"], notes="Non-intrusive footprinting only."),
        _entry("active-recon", "Active recon operator", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Probes, banners, and live service discovery."),
        _entry("social-engineering", "Social engineering planner", category="Reconnaissance & OSINT", tasks=["plan", "decide"], notes="Phishing pretexts and vishing scripts for authorized tests."),
        _entry("metadata-harvest", "Metadata harvester", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="EXIF, PDF, and document metadata leaks."),
        _entry("google-dorking", "Search dork specialist", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Operator queries and exposed asset discovery."),
        _entry("breach-intel", "Breach intelligence analyst", category="Reconnaissance & OSINT", tasks=["plan", "recon", "summarize"], notes="Credential exposure and paste-site correlation."),
        _entry("brand-monitor", "Brand abuse monitor", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Typosquatting, fake apps, and impersonation."),
        _entry("supply-chain-osint", "Supply-chain OSINT", category="Reconnaissance & OSINT", tasks=["plan", "recon"], notes="Vendor exposure and third-party attack surface."),
        # --- Network & infrastructure ---
        _entry("network-mapper", "Network mapper", category="Network & infrastructure", tasks=["plan", "recon"], notes="Topology, routing, and path discovery."),
        _entry("port-scan", "Port scan operator", category="Network & infrastructure", tasks=["plan", "recon"], notes="Masscan, nmap, and service discovery."),
        _entry("service-fingerprint", "Service fingerprinter", category="Network & infrastructure", tasks=["plan", "recon", "decide"], notes="Banner grab, version ID, and tech stack."),
        _entry("firewall-evasion", "Firewall evasion planner", category="Network & infrastructure", tasks=["plan", "decide"], notes="Fragmentation, timing, and proxy pivot tactics."),
        _entry("vpn-tunnel", "VPN / tunnel analyst", category="Network & infrastructure", tasks=["plan", "decide"], notes="IPsec, WireGuard, SSL VPN misconfigs."),
        _entry("network-segmentation", "Segmentation reviewer", category="Network & infrastructure", tasks=["plan", "harden"], notes="East-west paths and flat network risks."),
        _entry("bgp-routing", "BGP / routing security", category="Network & infrastructure", tasks=["plan", "harden"], notes="Route leaks, RPKI, and anycast issues."),
        _entry("ddos-resilience", "DDoS resilience analyst", category="Network & infrastructure", tasks=["plan", "harden"], notes="Rate limits, scrubbing, and capacity planning."),
        _entry("proxy-pivot", "Proxy pivot operator", category="Network & infrastructure", tasks=["plan", "decide"], notes="Residential, rotating, and geo proxy strategy."),
        # --- Web application security ---
        _entry("web-crawler", "Web crawler / surface mapper", category="Web application security", tasks=["plan", "recon"], notes="Katana, gospider, and link discovery."),
        _entry("api-security", "API security specialist", category="Web application security", tasks=["plan", "decide"], notes="REST, GraphQL, and gRPC abuse."),
        _entry("graphql-security", "GraphQL security", category="Web application security", tasks=["plan", "decide"], notes="Introspection, batching, and IDOR via queries."),
        _entry("jwt-abuse", "JWT / token abuse analyst", category="Web application security", tasks=["plan", "decide"], notes="Alg none, key confusion, and weak signing."),
        _entry("ssrf-specialist", "SSRF specialist", category="Web application security", tasks=["plan", "decide"], notes="Cloud metadata and internal pivot chains."),
        _entry("xss-hunter", "XSS hunter", category="Web application security", tasks=["plan", "decide"], notes="Reflected, stored, DOM, and CSP bypass."),
        _entry("csrf-analyst", "CSRF analyst", category="Web application security", tasks=["plan", "decide"], notes="Token gaps and cross-origin write primitives."),
        _entry("ssti-detector", "SSTI detector", category="Web application security", tasks=["plan", "decide"], notes="Template injection across Jinja, Twig, Freemarker."),
        _entry("file-upload", "File upload abuse", category="Web application security", tasks=["plan", "decide"], notes="Polyglots, path traversal, and MIME bypass."),
        _entry("business-logic", "Business logic tester", category="Web application security", tasks=["plan", "decide"], notes="Workflow abuse, race conditions, and price tampering."),
        _entry("websocket-security", "WebSocket security", category="Web application security", tasks=["plan", "decide"], notes="Origin checks, auth on upgrade, and message tampering."),
        _entry("cms-scanner", "CMS scanner", category="Web application security", tasks=["plan", "recon", "decide"], notes="WordPress, Drupal, Joomla plugin CVEs."),
        _entry("oauth-web", "OAuth / OIDC web flows", category="Web application security", tasks=["plan", "decide"], notes="Redirect URI, PKCE, and state fixation."),
        _entry("cors-analyst", "CORS misconfiguration analyst", category="Web application security", tasks=["plan", "decide"], notes="Reflective origins and credentialed reads."),
        # --- Vulnerability assessment ---
        _entry("nuclei-runner", "Nuclei template operator", category="Vulnerability assessment", tasks=["plan", "decide"], notes="Template selection and severity triage."),
        _entry("cve-matcher", "CVE matcher", category="Vulnerability assessment", tasks=["plan", "decide", "summarize"], notes="Version-to-CVE mapping and exploitability."),
        _entry("dependency-scan", "Dependency / SCA analyst", category="Vulnerability assessment", tasks=["plan", "harden"], notes="SBOM, transitive deps, and known vulns."),
        _entry("misconfig-finder", "Misconfiguration finder", category="Vulnerability assessment", tasks=["plan", "decide", "harden"], notes="Cloud and app config drift."),
        _entry("ssl-tls-audit", "SSL/TLS auditor", category="Vulnerability assessment", tasks=["plan", "harden"], notes="Cipher suites, cert chains, and HSTS."),
        _entry("header-hardening", "Security header analyst", category="Vulnerability assessment", tasks=["plan", "harden"], notes="CSP, X-Frame, and cookie flags."),
        _entry("baseline-scanner", "CIS / baseline scanner", category="Vulnerability assessment", tasks=["plan", "harden"], notes="Benchmark checks and hardening gaps."),
        _entry("attack-surface", "Attack surface quantifier", category="Vulnerability assessment", tasks=["plan", "recon", "summarize"], notes="Exposure scoring and prioritization."),
        # --- Exploitation & offensive ---
        _entry("exploit-dev", "Exploit development advisor", category="Exploitation & offensive", tasks=["plan", "decide"], notes="PoC shaping and weaponization guardrails."),
        _entry("metasploit-operator", "Metasploit operator", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Module selection and session handling."),
        _entry("payload-crafter", "Payload crafter", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Stagers, encoders, and evasion wrappers."),
        _entry("shell-stager", "Shell / stager operator", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Reverse shells, bind shells, and web shells."),
        _entry("privilege-escalation", "Privilege escalation", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Local privesc paths on Linux and Windows."),
        _entry("buffer-overflow", "Memory corruption advisor", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Stack/heap overflow and ROP planning."),
        _entry("deserialisation", "Deserialization exploit analyst", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Java, PHP, Python, .NET gadget chains."),
        _entry("race-condition", "Race condition hunter", category="Exploitation & offensive", tasks=["plan", "decide"], notes="TOCTOU and concurrency bugs."),
        _entry("sql-injection", "SQL injection specialist", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Sqlmap strategy, blind, and OOB exfil."),
        _entry("nosql-injection", "NoSQL injection specialist", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Mongo, Couch, and operator injection."),
        _entry("ldap-injection", "LDAP injection specialist", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Filter bypass and auth bypass."),
        _entry("command-injection", "Command injection specialist", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Shell metacharacters and argument injection."),
        _entry("xxe-exploit", "XXE exploit specialist", category="Exploitation & offensive", tasks=["plan", "decide"], notes="External entities and SSRF via XML."),
        _entry("smb-exploit", "SMB / Windows exploit path", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Eternal-family patterns and signing relay."),
        _entry("rce-validator", "RCE proof validator", category="Exploitation & offensive", tasks=["plan", "decide", "summarize"], notes="Safe impact proof and evidence capture."),
        # --- Post-exploitation ---
        _entry("lateral-movement", "Lateral movement planner", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Pivot paths, trust relationships, and hops."),
        _entry("persistence", "Persistence operator", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Scheduled tasks, services, and implants."),
        _entry("credential-dump", "Credential access analyst", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="LSASS, SAM, secrets dumps (authorized)."),
        _entry("pass-the-hash", "Pass-the-hash / ticket abuse", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="NTLM relay, PtH, and golden ticket patterns."),
        _entry("kerberoast", "Kerberoast / AD abuse", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="SPN abuse, AS-REP roast, and delegation."),
        _entry("bloodhound-analyst", "BloodHound path analyst", category="Post-exploitation & lateral movement", tasks=["plan", "decide", "summarize"], notes="ACL abuse and shortest path to DA."),
        _entry("data-exfil", "Data exfiltration planner", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Channels, staging, and DLP evasion awareness."),
        _entry("ransomware-sim", "Ransomware simulation", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Impact modeling without destructive payloads."),
        _entry("c2-operator", "C2 framework operator", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Beacon staging, malleable profiles, and OPSEC."),
        _entry("domain-dominance", "Domain dominance planner", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="DA objectives and cleanup planning."),
        # --- Cloud & container ---
        _entry("aws-security", "AWS security assessor", category="Cloud & container security", tasks=["plan", "decide", "harden"], notes="IAM, S3, Lambda, and metadata paths."),
        _entry("azure-security", "Azure security assessor", category="Cloud & container security", tasks=["plan", "decide", "harden"], notes="Entra ID, storage, and ARM misconfigs."),
        _entry("gcp-security", "GCP security assessor", category="Cloud & container security", tasks=["plan", "decide", "harden"], notes="GCS, IAM bindings, and workload identity."),
        _entry("kubernetes-security", "Kubernetes security", category="Cloud & container security", tasks=["plan", "decide", "harden"], notes="RBAC, secrets, and privileged pods."),
        _entry("docker-security", "Container / Docker security", category="Cloud & container security", tasks=["plan", "harden"], notes="Socket mounts, caps, and image vulns."),
        _entry("terraform-audit", "IaC / Terraform auditor", category="Cloud & container security", tasks=["plan", "harden"], notes="Static IaC misconfiguration review."),
        _entry("serverless-security", "Serverless security", category="Cloud & container security", tasks=["plan", "decide"], notes="Lambda, Cloud Functions event injection."),
        _entry("cloud-iam", "Cloud IAM analyst", category="Cloud & container security", tasks=["plan", "harden"], notes="Over-privileged roles and trust policies."),
        _entry("object-storage", "Object storage auditor", category="Cloud & container security", tasks=["plan", "harden"], notes="Public buckets and signed URL abuse."),
        # --- Identity & access ---
        _entry("ad-security", "Active Directory security", category="Identity & access", tasks=["plan", "decide", "harden"], notes="Tier model, GPO, and auth hardening."),
        _entry("oauth-oidc", "OAuth / OIDC identity flows", category="Identity & access", tasks=["plan", "decide"], notes="Token lifetimes, scopes, and federation."),
        _entry("mfa-bypass-analyst", "MFA bypass analyst", category="Identity & access", tasks=["plan", "decide"], notes="Fatigue, relay, and recovery abuse (authorized)."),
        _entry("password-spray", "Password spray planner", category="Identity & access", tasks=["plan", "decide"], notes="Lockout-aware spray and smart lock detection."),
        _entry("secrets-scanner", "Secrets scanner", category="Identity & access", tasks=["plan", "recon", "harden"], notes="API keys in repos, env files, and logs."),
        _entry("pki-identity", "PKI / certificate identity", category="Identity & access", tasks=["plan", "harden"], notes="Client cert auth and mis-issued certs."),
        # --- Defensive & blue team ---
        _entry("siem-analyst", "SIEM analyst", category="Defensive & blue team", tasks=["plan", "summarize", "harden"], notes="Detection queries and alert triage."),
        _entry("detection-engineer", "Detection engineer", category="Defensive & blue team", tasks=["plan", "harden"], notes="Sigma, YARA-L, and rule tuning."),
        _entry("threat-hunter", "Threat hunter", category="Defensive & blue team", tasks=["plan", "decide", "summarize"], notes="Hypothesis-driven hunts and baselines."),
        _entry("log-forensics", "Log forensics analyst", category="Defensive & blue team", tasks=["plan", "summarize"], notes="Correlation across auth, proxy, and EDR logs."),
        _entry("hardening-advisor", "Hardening advisor", category="Defensive & blue team", tasks=["plan", "harden"], notes="Actionable remediation and CIS mappings."),
        _entry("patch-prioritizer", "Patch prioritization", category="Defensive & blue team", tasks=["plan", "harden", "summarize"], notes="CVSS, KEV, and exposure-based ranking."),
        _entry("zero-trust", "Zero trust architect", category="Defensive & blue team", tasks=["plan", "harden"], notes="Micro-segmentation and continuous verification."),
        _entry("waf-tuning", "WAF tuning analyst", category="Defensive & blue team", tasks=["plan", "harden"], notes="False positives and bypass-resistant rules."),
        _entry("edr-response", "EDR response operator", category="Defensive & blue team", tasks=["plan", "summarize"], notes="Isolation, collection, and timeline."),
        # --- Threat intelligence ---
        _entry("ioc-analyst", "IOC analyst", category="Threat intelligence", tasks=["plan", "summarize"], notes="Indicators, enrichment, and decay."),
        _entry("malware-family", "Malware family analyst", category="Threat intelligence", tasks=["plan", "summarize"], notes="TTP mapping and family attribution."),
        _entry("apt-emulation", "APT emulation planner", category="Threat intelligence", tasks=["plan", "decide"], notes="MITRE-mapped adversary scenarios."),
        _entry("darkweb-monitor", "Dark web monitor", category="Threat intelligence", tasks=["plan", "recon", "summarize"], notes="Leak sites and actor chatter (legal sources)."),
        _entry("feed-correlator", "Threat feed correlator", category="Threat intelligence", tasks=["plan", "summarize"], notes="STIX/TAXII ingestion and dedup."),
        _entry("mitre-mapper", "MITRE ATT&CK mapper", category="Threat intelligence", tasks=["plan", "summarize"], notes="Technique coverage and gap analysis."),
        # --- Malware & RE ---
        _entry("malware-analyst", "Malware analyst", category="Malware & reverse engineering", tasks=["plan", "summarize"], notes="Static/dynamic triage and family ID."),
        _entry("reverse-engineer", "Reverse engineer", category="Malware & reverse engineering", tasks=["plan", "decide"], notes="Disassembly, decompilation, and patching."),
        _entry("sandbox-analyst", "Sandbox analyst", category="Malware & reverse engineering", tasks=["plan", "summarize"], notes="Behavioral analysis and C2 extraction."),
        _entry("yara-author", "YARA rule author", category="Malware & reverse engineering", tasks=["plan", "harden"], notes="Signature authoring and false-positive control."),
        _entry("packer-unpacker", "Packer / obfuscation analyst", category="Malware & reverse engineering", tasks=["plan", "decide"], notes="Unpacking and deobfuscation strategy."),
        # --- Mobile, IoT ---
        _entry("mobile-android", "Android security", category="Mobile, IoT & embedded", tasks=["plan", "decide"], notes="APK reversing, intents, and backup flags."),
        _entry("mobile-ios", "iOS security", category="Mobile, IoT & embedded", tasks=["plan", "decide"], notes="IPA analysis, keychain, and jailbreak checks."),
        _entry("iot-security", "IoT security assessor", category="Mobile, IoT & embedded", tasks=["plan", "decide"], notes="Default creds, UART, and cloud pairing."),
        _entry("firmware-analysis", "Firmware analyst", category="Mobile, IoT & embedded", tasks=["plan", "decide"], notes="Binwalk, squashfs, and hardcoded secrets."),
        _entry("embedded-arm", "Embedded / ARM analyst", category="Mobile, IoT & embedded", tasks=["plan", "decide"], notes="RTOS, JTAG, and debug interfaces."),
        # --- Wireless & physical ---
        _entry("wifi-audit", "Wi-Fi auditor", category="Wireless & physical", tasks=["plan", "decide"], notes="WPA2/3, evil twin, and rogue AP detection."),
        _entry("bluetooth-le", "Bluetooth / BLE security", category="Wireless & physical", tasks=["plan", "decide"], notes="Pairing, GATT, and replay."),
        _entry("rf-analysis", "RF / SDR analyst", category="Wireless & physical", tasks=["plan", "decide"], notes="Signal analysis and proprietary protocols."),
        _entry("physical-pentest", "Physical pentest planner", category="Wireless & physical", tasks=["plan", "decide"], notes="Badge cloning, tailgating, and lock bypass."),
        # --- Compliance ---
        _entry("pci-dss", "PCI-DSS assessor", category="Compliance & GRC", tasks=["plan", "harden", "summarize"], notes="Cardholder data scope and controls."),
        _entry("hipaa", "HIPAA security reviewer", category="Compliance & GRC", tasks=["plan", "harden"], notes="PHI safeguards and audit trails."),
        _entry("iso27001", "ISO 27001 advisor", category="Compliance & GRC", tasks=["plan", "harden"], notes="ISMS controls and evidence mapping."),
        _entry("gdpr-privacy", "GDPR / privacy reviewer", category="Compliance & GRC", tasks=["plan", "harden"], notes="Data minimization and breach notification."),
        _entry("soc2-audit", "SOC 2 control mapper", category="Compliance & GRC", tasks=["plan", "harden", "summarize"], notes="Trust criteria and test procedures."),
        _entry("nist-csf", "NIST CSF mapper", category="Compliance & GRC", tasks=["plan", "harden"], notes="Identify, protect, detect, respond, recover."),
        # --- ICS / OT ---
        _entry("plc-scada", "PLC / SCADA security", category="ICS / OT", tasks=["plan", "decide", "harden"], notes="Modbus, DNP3, and engineering workstations."),
        _entry("modbus-security", "Modbus / fieldbus analyst", category="ICS / OT", tasks=["plan", "decide"], notes="Plaintext protocols and safety interlocks."),
        _entry("ot-network", "OT network segmentation", category="ICS / OT", tasks=["plan", "harden"], notes="Purdue model and IT/OT boundaries."),
        _entry("safety-systems", "Safety instrumented systems", category="ICS / OT", tasks=["plan", "harden"], notes="Safety PLC and ESD review."),
        # --- AI / ML security ---
        _entry("llm-red-team", "LLM red team operator", category="AI / ML security", tasks=["plan", "decide"], notes="Jailbreaks, tool abuse, and guardrail evasion."),
        _entry("prompt-injection", "Prompt injection specialist", category="AI / ML security", tasks=["plan", "decide"], notes="Direct/indirect injection and exfil."),
        _entry("rag-poisoning", "RAG poisoning analyst", category="AI / ML security", tasks=["plan", "decide", "harden"], notes="Corpus tampering and retrieval attacks."),
        _entry("model-extraction", "Model extraction analyst", category="AI / ML security", tasks=["plan", "decide"], notes="API abuse and distillation threats."),
        _entry("ml-supply-chain", "ML supply-chain security", category="AI / ML security", tasks=["plan", "harden"], notes="Pickle, ONNX, and hub integrity."),
        # --- Crypto ---
        _entry("crypto-audit", "Cryptography auditor", category="Cryptography & PKI", tasks=["plan", "harden"], notes="Weak algorithms, nonces, and key sizes."),
        _entry("pki-tls", "PKI / TLS architect", category="Cryptography & PKI", tasks=["plan", "harden"], notes="Cert lifecycle, CT, and mTLS."),
        _entry("quantum-readiness", "Post-quantum readiness", category="Cryptography & PKI", tasks=["plan", "harden"], notes="Hybrid KEM migration planning."),
        # --- Forensics & IR ---
        _entry("disk-forensics", "Disk forensics analyst", category="Forensics & incident response", tasks=["plan", "summarize"], notes="Imaging, carving, and timeline."),
        _entry("memory-forensics", "Memory forensics analyst", category="Forensics & incident response", tasks=["plan", "summarize"], notes="Volatility-style artifact recovery."),
        _entry("timeline-analyst", "Incident timeline analyst", category="Forensics & incident response", tasks=["plan", "summarize"], notes="Root cause and blast radius."),
        _entry("ir-coordinator", "Incident response coordinator", category="Forensics & incident response", tasks=["plan", "decide", "summarize"], notes="Containment, eradication, and comms."),
        _entry("evidence-handler", "Digital evidence handler", category="Forensics & incident response", tasks=["plan", "summarize"], notes="Chain of custody and admissibility."),
        # --- Purple team ---
        _entry("purple-team", "Purple team facilitator", category="Purple team & orchestration", tasks=["plan", "decide", "summarize"], notes="Align offense findings with detection gaps."),
        _entry("attack-path", "Attack path modeler", category="Purple team & orchestration", tasks=["plan", "decide", "summarize"], notes="Graph-based paths and choke points."),
        _entry("risk-quant", "Cyber risk quantifier", category="Purple team & orchestration", tasks=["plan", "summarize"], notes="Likelihood, impact, and FAIR-style estimates."),
        _entry("report-writer", "Executive report writer", category="Purple team & orchestration", tasks=["summarize", "harden"], notes="Board-ready findings and remediation."),
        _entry("tool-orchestrator", "Tool orchestrator", category="Purple team & orchestration", tasks=["plan", "decide"], notes="Multi-tool sequencing and parallelism."),
        _entry("decision-engine", "Tactical decision engine", category="Purple team & orchestration", tasks=["decide", "plan"], notes="Next-step selection under constraints."),
        _entry("plan-phase", "Mission plan phase author", category="Purple team & orchestration", tasks=["plan"], notes="Playbook step authoring and tool args."),
        # --- Commercial providers (recipes) ---
        _entry("openai-gpt4o", "OpenAI GPT-4o", category="Commercial LLM providers", model="gpt-4o", base_url_hint=openai, license="commercial", tasks=["plan", "decide", "summarize"], notes="Set OPENAI_API_KEY; wire via FIREBREAK_SCAFFOLD_EXTRA_* or register."),
        _entry("openai-gpt4o-mini", "OpenAI GPT-4o mini", category="Commercial LLM providers", model="gpt-4o-mini", base_url_hint=openai, license="commercial", tasks=["plan", "decide"], notes="Cost-efficient planning scaffold."),
        _entry("anthropic-claude", "Anthropic Claude", category="Commercial LLM providers", model="claude-3-5-sonnet-20241022", base_url_hint=anthropic, license="commercial", tasks=["plan", "decide", "summarize"], notes="OpenAI-compatible gateway or native adapter required."),
        _entry("groq-fast", "Groq fast inference", category="Commercial LLM providers", model="llama-3.3-70b-versatile", base_url_hint=groq, license="commercial", tasks=["plan", "decide"], notes="Low-latency planning via Groq API."),
        _entry("together-mix", "Together.ai models", category="Commercial LLM providers", model="Qwen/Qwen2.5-Coder-32B-Instruct", base_url_hint=together, license="commercial", tasks=["plan", "decide"], notes="Hosted open-weight models."),
        _entry("openrouter-mix", "OpenRouter multi-model", category="Commercial LLM providers", model="openai/gpt-4o-mini", base_url_hint=openrouter, license="commercial", tasks=["plan", "decide"], notes="Route to many providers via one API."),
        _entry("firebreak-gguf", "Firebreak GGUF (local)", category="Commercial LLM providers", model="firebreak-gguf", base_url_hint=ollama, license="Apache-2.0", tasks=["plan", "decide", "harden"], notes="Custom Modelfile from training/adapters."),
        # --- Aggressive strike bundles (mission scaffolds) ---
        _entry("waf-bypass-strike", "WAF bypass strike", category="Web application security", tasks=["plan", "decide"], notes="Evasive ffuf + sqlmap + nuclei rotation against CDN/WAF."),
        _entry("api-endpoint-strike", "API endpoint strike", category="Web application security", tasks=["plan", "decide"], notes="Katana crawl + arjun params + ffuf + nuclei on REST/GraphQL."),
        _entry("cred-spray-strike", "Credential spray strike", category="Identity & access", tasks=["plan", "decide"], notes="Hydra + crackmapexec + enum4linux bounded spray paths."),
        _entry("ssrf-strike-chain", "SSRF strike chain", category="Web application security", tasks=["plan", "decide"], notes="Katana + httpx + ffuf + nuclei SSRF/OAST paths."),
        _entry("sqli-impact-strike", "SQLi impact strike", category="Exploitation & offensive", tasks=["plan", "decide"], notes="Sqlmap + nuclei + katana proof-of-data-access rotation."),
        _entry("xss-chain-strike", "XSS chain strike", category="Web application security", tasks=["plan", "decide"], notes="Dalfox + xsstrike + nuclei XSS templates."),
        _entry("ad-domain-strike", "AD domain strike", category="Post-exploitation & lateral movement", tasks=["plan", "decide"], notes="Bloodhound + crackmapexec + impacket + enum4linux."),
        _entry("cloud-misconfig-strike", "Cloud misconfig strike", category="Cloud & container security", tasks=["plan", "decide"], notes="Nuclei cloud templates + httpx + katana + ffuf."),
        _entry("full-surface-strike", "Full surface strike", category="Reconnaissance & OSINT", tasks=["plan", "recon", "decide"], notes="Subfinder + amass + rustscan + httpx + whatweb parallel sweep."),
    ]


def core_platform_scaffolds() -> list[dict[str, Any]]:
    """Env-wired platform scaffolds shown first in the catalog."""
    return [
        _entry(
            "ollama-primary",
            "Firebreak (Ollama primary)",
            category="Core platform",
            model=os.environ.get("FIREBREAK_LLM_MODEL") or "firebreak",
            base_url_hint=os.environ.get("FIREBREAK_LLM_BASE_URL") or "http://ollama:11434/v1",
            tasks=["plan", "decide", "harden", "summarize"],
            notes="Primary local model from FIREBREAK_LLM_* env.",
        ),
        _entry(
            "ollama-fallback",
            "Ollama fallback (base model)",
            category="Core platform",
            model=os.environ.get("FIREBREAK_LLM_BASE_MODEL") or "qwen2.5:7b",
            base_url_hint=os.environ.get("FIREBREAK_LLM_BASE_URL") or "http://ollama:11434/v1",
            tasks=["plan", "decide"],
            notes="Fallback when primary is unavailable.",
        ),
        _entry(
            "openai-compat",
            "Generic OpenAI-compatible",
            category="Core platform",
            model="gpt-4o-mini",
            base_url_hint="https://api.openai.com/v1",
            license="commercial",
            tasks=["plan", "decide"],
            notes="Set FIREBREAK_SCAFFOLD_EXTRA_* or register a live endpoint.",
        ),
    ]


def cyber_scaffold_catalog() -> list[dict[str, Any]]:
    """Full builtin catalog: core platform + cyber domain recipes."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in core_platform_scaffolds() + _cyber_scaffolds():
        sid = str(row.get("id") or "")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(row)
    return out


def catalog_categories(catalog: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Grouped catalog counts for UI and API consumers."""
    catalog = catalog if catalog is not None else cyber_scaffold_catalog()
    buckets: dict[str, list[dict[str, Any]]] = {cat: [] for cat in SCAFFOLD_CATEGORIES}
    other: list[dict[str, Any]] = []
    for row in catalog:
        cat = str(row.get("category") or "")
        if cat in buckets:
            buckets[cat].append(row)
        else:
            other.append(row)
    result = [
        {"id": cat, "label": cat, "count": len(buckets[cat])}
        for cat in SCAFFOLD_CATEGORIES
        if buckets[cat]
    ]
    if other:
        result.append({"id": "other", "label": "Other", "count": len(other)})
    return result
