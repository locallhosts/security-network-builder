"""Console, Markdown and JSON reporting."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from models import Recommendation


def render_console(recs: list[Recommendation]) -> str:
    if not recs:
        return "No engineers matched the profile. Try lowering min_stars or widening keywords."
    out = ["Recommended Engineers:\n"]
    for r in recs:
        out.append(f"@{r.login}\n\nScore: {r.score:g}\n")
        out.append("Areas:")
        out.extend(f"- {d}" for d in r.matched_domains)
        out.append("")
    return "\n".join(out)


def render_markdown(recs: list[Recommendation], profile_name: str) -> str:
    lines = [
        f"# Security Network Report: {profile_name}",
        "",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "| # | Engineer | Score | Areas |",
        "|---|----------|-------|-------|",
    ]
    for i, r in enumerate(recs, 1):
        lines.append(f"| {i} | [@{r.login}]({r.url}) | {r.score:g} | {', '.join(r.matched_domains)} |")
    for r in recs:
        p = r.profile
        lines += ["", f"## @{r.login} (score {r.score:g})", ""]
        if p.get("name") or p.get("bio"):
            lines.append(f"**{p.get('name') or r.login}**: {p.get('bio') or ''}".rstrip(": "))
            lines.append("")
        lines.append("**Matched areas**")
        lines += [f"- ✓ {d}" for d in r.matched_domains]
        lines += ["", "**Evidence**"]
        lines += [f"- {e}" for e in r.evidence]
        lines += ["", "**Score breakdown**"]
        lines += [f"- {k}: +{v:g}" for k, v in r.breakdown.items()]
        lines += ["", "**Top matching repositories**"]
        lines += [f"- [{x['name']}]({x['url']}) ⭐ {x['stars']}" for x in r.matched_repos]
    return "\n".join(lines) + "\n"


def write_reports(recs: list[Recommendation], out_dir: str | Path, profile_name: str, fmt: str = "both") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    written = []
    if fmt in ("md", "both"):
        p = out / f"report_{stamp}.md"
        p.write_text(render_markdown(recs, profile_name), encoding="utf-8")
        written.append(p)
    if fmt in ("json", "both"):
        p = out / f"report_{stamp}.json"
        p.write_text(json.dumps([r.to_dict() for r in recs], indent=2), encoding="utf-8")
        written.append(p)
    return written
