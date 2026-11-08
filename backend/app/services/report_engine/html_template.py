"""
HTML templates for PDF report generation.

Every interpolation that can carry user- or model-supplied text routes
through ``_e()`` so a hostile claim/citation/annotation can't inject
``<script>`` or break out of an HTML attribute. Static numeric formats
(``{:.0f}``) and fixed dict lookups (``v_color``) skip escaping by
design.

CSS color values are interpolated unescaped (``html.escape`` does not
help in CSS context). They are constrained at write time by the schema
validator and re-checked here via ``_safe_color()`` as belt-and-braces;
anything that doesn't match the strict hex pattern falls back to the
ArtiProof default.
"""

import re
from datetime import datetime
from html import escape as _html_escape


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _e(value) -> str:
    """Escape a value for HTML body or quoted-attribute context. ``None``
    becomes an empty string; everything else is stringified first so a
    surprise int/float doesn't blow up at render time."""
    if value is None:
        return ""
    return _html_escape(str(value), quote=True)


def _safe_color(value: str | None, default: str) -> str:
    """Return ``value`` if it matches a strict hex-color pattern, else
    ``default``. Defends the renderer against CSS injection if a bad
    value somehow got past the schema validator (legacy DB rows, future
    schema regression)."""
    if isinstance(value, str) and _HEX_COLOR_RE.match(value):
        return value
    return default


def render_source_check_report(
    check_data: dict,
    narrative: str,
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """Render a source verification report as HTML."""
    title = check_data.get("input_title") or "Source Verification Report"
    score = check_data.get("overall_credibility_score", 0)
    ai_pct = check_data.get("ai_content_percentage", 0)
    misinfo = check_data.get("misinfo_claims_found", 0)
    claims = check_data.get("claims", [])
    citations = check_data.get("citations", [])

    score_color = "#10b981" if score >= 70 else "#eab308" if score >= 40 else "#ef4444"

    claims_html = ""
    for c in claims:
        verdict = c.get("verdict", "unverified")
        v_color = {"true": "#10b981", "false": "#ef4444", "misleading": "#eab308",
                   "partially_true": "#f59e0b", "unverified": "#71717a"}.get(verdict, "#71717a")
        true_version = c.get("true_version")
        claims_html += f"""
        <div style="border-left: 3px solid {v_color}; padding: 8px 12px; margin: 8px 0; background: #f8fafc;">
            <strong style="color: {v_color}; text-transform: uppercase; font-size: 11px;">{_e(verdict)}</strong>
            <span style="font-size: 11px; color: #64748b; margin-left: 8px;">{int(c.get('confidence', 0) * 100)}% confidence</span>
            <p style="margin: 4px 0 0; font-size: 13px;">{_e(c.get('claim_text', ''))}</p>
            <p style="margin: 4px 0 0; font-size: 12px; color: #64748b;">{_e(c.get('explanation', ''))}</p>
            {"<p style='margin: 4px 0 0; font-size: 12px; color: #10b981;'><em>Correct: " + _e(true_version) + "</em></p>" if true_version else ""}
        </div>"""

    citations_html = ""
    for ci in citations:
        icon = "&#x274C;" if ci.get("is_retracted") else ("&#x26A0;" if not ci.get("is_accessible", True) else "&#x2705;")
        # Slice raw, then escape — escaping first risks chopping an entity mid-sequence.
        citation_text = (ci.get("original_citation") or "")[:60]
        citations_html += f"""
        <tr>
            <td style="padding: 6px 8px; font-size: 12px;">{icon} {_e(citation_text)}</td>
            <td style="padding: 6px 8px; font-size: 12px; text-align: center;">{"RETRACTED" if ci.get("is_retracted") else ("Inaccessible" if not ci.get("is_accessible", True) else "OK")}</td>
            <td style="padding: 6px 8px; font-size: 12px; text-align: center;">{ci.get('credibility_score', 0):.0f}</td>
        </tr>"""

    narrative_html = "".join(
        f"<p style='color: #334155; font-size: 13px; line-height: 1.6;'>{_e(p)}</p>"
        for p in (narrative or "").split(chr(10) + chr(10))
        if p.strip()
    )

    return _wrap_html(title, f"""
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; width: 100px; height: 100px; border-radius: 50%;
                        border: 5px solid {score_color}; line-height: 90px; font-size: 36px;
                        font-weight: bold; color: {score_color};">{score:.0f}</div>
            <p style="margin-top: 8px; color: #64748b; font-size: 14px;">Credibility Score</p>
        </div>

        <div style="display: flex; gap: 16px; margin-bottom: 24px;">
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #3b82f6;">{ai_pct:.0f}%</div>
                <div style="font-size: 11px; color: #64748b;">AI Content</div>
            </div>
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #f59e0b;">{misinfo}</div>
                <div style="font-size: 11px; color: #64748b;">Misinfo Claims</div>
            </div>
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 24px; font-weight: bold; color: #8b5cf6;">{len(citations)}</div>
                <div style="font-size: 11px; color: #64748b;">Citations Checked</div>
            </div>
        </div>

        <h2 style="color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Executive Summary</h2>
        {narrative_html}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Claims Analysis</h2>" + claims_html if claims else ""}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Citation Health</h2><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #f1f5f9;'><th style='padding: 6px 8px; text-align: left; font-size: 12px;'>Citation</th><th style='padding: 6px 8px; text-align: center; font-size: 12px;'>Status</th><th style='padding: 6px 8px; text-align: center; font-size: 12px;'>Score</th></tr></thead><tbody>" + citations_html + "</tbody></table>" if citations else ""}
    """, branding, annotations)


def render_researcher_report(
    profile_data: dict,
    narrative: str,
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """Render a researcher integrity report as HTML."""
    name = profile_data.get("researcher_name", "Unknown")
    institution = profile_data.get("institution") or "Unknown"
    integrity = profile_data.get("integrity_score", 0)
    score_color = "#10b981" if integrity >= 70 else "#eab308" if integrity >= 40 else "#ef4444"

    publications = profile_data.get("publications", [])
    ring_flags = profile_data.get("citation_ring_flags") or {}
    flags = ring_flags.get("flags", [])

    pubs_html = ""
    for p in publications[:30]:
        topic = f"{p.get('topic_match_score', 0) * 100:.0f}%" if p.get("topic_match_score") is not None else "—"
        # Slice raw, escape after.
        pub_title = (p.get("title") or "")[:50]
        pubs_html += f"""
        <tr>
            <td style="padding: 5px 8px; font-size: 11px;">{_e(pub_title)}</td>
            <td style="padding: 5px 8px; font-size: 11px;">{_e(p.get('journal') or '—')}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: center;">{_e(p.get('year', '—'))}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: right;">{p.get('citation_count', 0)}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: center;">{topic}</td>
        </tr>"""

    flags_html = ""
    if flags:
        flags_html = "<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Integrity Flags</h2><ul>"
        for f in flags:
            flags_html += f"<li style='font-size: 13px; color: #b45309; margin: 4px 0;'>{_e(f)}</li>"
        flags_html += "</ul>"

    narrative_html = "".join(
        f"<p style='color: #334155; font-size: 13px; line-height: 1.6;'>{_e(p)}</p>"
        for p in (narrative or "").split(chr(10) + chr(10))
        if p.strip()
    )

    return _wrap_html(f"Researcher Integrity Report — {name}", f"""
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #1e293b; margin: 0;">{_e(name)}</h2>
            <p style="color: #64748b; margin: 4px 0;">{_e(institution)}</p>
        </div>

        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; width: 100px; height: 100px; border-radius: 50%;
                        border: 5px solid {score_color}; line-height: 90px; font-size: 36px;
                        font-weight: bold; color: {score_color};">{integrity:.0f}</div>
            <p style="margin-top: 8px; color: #64748b; font-size: 14px;">Integrity Score</p>
        </div>

        <div style="display: flex; gap: 16px; margin-bottom: 24px;">
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 14px; color: #64748b;">Official h-index</div>
                <div style="font-size: 28px; font-weight: bold;">{_e(profile_data.get('official_h_index') or '—')}</div>
            </div>
            <div style="flex: 1; background: #ecfdf5; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 14px; color: #10b981;">Adjusted h-index</div>
                <div style="font-size: 28px; font-weight: bold; color: #10b981;">{_e(profile_data.get('adjusted_h_index') or '—')}</div>
            </div>
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 14px; color: #64748b;">Self-citation</div>
                <div style="font-size: 28px; font-weight: bold;">{(profile_data.get('self_citation_rate') or 0) * 100:.1f}%</div>
            </div>
        </div>

        <h2 style="color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Executive Summary</h2>
        {narrative_html}

        {flags_html}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Publications</h2><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #f1f5f9;'><th style='padding: 5px 8px; text-align: left; font-size: 11px;'>Title</th><th style='padding: 5px 8px; text-align: left; font-size: 11px;'>Journal</th><th style='padding: 5px 8px; text-align: center; font-size: 11px;'>Year</th><th style='padding: 5px 8px; text-align: right; font-size: 11px;'>Cites</th><th style='padding: 5px 8px; text-align: center; font-size: 11px;'>Topic</th></tr></thead><tbody>" + pubs_html + "</tbody></table>" if publications else ""}
    """, branding, annotations)


def _branding_for(branding: dict | None) -> dict:
    """Resolve branding dict (potentially partial) to a fully-populated set
    of values the renderer can substitute. Falls back to ArtiProof's wine
    palette when keys are missing. Color values are constrained to the
    strict hex pattern via ``_safe_color`` so a stray non-hex value can't
    escape CSS context."""
    b = branding or {}
    return {
        "name": b.get("name") or "ArtiProof",
        "logo_url": b.get("logo_url"),
        "primary_color": _safe_color(b.get("primary_color"), "#7C2828"),
        # Footer underline + secondary accents. Falls back to the brand
        # amber so reports without an explicit override still feel branded.
        "secondary_color": _safe_color(b.get("secondary_color"), "#C8901E"),
        "tagline": b.get("tagline") or "Research Integrity Platform",
    }


def _annotations_html(annotations: list[dict] | None) -> str:
    """Render the annotations block — appears at the top of the body when
    a report has user-added notes. Empty when annotations is None/empty."""
    if not annotations:
        return ""
    items = []
    for a in annotations:
        if not isinstance(a, dict):
            continue
        text = (a.get("text") or "").strip()
        if not text:
            continue
        author = a.get("author_name") or "Author"
        when = a.get("created_at") or ""
        items.append(
            f"<div style='border-left: 3px solid #C8901E; padding: 6px 12px; "
            f"margin: 4px 0; background: #FBF5E8;'>"
            f"<p style='margin: 0; font-size: 12px; color: #94670F;'>"
            f"<strong>{_e(author)}</strong> "
            f"<span style='color: #B79E89;'>· {_e(when)}</span></p>"
            f"<p style='margin: 4px 0 0; font-size: 13px; color: #1A0808;'>{_e(text)}</p>"
            f"</div>"
        )
    if not items:
        return ""
    return (
        "<div style='margin-bottom: 24px;'>"
        "<p style='font-size: 11px; color: #6B5048; text-transform: uppercase; "
        "letter-spacing: 0.05em; margin: 0 0 6px;'>Notes</p>"
        + "".join(items) + "</div>"
    )


def _wrap_html(
    title: str,
    body: str,
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """Render the outer page chrome.

    `branding` (optional): {name, logo_url, primary_color, tagline}.
    Falls back to ArtiProof when null. White-label customers' org rows
    populate this; everyone else gets the default.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    b = _branding_for(branding)
    notes_html = _annotations_html(annotations)
    if b["logo_url"]:
        header_logo = (
            f'<img src="{_e(b["logo_url"])}" alt="{_e(b["name"])}" '
            f'style="max-height: 40px; max-width: 200px; margin-bottom: 4px;" />'
        )
    else:
        header_logo = (
            f'<h1 style="color: {b["primary_color"]}; margin: 0; font-size: 24px;">'
            f'{_e(b["name"])}</h1>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{_e(title)}</title>
<style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           color: #1e293b; line-height: 1.5; max-width: 800px; margin: 0 auto; }}
    table {{ border: 1px solid #e2e8f0; }}
    tr:nth-child(even) {{ background: #f8fafc; }}
    td, th {{ border-bottom: 1px solid #e2e8f0; }}
</style>
</head>
<body>
    <div style="text-align: center; padding: 16px 0; border-bottom: 3px solid {b['primary_color']}; margin-bottom: 24px;">
        {header_logo}
        <p style="color: #64748b; font-size: 12px; margin: 4px 0;">{_e(b['tagline'])}</p>
    </div>
    <h1 style="color: #1e293b; font-size: 22px; text-align: center;">{_e(title)}</h1>
    <p style="text-align: center; color: #94a3b8; font-size: 12px;">Generated: {now}</p>
    {notes_html}
    {body}
    <div style="margin-top: 40px; padding-top: 16px; border-top: 1px solid {b['secondary_color']}; text-align: center;">
        <p style="color: #94a3b8; font-size: 11px;">{_e(b['name'])} — generated by ArtiProof</p>
    </div>
</body>
</html>"""


# ─── New templates ────────────────────────────────────────────────────────


def render_executive_summary_report(
    check_data: dict,
    narrative: str,
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """1-page condensed source-check report.

    Drops the per-claim and per-citation tables — keeps the score, the
    narrative, and a one-line bullet summary of flagged findings. Designed
    to fit on a single A4 page.
    """
    score = check_data.get("overall_credibility_score", 0)
    ai_pct = check_data.get("ai_content_percentage", 0)
    misinfo = check_data.get("misinfo_claims_found", 0)
    citations = check_data.get("citations", []) or []
    claims = check_data.get("claims", []) or []
    title = check_data.get("input_title") or "Source Verification Report"
    score_color = (
        "#10b981" if score >= 70 else "#eab308" if score >= 40 else "#ef4444"
    )
    retracted = sum(1 for c in citations if c.get("is_retracted"))
    inaccessible = sum(1 for c in citations if not c.get("is_accessible", True))
    false_claims = sum(1 for c in claims if c.get("verdict") == "false")
    misleading = sum(1 for c in claims if c.get("verdict") == "misleading")

    narrative_html = "".join(
        f"<p style='color: #334155; font-size: 13px; line-height: 1.5; margin: 8px 0;'>{_e(p)}</p>"
        for p in (narrative or "").split(chr(10) + chr(10))
        if p.strip()
    )[:2400]

    body = f"""
        <div style="display: flex; align-items: center; gap: 24px; margin-bottom: 24px;">
            <div style="flex-shrink: 0; width: 92px; height: 92px; border-radius: 50%;
                        border: 4px solid {score_color}; display: flex; align-items: center;
                        justify-content: center; font-size: 32px; font-weight: bold;
                        color: {score_color};">{score:.0f}</div>
            <div style="flex: 1;">
                <p style="margin: 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280;">Credibility</p>
                <p style="margin: 4px 0; font-size: 14px; color: #1e293b;">
                    {ai_pct:.0f}% AI · {misinfo} misinfo · {len(citations)} citations
                </p>
            </div>
        </div>

        <h2 style="color: #1e293b; font-size: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-top: 16px;">Summary</h2>
        {narrative_html}

        <h2 style="color: #1e293b; font-size: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-top: 16px;">Findings</h2>
        <ul style="font-size: 13px; line-height: 1.6; color: #334155; padding-left: 20px;">
            {"<li><strong>" + str(false_claims) + "</strong> false claim" + ("s" if false_claims != 1 else "") + " identified.</li>" if false_claims else ""}
            {"<li><strong>" + str(misleading) + "</strong> misleading claim" + ("s" if misleading != 1 else "") + " identified.</li>" if misleading else ""}
            {"<li><strong>" + str(retracted) + "</strong> retracted citation" + ("s" if retracted != 1 else "") + ".</li>" if retracted else ""}
            {"<li><strong>" + str(inaccessible) + "</strong> inaccessible citation" + ("s" if inaccessible != 1 else "") + ".</li>" if inaccessible else ""}
            {"<li>AI content detected in <strong>" + f"{ai_pct:.0f}%" + "</strong> of analyzed paragraphs.</li>" if ai_pct >= 50 else ""}
            {"<li>No major findings — score and citations look clean.</li>" if (false_claims + misleading + retracted + inaccessible == 0 and ai_pct < 50) else ""}
        </ul>
    """
    return _wrap_html(f"Executive Summary: {title}", body, branding, annotations)


def render_comparison_report(
    items: list[dict],
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """Multi-source comparison. Each item is a check_data dict (same shape
    as the single-source renderer expects). Renders a single page with a
    side-by-side scoreboard and a table of the key metrics across all."""
    title = f"Source Comparison ({len(items)} sources)"

    rows = []
    for item in items:
        score = item.get("overall_credibility_score", 0) or 0
        ai_pct = item.get("ai_content_percentage", 0) or 0
        misinfo = item.get("misinfo_claims_found", 0) or 0
        citations = item.get("citations", []) or []
        retracted = sum(1 for c in citations if c.get("is_retracted"))
        score_color = (
            "#10b981" if score >= 70 else "#eab308" if score >= 40 else "#ef4444"
        )
        rows.append(f"""
            <tr>
                <td style="padding: 8px;"><strong>{_e(item.get('input_title') or 'Untitled')}</strong></td>
                <td style="padding: 8px; text-align: center; color: {score_color}; font-weight: 600;">{score:.0f}</td>
                <td style="padding: 8px; text-align: center;">{ai_pct:.0f}%</td>
                <td style="padding: 8px; text-align: center;">{misinfo}</td>
                <td style="padding: 8px; text-align: center;">{retracted}</td>
                <td style="padding: 8px; text-align: center;">{len(citations)}</td>
            </tr>
        """)

    body = f"""
        <p style="font-size: 13px; color: #334155;">
            Comparing {len(items)} source{"s" if len(items) != 1 else ""} side-by-side.
            Each row shows the credibility score and key counts.
        </p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr style="background: #f1f5f9;">
                    <th style="padding: 8px; text-align: left; font-size: 12px;">Source</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Score</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">AI %</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Misinfo</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Retracted</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Citations</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    """
    return _wrap_html(title, body, branding, annotations)


def render_institutional_audit_report(
    items: list[dict],
    branding: dict | None = None,
    annotations: list[dict] | None = None,
) -> str:
    """Institutional audit — many researchers, scoreboard layout."""
    title = f"Institutional Audit ({len(items)} researchers)"

    rows = []
    for item in items:
        name = item.get("researcher_name", "Unknown")
        institution = item.get("institution") or "—"
        official = item.get("official_h_index")
        adjusted = item.get("adjusted_h_index")
        integrity = item.get("integrity_score", 0) or 0
        self_cite = (item.get("self_citation_rate") or 0) * 100
        ring_flags = item.get("citation_ring_flags") or {}
        flag_count = len(ring_flags.get("flags") or [])
        score_color = (
            "#10b981" if integrity >= 70 else "#eab308" if integrity >= 40 else "#ef4444"
        )
        rows.append(f"""
            <tr>
                <td style="padding: 8px;"><strong>{_e(name)}</strong><br/>
                    <span style="font-size: 11px; color: #64748b;">{_e(institution)}</span></td>
                <td style="padding: 8px; text-align: center;">{_e(official) if official is not None else '—'}</td>
                <td style="padding: 8px; text-align: center;">{_e(adjusted) if adjusted is not None else '—'}</td>
                <td style="padding: 8px; text-align: center; color: {score_color}; font-weight: 600;">{integrity:.0f}</td>
                <td style="padding: 8px; text-align: center;">{self_cite:.1f}%</td>
                <td style="padding: 8px; text-align: center;">{flag_count}</td>
            </tr>
        """)

    body = f"""
        <p style="font-size: 13px; color: #334155;">
            Integrity audit across {len(items)} researcher{"s" if len(items) != 1 else ""}.
            Adjusted h-index reflects self-citation + ring-detection corrections.
        </p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
            <thead>
                <tr style="background: #f1f5f9;">
                    <th style="padding: 8px; text-align: left; font-size: 12px;">Researcher</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">h-index</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Adjusted</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Integrity</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Self-cite</th>
                    <th style="padding: 8px; text-align: center; font-size: 12px;">Flags</th>
                </tr>
            </thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    """
    return _wrap_html(title, body, branding, annotations)
