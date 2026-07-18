import html
import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlparse


def target_filename(target: str) -> str:
    """Convert a URL, hostname, or IP into a safe report filename."""
    value = target.strip()
    parsed = urlparse(value if "://" in value else f"//{value}", scheme="")

    parts = [parsed.hostname or parsed.path or "target"]
    if parsed.port:
        parts.append(str(parsed.port))
    if parsed.hostname and parsed.path and parsed.path != "/":
        parts.extend(part for part in parsed.path.split("/") if part)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        parts.extend((key, value))

    name = "_".join(parts)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("._-") or "target"


def _build_report(target: str, rows: list[dict]) -> dict:
    phases: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        phase = str(row.get("phase") or "unknown")
        phases[phase].append(
            {
                "tool": row.get("tool"),
                "timestamp": row.get("timestamp"),
                "result": row.get("result"),
            }
        )

    return {
        "target": target,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result_count": len(rows),
        "phases": dict(phases),
    }


def _render_value(value) -> str:
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, indent=2, ensure_ascii=False)
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    return html.escape(rendered)


def _render_html(report: dict) -> str:
    sections = []
    for phase, entries in report["phases"].items():
        tools = []
        for entry in entries:
            result = entry.get("result") or {}
            error = result.get("error") if isinstance(result, dict) else None
            status = "error" if error else "ok"
            details = []
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in {"tool", "target", "raw_output"}:
                        continue
                    details.append(
                        f"<dt>{html.escape(str(key))}</dt>"
                        f"<dd><pre>{_render_value(value)}</pre></dd>"
                    )
                raw_output = result.get("raw_output")
            else:
                details.append(f"<dd><pre>{_render_value(result)}</pre></dd>")
                raw_output = None

            raw = ""
            if raw_output:
                raw = (
                    "<details><summary>Raw output</summary>"
                    f"<pre>{_render_value(raw_output)}</pre></details>"
                )

            tools.append(
                '<article class="tool">'
                f'<h3>{html.escape(str(entry.get("tool") or "unknown"))}'
                f' <span class="{status}">{status.upper()}</span></h3>'
                f'<p class="timestamp">{html.escape(str(entry.get("timestamp") or ""))}</p>'
                f"<dl>{''.join(details)}</dl>{raw}</article>"
            )
        sections.append(
            f"<section><h2>{html.escape(phase)}</h2>{''.join(tools)}</section>"
        )

    target = html.escape(str(report["target"]))
    generated = html.escape(str(report["generated_at"]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cerberus-X report — {target}</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 1100px; margin: 2rem auto; padding: 0 1rem; background: #0b1020; color: #e5e7eb; }}
    header, section {{ background: #121a2d; border: 1px solid #26334d; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1rem; }}
    .tool {{ border-top: 1px solid #26334d; padding: .75rem 0; }}
    .tool:first-of-type {{ border-top: 0; }}
    .ok {{ color: #4ade80; }} .error {{ color: #fb7185; }}
    .timestamp {{ color: #94a3b8; font-size: .9rem; }}
    dt {{ color: #93c5fd; font-weight: 700; }}
    dd {{ margin: .25rem 0 1rem; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #080d18; border-radius: 8px; padding: .75rem; }}
    summary {{ cursor: pointer; color: #93c5fd; }}
  </style>
</head>
<body>
  <header>
    <h1>{target}</h1>
    <p>Generated {generated} · {report["result_count"]} results</p>
  </header>
  {''.join(sections)}
</body>
</html>
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def export_target_reports(
    target: str,
    rows: list[dict],
    output_dir: str | os.PathLike | None = None,
) -> dict[str, Path]:
    directory = Path(
        output_dir or os.environ.get("CERBERUS_OUTPUT_DIR", "/app/output")
    )
    basename = target_filename(target)
    json_path = directory / f"{basename}.json"
    html_path = directory / f"{basename}.html"
    report = _build_report(target, rows)

    _atomic_write(
        json_path,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    )
    _atomic_write(html_path, _render_html(report))
    return {"json": json_path, "html": html_path}
