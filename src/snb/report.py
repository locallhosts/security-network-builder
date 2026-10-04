"""Console, Markdown and JSON reporting."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Recommendation


def render_console(recs: list[Recommendation]) -> str:
    if not recs:
        return "No engineers matched the profile. Try lowering min_stars or widening keywords."
    out = ["Recommended Engineers:\n"]
    for r in recs:
        out.append(f"@{r.login}{'  (new)' if r.is_new else ''}\n\nScore: {r.score:g}\n")
        out.append("Areas:")
        out.extend(f"- {d}" for d in r.matched_domains)
        if r.explanation:
            out.append(f"\nWhy: {r.explanation}")
        out.append("")
    return "\n".join(out)


def render_markdown(recs: list[Recommendation], profile_name: str, graph: dict[str, Any] | None = None, orgs: list[dict[str, Any]] | None = None) -> str:
    lines = [
        f"# Security Network Report: {profile_name}",
        "",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "| # | Engineer | Score | Areas |",
        "|---|----------|-------|-------|",
    ]
    for i, r in enumerate(recs, 1):
        tag = " 🆕" if r.is_new else ""
        lines.append(f"| {i} | [@{r.login}]({r.url}){tag} | {r.score:g} | {', '.join(r.matched_domains)} |")

    communities = [c for c in (graph or {}).get("communities", []) if c["size"] > 1]
    if communities:
        lines += ["", "## Communities", ""]
        for c in communities:
            lines.append(f"- **Community {c['id'] + 1}** ({c['top_domain'] or 'mixed'}): " + ", ".join(f"@{m}" for m in c["members"]))
    if orgs:
        lines += ["", "## Organizations", ""]
        for o in orgs[:10]:
            lines.append(f"- [{o['login']}]({o['url']}): {', '.join('@' + m for m in o['members'])} (total score {o['total_score']:g})")

    for r in recs:
        p = r.profile
        lines += ["", f"## @{r.login} (score {r.score:g})", ""]
        if p.get("name") or p.get("bio"):
            lines += [f"**{p.get('name') or r.login}**: {p.get('bio') or ''}".rstrip(": "), ""]
        if r.explanation:
            lines += [r.explanation, ""]
        lines.append("**Matched areas**")
        lines += [f"- ✓ {d}" for d in r.matched_domains]
        lines += ["", "**Evidence**"]
        lines += [f"- {e}" for e in r.evidence]
        lines += ["", "**Score breakdown**"]
        lines += [f"- {k}: +{v:g}" for k, v in r.breakdown.items()]
        lines += ["", "**Top matching repositories**"]
        lines += [f"- [{x['name']}]({x['url']}) ⭐ {x['stars']}" for x in r.matched_repos]
    return "\n".join(lines) + "\n"


def write_pdf_report(
    recs: list[Recommendation],
    out_dir: str | Path,
    profile_name: str,
    graph: dict[str, Any] | None = None,
    orgs: list[dict[str, Any]] | None = None,
) -> Path:
    """Write a compact PDF report using the optional reportlab dependency."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError as exc:
        raise RuntimeError("PDF reports require the optional 'pdf' dependency: pip install '.[pdf]'") from exc

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"report_{stamp}.pdf"
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Security Network Report: {profile_name}", styles["Title"]),
             Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["Normal"]), Spacer(1, 12)]
    for index, rec in enumerate(recs, 1):
        story.append(Paragraph(f"{index}. @{rec.login} — score {rec.score:g}", styles["Heading2"]))
        story.append(Paragraph("Areas: " + ", ".join(rec.matched_domains) or "Areas: none", styles["BodyText"]))
        if rec.explanation:
            story.append(Paragraph(rec.explanation, styles["BodyText"]))
        if rec.evidence:
            story.append(Paragraph("Evidence: " + "; ".join(rec.evidence[:8]), styles["BodyText"]))
        story.append(Spacer(1, 8))
    SimpleDocTemplate(str(path), pagesize=letter, title="Security Network Report").build(story)
    return path


def write_reports(
    recs: list[Recommendation],
    out_dir: str | Path,
    profile_name: str,
    fmt: str = "both",
    graph: dict[str, Any] | None = None,
    orgs: list[dict[str, Any]] | None = None,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    written = []
    if fmt in ("md", "both"):
        p = out / f"report_{stamp}.md"
        p.write_text(render_markdown(recs, profile_name, graph, orgs), encoding="utf-8")
        written.append(p)
    if fmt in ("json", "both"):
        p = out / f"report_{stamp}.json"
        payload = {"profile": profile_name, "recommendations": [r.to_dict() for r in recs], "graph": graph or {}, "organizations": orgs or []}
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(p)
    return written
