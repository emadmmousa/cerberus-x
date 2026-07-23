"""Parse and normalize OSINT engagement seeds (multi-identifier targets)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

OSINT_KINDS = (
    "social_url",
    "username",
    "full_name",
    "mobile",
    "email",
    "domain",
)

from orchestrator.chat.intent import is_launch_ack_message  # noqa: F401 — re-export

_STRIKE_PROFILE_RE = re.compile(
    r"(?i)Target profile for this deck:\s*"
    r"(username|full_name|email|mobile|social_url|domain)"
)

_DECK_FOLLOWUP_RE = re.compile(
    r"(?i)wait for my next message with the authorized"
)


def expected_strike_profile(text: str) -> str | None:
    """Parse Strike library deck marker emitted by the frontend."""
    match = _STRIKE_PROFILE_RE.search(text or "")
    if not match:
        return None
    kind = match.group(1).strip().lower()
    return kind if kind in OSINT_KINDS else None


# Intelligence-only tools — scrape public/hidden sources and match leaks; no vuln/exploit.
OSINT_TOOLS: tuple[str, ...] = (
    "theharvester",
    "subfinder",
    "gau",
    "sherlock",
    "katana",
    "httpx",
    "whatweb",
    "darkweb",
    "breach_intel",
)

OSINT_SCOPE = (
    "Scrape public sources (subdomains, archives, usernames, web surfaces), "
    "index hidden services, and query breach databases for records matching "
    "operator-provided seeds. Does not run vuln scans, payloads, or credential attacks."
)

OSINT_KIND_LABELS: dict[str, str] = {
    "social_url": "Social profile URL",
    "username": "Username",
    "full_name": "Full name",
    "mobile": "Mobile number",
    "email": "Email",
    "domain": "Domain",
}

# Person-centric OSINT missions label/display target (not strike host selection).
OSINT_MISSION_TARGET_ORDER: tuple[str, ...] = (
    "full_name",
    "email",
    "username",
    "mobile",
    "domain",
    "social_url",
)

_SEED_LINE_RE = re.compile(
    r"(?im)^\s*[-*•]?\s*"
    r"(Full name|Email|Username|Mobile(?:\s+number)?|Domain|Social profile URL)\s*:\s*(.+?)\s*$"
)
_SEED_LINE_KINDS: dict[str, str] = {
    "full name": "full_name",
    "email": "email",
    "username": "username",
    "mobile": "mobile",
    "mobile number": "mobile",
    "domain": "domain",
    "social profile url": "social_url",
}
_OSINT_ON_SUBJECT_RE = re.compile(
    r"(?i)\bosint(?:[-\s]?only)?\s+on\s+(.+?)\s+and\s+seeds\b"
)
_OSINT_FOR_SUBJECT_RE = re.compile(
    r"(?i)\b(?:run\s+)?osint(?:[-\s]?only)?\s+(?:on|for|about|against)\s+(.+?)(?:\s+and\s+seeds|\s*[:.]?\s*$|\s+(?:using|with)\b)"
)
_OSINT_INVESTIGATE_RE = re.compile(
    r"(?i)\b(?:investigate|lookup|trace|background\s+(?:check|search)\s+(?:on|for))\s+(.+?)(?:\s+and\s+seeds|\s*[:.]?\s*$|\s+(?:using|with)\b)"
)

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w+$", re.I)
_PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,20}$")
_USERNAME_RE = re.compile(r"^@?[a-z0-9._-]{2,64}$", re.I)
_DOMAIN_RE = re.compile(
    r"^(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?(?:/.*)?$",
    re.I,
)
_SOCIAL_HOSTS = frozenset(
    {
        "twitter.com",
        "x.com",
        "instagram.com",
        "facebook.com",
        "linkedin.com",
        "tiktok.com",
        "youtube.com",
        "threads.net",
        "reddit.com",
        "github.com",
        "mastodon.social",
    }
)


def _collapse_name(value: str) -> str:
    return " ".join(value.strip().split())


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _normalize_mobile(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if raw.strip().startswith("+") and digits:
        return f"+{digits}"
    return digits


def _normalize_domain(raw: str) -> str:
    text = (raw or "").strip().rstrip(".,)]")
    probe = text if "://" in text else f"https://{text.lstrip('/')}"
    host = (urlparse(probe).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_social_url(raw: str) -> str:
    text = (raw or "").strip()
    if "://" not in text:
        text = f"https://{text.lstrip('/')}"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").rstrip("/")
    return f"https://{host}{path}" if path else f"https://{host}"


def classify_osint_seed(raw: str, *, kind: str | None = None) -> dict[str, str]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty seed")
    if is_launch_ack_message(text):
        raise ValueError("launch ack, not seed")

    if kind:
        kind = str(kind).strip().lower()
        if kind not in OSINT_KINDS:
            raise ValueError(f"invalid kind: {kind}")
    else:
        kind = _infer_kind(text)

    if kind == "email":
        value = text.lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("invalid email")
        return {"kind": kind, "value": value, "display": value}

    if kind == "mobile":
        value = _normalize_mobile(text)
        if len(re.sub(r"\D", "", value)) < 7:
            raise ValueError("invalid mobile number")
        return {"kind": kind, "value": value, "display": value}

    if kind == "social_url":
        value = _normalize_social_url(text)
        host = (urlparse(value).hostname or "").lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        if not host:
            raise ValueError("invalid social profile URL")
        return {"kind": kind, "value": value, "display": value}

    if kind == "domain":
        value = _normalize_domain(text)
        if not value:
            raise ValueError("invalid domain")
        return {"kind": kind, "value": value, "display": value}

    if kind == "username":
        value = text.lstrip("@").lower()
        if not _USERNAME_RE.match(value) and not _USERNAME_RE.match(f"@{value}"):
            raise ValueError("invalid username")
        return {"kind": kind, "value": value, "display": f"@{value}"}

    if kind == "full_name":
        value = _collapse_name(text)
        if len(value) < 2 or not _has_letters(value):
            raise ValueError("invalid full name")
        return {"kind": kind, "value": value, "display": value}

    raise ValueError("invalid seed")


def _infer_kind(text: str) -> str:
    if _EMAIL_RE.match(text.strip()):
        return "email"
    if _PHONE_RE.match(text.strip()) and sum(ch.isdigit() for ch in text) >= 7:
        return "mobile"
    if text.strip().startswith("@") or (
        _USERNAME_RE.match(text.strip()) and "." not in text and "@" not in text and " " not in text
    ):
        return "username"
    probe = text if "://" in text else f"https://{text.lstrip('/')}"
    host = (urlparse(probe).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if host in _SOCIAL_HOSTS:
        return "social_url"
    if _DOMAIN_RE.match(text.strip()):
        return "domain"
    if " " in text.strip() and _has_letters(text):
        return "full_name"
    return "username"


def normalize_osint_seeds(raw_rows: list[Any] | None) -> list[dict[str, str]]:
    from utils.text_encoding import ensure_utf8_text

    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw_rows or []:
        if isinstance(row, dict):
            value = ensure_utf8_text(str(row.get("value") or row.get("target") or "").strip())
            kind = ensure_utf8_text(str(row.get("kind") or row.get("type") or "").strip().lower()) or None
        else:
            value = ensure_utf8_text(str(row or "").strip())
            kind = None
        if not value:
            continue
        try:
            seed = classify_osint_seed(value, kind=kind)
        except ValueError:
            continue
        key = (seed["kind"], seed["value"])
        if key in seen:
            continue
        seen.add(key)
        out.append(seed)
    return out


def parse_operator_osint_seed_block(text: str) -> list[dict[str, str]]:
    """Parse labeled seed lines from operator prompt blocks."""
    seeds: list[dict[str, str]] = []
    for match in _SEED_LINE_RE.finditer(text or ""):
        label = match.group(1).strip().lower()
        value = match.group(2).strip()
        kind = _SEED_LINE_KINDS.get(label)
        if not kind or not value:
            continue
        try:
            seeds.append(classify_osint_seed(value, kind=kind))
        except ValueError:
            continue
    return seeds


def _clean_osint_subject(raw: str) -> str:
    name = re.sub(r"(?i)^authorized\s+", "", (raw or "").strip()).strip()
    name = re.sub(r"(?i)\s+and\s+seeds.*$", "", name).strip(" .,:;")
    return name


def _subject_to_osint_seed(name: str) -> list[dict[str, str]]:
    if not name or name.upper() == "TARGET":
        return []
    try:
        return [classify_osint_seed(name)]
    except ValueError:
        try:
            return [classify_osint_seed(name, kind="full_name")]
        except ValueError:
            return []


def extract_osint_on_subject(text: str) -> list[dict[str, str]]:
    """Extract a subject from OSINT-on/for/investigate phrasing."""
    blob = text or ""
    for pattern in (_OSINT_ON_SUBJECT_RE, _OSINT_FOR_SUBJECT_RE, _OSINT_INVESTIGATE_RE):
        match = pattern.search(blob)
        if match:
            seeds = _subject_to_osint_seed(_clean_osint_subject(match.group(1)))
            if seeds:
                return seeds
    return []


def extract_osint_seeds_from_text(text: str) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    seeds.extend(parse_operator_osint_seed_block(text))
    seeds.extend(extract_osint_on_subject(text))
    for token in re.findall(
        r"[\w.+-]+@[\w.-]+\.\w+|@[\w._-]{2,64}|\+?\d[\d\s().-]{6,18}\d|https?://[^\s]+",
        text or "",
    ):
        try:
            seeds.append(classify_osint_seed(token))
        except ValueError:
            continue
    for match in _DOMAIN_RE.finditer(text or ""):
        try:
            seeds.append(classify_osint_seed(match.group(0), kind="domain"))
        except ValueError:
            continue
    return normalize_osint_seeds(seeds)


def message_scopes_osint_seeds(text: str) -> bool:
    """True when the operator prompt defines OSINT scope inline (not via Prompts tab state alone)."""
    blob = text or ""
    if (
        _OSINT_ON_SUBJECT_RE.search(blob)
        or _OSINT_FOR_SUBJECT_RE.search(blob)
        or _OSINT_INVESTIGATE_RE.search(blob)
    ):
        return True
    if parse_operator_osint_seed_block(blob):
        return True
    if re.search(r"(?i)operator osint seeds", blob):
        return True
    return False


def extract_followup_osint_seeds(
    text: str,
    messages: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """Parse a single-line target the operator sends after a target-free deck template."""
    line = (text or "").strip()
    if not line or "\n" in line or len(line) > 240:
        return []
    if is_launch_ack_message(line):
        return []
    if re.search(
        r"(?i)operator osint seeds|firebreak-plan|add.*authorized|wait for my next message",
        line,
    ):
        return []
    history = list(messages or [])
    if not history:
        return []
    user_turns = [m for m in history if m.get("role") == "user"]
    if len(user_turns) < 2:
        return []
    prior_users = user_turns[:-1]
    prior_blob = " ".join(str(m.get("content") or "") for m in prior_users)
    deck_turn = bool(_DECK_FOLLOWUP_RE.search(prior_blob))
    osint_turn = bool(_OSINT_ON_SUBJECT_RE.search(prior_blob)) or bool(
        re.search(r"(?i)\bosint(?:[-\s]?only)?\b", prior_blob)
    )
    if not deck_turn and not osint_turn:
        return []
    preferred_kind = expected_strike_profile(prior_blob)
    try:
        if preferred_kind:
            try:
                return [classify_osint_seed(line, kind=preferred_kind)]
            except ValueError:
                pass
        return [classify_osint_seed(line)]
    except ValueError:
        if osint_turn or deck_turn:
            try:
                return [classify_osint_seed(line, kind="full_name")]
            except ValueError:
                return []
        return []


def _resolve_osint_seeds_from_text(
    text: str,
    *,
    messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Resolve seeds embedded in a single operator message."""
    text = text or ""
    if is_launch_ack_message(text):
        return []
    subject = extract_osint_on_subject(text)
    if subject:
        return normalize_osint_seeds(subject)
    if parse_operator_osint_seed_block(text) or re.search(r"(?i)operator osint seeds", text):
        return normalize_osint_seeds(extract_osint_seeds_from_text(text))
    followup = extract_followup_osint_seeds(text, messages)
    if followup:
        return followup
    msg_seeds = normalize_osint_seeds(extract_osint_seeds_from_text(text))
    if msg_seeds:
        return msg_seeds
    return []


def resolve_osint_seeds_for_chat(
    agent_seeds: list[Any] | None,
    user_text: str,
    *,
    messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Seeds from operator chat text only — never the Prompts-tab panel."""
    text = user_text or ""
    if is_launch_ack_message(text) and messages:
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            prior = str(msg.get("content") or "").strip()
            if not prior or prior == text.strip() or is_launch_ack_message(prior):
                continue
            seeds = _resolve_osint_seeds_from_text(prior, messages=messages)
            if seeds:
                return seeds
        return []
    return _resolve_osint_seeds_from_text(text, messages=messages)


def merge_osint_seeds_for_chat(
    agent_seeds: list[Any] | None,
    user_text: str,
    *,
    messages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Merge UI seeds with identifiers embedded in operator chat text."""
    combined: list[Any] = list(agent_seeds or [])
    blobs = [user_text or ""]
    if messages:
        blobs.extend(
            str(m.get("content") or "")
            for m in messages[-8:]
            if m.get("role") == "user"
        )
    message_seeds: list[dict[str, str]] = []
    for blob in blobs:
        message_seeds.extend(extract_osint_seeds_from_text(blob))
    message_seeds = normalize_osint_seeds(message_seeds)
    if not message_seeds:
        return normalize_osint_seeds(combined)

    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in normalize_osint_seeds(combined):
        by_key[(row["kind"], row["value"])] = row

    replace_kinds = {"full_name"}
    for seed in message_seeds:
        if seed["kind"] in replace_kinds:
            for key in list(by_key):
                if key[0] == seed["kind"]:
                    del by_key[key]
        by_key[(seed["kind"], seed["value"])] = seed

    return normalize_osint_seeds(list(by_key.values()))


def format_osint_seeds_for_llm(seeds: list[dict[str, str]]) -> str:
    """Operator-facing seed block injected into chat turns for the advisor LLM."""
    normalized = normalize_osint_seeds(seeds)
    if not normalized:
        return ""
    lines = [
        f"- {OSINT_KIND_LABELS.get(seed['kind'], seed['kind'])}: {seed['display']}"
        for seed in normalized
    ]
    return (
        "[Operator OSINT seeds — use ONLY these identifiers; never invent example.com, "
        "john-doe, or placeholder phones/emails]\n"
        + "\n".join(lines)
    )


def primary_mission_target(seeds: list[dict[str, str]]) -> str:
    if not seeds:
        return ""
    for preferred in ("domain", "email", "social_url", "username", "mobile", "full_name"):
        for seed in seeds:
            if seed.get("kind") == preferred:
                return str(seed.get("display") or seed.get("value") or "")
    first = seeds[0]
    return str(first.get("display") or first.get("value") or "")


def primary_osint_mission_target(seeds: list[dict[str, str]]) -> str:
    """Primary label for OSINT-only missions (prefer person name over social URL)."""
    normalized = normalize_osint_seeds(seeds)
    if not normalized:
        return ""
    for preferred in OSINT_MISSION_TARGET_ORDER:
        for seed in normalized:
            if seed.get("kind") == preferred:
                return str(seed.get("display") or seed.get("value") or "")
    first = normalized[0]
    return str(first.get("display") or first.get("value") or "")


def compile_osint_plan(
    seeds: list[dict[str, str]],
    *,
    posture: str = "aggressive",
    nl_goal: str = "",
) -> dict[str, Any] | None:
    """Build a runnable OSINT-only mission plan from operator seeds."""
    from tools.normalize_args import default_args_for

    normalized = normalize_osint_seeds(seeds)
    if not normalized:
        return None
    try:
        from orchestrator.mcp.registry import known_tools

        allow = set(known_tools())
    except Exception:
        allow = set(OSINT_TOOLS)
    tools = [tool for tool in OSINT_TOOLS if tool in allow]
    if not tools:
        return None
    target = primary_osint_mission_target(normalized)
    if not nl_goal:
        labels = ", ".join(
            f"{OSINT_KIND_LABELS.get(seed['kind'], seed['kind'])}={seed['display']}"
            for seed in normalized[:6]
        )
        nl_goal = (
            f"Authorized OSINT only: scrape public/hidden sources and match leaks for {labels}. "
            "No port scans or exploitation."
        )
    phase = {
        "name": "osint",
        "parallel": True,
        "tools": [{"tool": tool, "args": default_args_for(tool)} for tool in tools],
    }
    return {
        "target": target,
        "posture": posture,
        "nl_goal": nl_goal,
        "stealth": "high",
        "phases": [phase],
        "new_tools": [],
        "tool_names": tools,
        "osint_only": True,
    }


def proposal_is_osint_only(proposal: dict[str, Any]) -> bool:
    plan = proposal.get("plan") if isinstance(proposal.get("plan"), dict) else {}
    tools = plan.get("tool_names") or []
    if tools:
        return all(str(tool).lower() in OSINT_TOOLS for tool in tools)
    return bool(proposal.get("osint_only"))


def apply_osint_seeds_to_proposal(
    proposal: dict[str, Any],
    seeds: list[dict[str, str]],
    *,
    osint_only: bool | None = None,
) -> dict[str, Any]:
    out = dict(proposal or {})
    if not seeds:
        return out
    out["osint_seeds"] = seeds
    use_osint_target = osint_only if osint_only is not None else proposal_is_osint_only(out)
    pick_target = primary_osint_mission_target if use_osint_target else primary_mission_target
    if use_osint_target:
        out["target"] = pick_target(seeds)
    elif not str(out.get("target") or "").strip():
        out["target"] = pick_target(seeds)
    if out.get("target") and not out.get("nl_goal"):
        labels = ", ".join(f"{OSINT_KIND_LABELS.get(s['kind'], s['kind'])}={s['display']}" for s in seeds[:4])
        out["nl_goal"] = (
            f"Authorized OSINT: scrape public and hidden sources; match leaked data for {labels}"
        )
    missing = [m for m in (out.get("missing") or []) if m != "target"]
    if out.get("target"):
        out["missing"] = missing
        if not missing:
            out["ready"] = True
    else:
        out["missing"] = missing or ["target"]
        out["ready"] = False
    return out
