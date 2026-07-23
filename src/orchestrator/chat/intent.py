"""Natural-language intent detection for mission chat (plan, launch, confirm, execute)."""

from __future__ import annotations

import re

# Whole-message confirmations — must stay strict so "Confirmed" names are not seeds.
_LAUNCH_ACK_PHRASES: tuple[str, ...] = (
    r"yes(?:\s+please)?",
    r"yep(?:\s+please)?",
    r"yeah",
    r"yup",
    r"sure(?:\s+thing)?",
    r"ok(?:ay)?(?:\s+go)?",
    r"confirmed?",
    r"approved?",
    r"accept(?:ed)?",
    r"agreed?",
    r"affirmative",
    r"absolutely",
    r"definitely",
    r"correct",
    r"right",
    r"perfect",
    r"sounds\s+good",
    r"looks\s+good",
    r"good\s+to\s+go",
    r"all\s+good",
    r"do\s+it",
    r"go\s+ahead",
    r"go\s+for\s+it",
    r"let['\u2019]?s\s+go",
    r"let['\u2019]?s\s+do\s+it",
    r"proceed",
    r"continue",
    r"carry\s+on",
    r"move\s+forward",
    r"execute",
    r"executes?",
    r"ship\s+it",
    r"send\s+it",
    r"fire\s+away",
    r"pull\s+the\s+trigger",
    r"make\s+it\s+so",
    r"run\s+it",
    r"launch\s+it",
    r"begin(?:\s+now)?",
    r"commence",
    r"initiate",
    r"confirm",
    r"green\s+light",
    r"lgtm",
    r"roger(?:\s+that)?",
    r"copy(?:\s+that)?",
    r"yessir",
    r"thumbs\s+up",
    r"👍",
    r"✅",
    # Common Arabic confirmations
    r"نعم",
    r"موافق",
    r"تم",
    r"اكمل",
    r"أكمل",
    r"نفذ",
    r"بالتأكيد",
    r"موافقة",
)

_LAUNCH_ACK_RE = re.compile(
    r"(?i)^\s*(?:"
    + "|".join(_LAUNCH_ACK_PHRASES)
    + r")\s*[.!]?\s*$"
)

_ACK_TOKEN_SET = frozenset(
    {
        "yes",
        "yep",
        "yeah",
        "yup",
        "sure",
        "ok",
        "okay",
        "confirm",
        "confirmed",
        "approve",
        "approved",
        "accept",
        "accepted",
        "agreed",
        "affirmative",
        "absolutely",
        "definitely",
        "correct",
        "right",
        "perfect",
        "proceed",
        "continue",
        "execute",
        "executed",
        "commence",
        "initiate",
        "lgtm",
        "yessir",
        "roger",
        "copy",
    }
)

_FUZZY_ACK_ANCHORS: tuple[str, ...] = (
    "confirmed",
    "confirm",
    "approved",
    "approve",
    "proceed",
    "execute",
    "affirmative",
    "absolutely",
)


def _normalize_ack_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").strip().lower())


def _edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + (ca != cb),
                )
            )
        prev = cur
    return prev[-1]


def _fuzzy_launch_ack(text: str) -> bool:
    """Catch common confirm typos (e.g. Confimed) on short single-line replies."""
    raw = (text or "").strip()
    if not raw or "\n" in raw or len(raw) > 32:
        return False
    if re.fullmatch(
        r"[\s.!]*(?:نعم|موافق|تم|اكمل|أكمل|نفذ|بالتأكيد|موافقة)[\s.!]*",
        raw,
    ):
        return True
    token = _normalize_ack_token(raw)
    if not token or len(token) > 20:
        return False
    if token in _ACK_TOKEN_SET:
        return True
    if len(token) < 4:
        return False
    for anchor in _FUZZY_ACK_ANCHORS:
        if abs(len(token) - len(anchor)) > 2:
            continue
        if _edit_distance(token, anchor) <= 2:
            return True
    return False

# Inline confirm / execute cues inside longer operator messages.
_CONFIRM_INLINE_RE = re.compile(
    r"(?i)\b("
    r"yes|yep|yeah|yup|sure|ok(?:ay)?|confirmed?|approved?|accept(?:ed)?|"
    r"agreed?|affirmative|absolutely|definitely|sounds\s+good|looks\s+good|"
    r"good\s+to\s+go|do\s+it|go\s+ahead|go\s+for\s+it|let['\u2019]?s\s+go|"
    r"let['\u2019]?s\s+do\s+it|proceed|continue|carry\s+on|move\s+forward|"
    r"execute|executes?|confirm|ship\s+it|send\s+it|fire\s+away|make\s+it\s+so|"
    r"run\s+it|launch\s+it|start\s+now|begin\s+now|commence|initiate|green\s+light|"
    r"lgtm|roger(?:\s+that)?|copy(?:\s+that)?|"
    r"نعم|موافق|تم|اكمل|أكمل|نفذ|بالتأكيد"
    r")\b"
)

_LAUNCH_INTENT_RE = re.compile(
    r"(?i)\b("
    r"run|launch|start|kick(?:\s*|-)?off|scan|attack|exploit|assess|pentest|"
    r"pen[-\s]?test|recon|probe|enumerate|investigate|engage|conduct|perform|"
    r"commence|initiate|begin|fire|hit|go\s+(?:at|on|after|for)|"
    r"run\s+(?:recon|a\s+scan|the\s+scan|assessment|mission)|"
    r"start\s+(?:recon|scanning|the\s+scan|assessment|mission)|"
    r"do\s+(?:recon|a\s+scan|the\s+scan|assessment)"
    r")\b"
)

_EXECUTE_INTENT_RE = re.compile(
    r"(?i)\b("
    r"execute|executes?|execution|plan\s+and\s+(?:run|execute|launch|start)|"
    r"run\s+the\s+(?:full\s+)?(?:plan|mission|process|assessment|scan)|"
    r"full\s+red[-\s]?team|do\s+it|go\s+ahead|proceed|make\s+it\s+happen|"
    r"launch\s+it|run\s+it|start\s+the\s+mission|carry\s+out|put\s+it\s+into\s+action|"
    r"implement\s+the\s+plan|based\s+on\s+(?:our\s+)?(?:chat|conversation|discussion)|"
    r"from\s+(?:the\s+)?plan|execute\s+now|run\s+now|start\s+now|begin\s+now|"
    r"fire\s+when\s+ready|send\s+it|pull\s+the\s+trigger|get\s+started|"
    r"put\s+the\s+plan\s+into\s+(?:motion|action)"
    r")\b"
)

_ORDER_INTENT_RE = re.compile(
    r"(?i)\b("
    r"plan\s+and\s+execute|execute\s+the\s+plan|run\s+the\s+mission|"
    r"full\s+red[-\s]?team\s+process|authorized\s+assessment|"
    r"execute\s+the\s+mission|run\s+what\s+we\s+discussed|"
    r"based\s+on\s+what\s+we\s+discussed"
    r")\b"
)

_PLAN_INTENT_RE = re.compile(
    r"(?i)\b("
    r"plan(?:\s+(?:a|an|the|for))?\b|design(?:\s+(?:a|an|the|for))?\b|"
    r"outline(?:\s+(?:a|an|the|for))?\b|draft(?:\s+(?:a|an|the|for))?\b|"
    r"map\s+out|build\s+a\s+plan|create\s+a\s+plan|prepare\s+a\s+(?:plan|mission)|"
    r"game\s+plan|strategy|playbook|workflow|approach|recommend(?:\s+a)?|"
    r"suggest(?:\s+a)?|what(?:['\u2019]?s|\s+is)\s+the\s+(?:approach|plan|strategy)|"
    r"how\s+(?:would|should)\s+(?:you|we)\s+(?:attack|assess|approach|proceed)|"
    r"what\s+tools|tool\s+chain|attack\s+chain|kill\s+chain|mission\s+plan|"
    r"lay\s+out|sketch\s+(?:a|an|the)\s+(?:plan|approach)"
    r")\b"
)

_HUNT_VULNS_INTENT_RE = re.compile(
    r"(?i)\b("
    r"find\s+(?:a\s+)?vulnerabilit(?:y|ies)|"
    r"hunt\s+(?:for\s+)?vulnerabilit(?:y|ies)|"
    r"don['\u2019]?t\s+stop\s+until|"
    r"do\s+not\s+stop\s+until|"
    r"until\s+(?:you\s+)?find|"
    r"keep\s+(?:going|scanning|running)\s+until|"
    r"no\s+stop\s+until|"
    r"don['\u2019]?t\s+stop\s+before|"
    r"until\s+(?:a\s+)?vuln|"
    r"find\s+(?:issues|bugs|exploits)"
    r")\b"
)

_OSINT_ONLY_INTENT_RE = re.compile(
    r"(?i)\b("
    r"osint(?:[-\s]?only)?|osint\s+only|open[-\s]?source\s+intel(?:ligence)?|"
    r"intelligence\s+(?:only|report|gathering)|intel\s+only|gather\s+intel|"
    r"surface\s+map|leak\s+(?:hunt|match|radar)|breach_intel|theharvester|subfinder|"
    r"gau|sherlock|katana|httpx|whatweb|darkweb|"
    r"scrape\s+public|hidden[-\s]web|no\s+port\s+scan|people\s+search|"
    r"background\s+(?:check|search)|email\s+trace|username\s+(?:search|trace)|"
    r"phone\s+(?:lookup|trace)|domain\s+intel|"
    r"without\s+(?:any\s+)?(?:port\s+scan|vuln|exploitation)|"
    r"run\s+osint|do\s+osint|perform\s+osint|osint\s+(?:on|for|about)"
    r")\b"
)

_OSINT_EXCLUDE_INTENT_RE = re.compile(
    r"(?i)\b(nmap|rustscan|nuclei|sqlmap|metasploit|exploit|port\s+scan)\b"
)

_AUTHZ_ADD_INTENT_RE = re.compile(
    r"(?i)\b("
    r"add(?:\s+it|\s+them|\s+that|\s+this|\s+.+)?\s+(?:to\s+)?(?:my\s+)?"
    r"(?:authorized|auth(?:orized)?)\s*(?:target\s*)?list|"
    r"authorize\s+(?:this|the|these|all|it)\s+(?:target|seed|url|domain)s?"
    r")\b"
)

_ADAPTIVE_ATTACK_RE = re.compile(
    r"(?i)\b(deep\s+study|study\s+(?:the\s+)?(?:site|target|website)|"
    r"keep\s+trying|try\s+another\s+tool|invent|new\s+method|"
    r"full\s+(?:attack|assessment|red[-\s]?team)|"
    r"find\s+(?:a\s+)?way\s+in|break\s+in|compromise)\b"
)


def is_launch_ack_message(text: str) -> bool:
    """True when the operator is confirming a pending plan, not naming a target."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _LAUNCH_ACK_RE.match(stripped):
        return True
    return _fuzzy_launch_ack(stripped)


def wants_confirm(text: str) -> bool:
    """Broader confirm cues inside a message (may be longer than a bare ack)."""
    if is_launch_ack_message(text):
        return True
    return bool(_CONFIRM_INLINE_RE.search(text or ""))


_PLAN_CONTEXT_RE = re.compile(
    r"(?i)\b("
    r"design|outline|draft|map\s+out|build\s+a\s+plan|create\s+a\s+plan|"
    r"what(?:['\u2019]?s|\s+is)\s+the\s+(?:approach|plan|strategy)|"
    r"how\s+(?:would|should)\s+(?:you|we)|recommend|suggest|game\s+plan|"
    r"attack\s+chain|kill\s+chain|tool\s+chain|mission\s+plan|lay\s+out"
    r")\b"
)


def wants_launch(text: str) -> bool:
    blob = text or ""
    if _PLAN_CONTEXT_RE.search(blob) and not _EXECUTE_INTENT_RE.search(blob):
        return False
    return bool(_LAUNCH_INTENT_RE.search(blob))


def wants_plan(text: str, messages: list[dict[str, str]] | None = None) -> bool:
    blob = _conversation_blob(text, messages)
    return bool(_PLAN_INTENT_RE.search(blob))


def wants_execution(text: str, messages: list[dict[str, str]] | None = None) -> bool:
    blob = _conversation_blob(text, messages)
    return bool(_EXECUTE_INTENT_RE.search(blob) or _ORDER_INTENT_RE.search(blob))


def wants_vuln_hunt(text: str, messages: list[dict[str, str]] | None = None) -> bool:
    blob = _conversation_blob(text, messages)
    return bool(_HUNT_VULNS_INTENT_RE.search(blob))


def wants_osint_only(text: str, messages: list[dict[str, str]] | None = None) -> bool:
    blob = _conversation_blob(text, messages)
    if not _OSINT_ONLY_INTENT_RE.search(blob):
        return False
    if _OSINT_EXCLUDE_INTENT_RE.search(blob) and not re.search(
        r"(?i)(no\s+(?:port|vuln)|without\s+(?:port|vuln|exploit)|do\s+not\s+run)",
        blob,
    ):
        return False
    return True


def wants_authorize_targets(text: str) -> bool:
    return bool(_AUTHZ_ADD_INTENT_RE.search(text or ""))


def wants_adaptive_attack(text: str, messages: list[dict[str, str]] | None = None) -> bool:
    if wants_vuln_hunt(text, messages):
        return True
    blob = _conversation_blob(text, messages)
    if wants_execution(text, messages):
        return True
    return bool(_ADAPTIVE_ATTACK_RE.search(blob))


def mission_compile_trigger(
    text: str,
    messages: list[dict[str, str]] | None = None,
    *,
    osint_order: bool = False,
) -> bool:
    """True when chat should synthesize or attach a runnable mission plan."""
    return bool(
        wants_launch(text)
        or wants_confirm(text)
        or wants_execution(text, messages)
        or wants_plan(text, messages)
        or wants_vuln_hunt(text, messages)
        or wants_adaptive_attack(text, messages)
        or osint_order
    )


def mission_auto_execute_trigger(
    text: str,
    messages: list[dict[str, str]] | None = None,
    *,
    osint_order: bool = False,
) -> bool:
    """True when a ready plan should launch immediately (not plan-only requests)."""
    if (
        wants_plan(text, messages)
        and not wants_execution(text, messages)
        and not wants_confirm(text)
        and not wants_vuln_hunt(text, messages)
        and not wants_adaptive_attack(text, messages)
        and not osint_order
    ):
        return False
    return bool(
        wants_execution(text, messages)
        or wants_launch(text)
        or wants_confirm(text)
        or wants_vuln_hunt(text, messages)
        or wants_adaptive_attack(text, messages)
        or osint_order
    )


def _conversation_blob(text: str, messages: list[dict[str, str]] | None, *, limit: int = 8) -> str:
    parts = [text or ""]
    if messages:
        parts.extend(
            str(m.get("content") or "")
            for m in messages[-limit:]
            if m.get("role") in ("user", "assistant")
        )
    return " ".join(parts)


ADVISOR_INTENT_GUIDE = """Operator intent (critical — Firebreak parses these server-side; treat them the same):

PLAN-ONLY — emit ```firebreak-plan```, then ask to confirm; do NOT say the mission is already running:
- design / outline / draft / map out / build or create a plan, game plan, strategy, approach
- attack chain, kill chain, tool chain, mission plan, "what's the approach", "how would you attack"
- recommend or suggest a flow — plan first, wait for explicit go-ahead unless they also order execution

EXECUTE / LAUNCH — emit ```firebreak-plan``` plus one brief line; backend auto-runs when enabled:
- run, launch, start, kick off, scan, assess, recon, probe, conduct, perform, initiate, commence
- execute, carry out the plan, put it into action, run what we discussed, based on our chat
- plan and execute, full red-team process, get started, fire when ready, send it

CONFIRM — after you showed a plan, treat as authorization to launch (never a new target name):
- yes, confirmed, approved, sounds good, looks good, good to go, let's go, go ahead, proceed, do it
- affirmative, green light, ship it, run it, launch it, absolutely, roger, copy that
- Arabic: نعم, موافق, تم, أكمل, نفذ, بالتأكيد

OSINT-ONLY — schedule only intelligence tools (theharvester, subfinder, gau, sherlock, katana,
httpx, whatweb, darkweb, breach_intel); no nmap/nuclei/sqlmap/metasploit unless they also order attack:
- osint-only, gather intel, open-source intelligence, run osint on/for/about NAME
- investigate, lookup, trace, background check, leak hunt, breach intel

Target-free deck follow-up: the operator's next single-line message may BE the seed (full name in any
script, email, @username, phone, domain, social URL). Short confirms like "Confirmed" or "sounds good"
approve the pending plan — they are never OSINT seeds or hostnames."""
