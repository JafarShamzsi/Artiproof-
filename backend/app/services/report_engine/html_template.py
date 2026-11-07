"""
HTML templates for PDF report generation.
"""

from datetime import datetime


def render_source_check_report(check_data: dict, narrative: str) -> str:
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
        claims_html += f"""
        <div style="border-left: 3px solid {v_color}; padding: 8px 12px; margin: 8px 0; background: #f8fafc;">
            <strong style="color: {v_color}; text-transform: uppercase; font-size: 11px;">{verdict}</strong>
            <span style="font-size: 11px; color: #64748b; margin-left: 8px;">{int(c.get('confidence', 0) * 100)}% confidence</span>
            <p style="margin: 4px 0 0; font-size: 13px;">{c.get('claim_text', '')}</p>
            <p style="margin: 4px 0 0; font-size: 12px; color: #64748b;">{c.get('explanation', '')}</p>
            {"<p style='margin: 4px 0 0; font-size: 12px; color: #10b981;'><em>Correct: " + c.get('true_version', '') + "</em></p>" if c.get('true_version') else ""}
        </div>"""

    citations_html = ""
    for ci in citations:
        icon = "&#x274C;" if ci.get("is_retracted") else ("&#x26A0;" if not ci.get("is_accessible", True) else "&#x2705;")
        citations_html += f"""
        <tr>
            <td style="padding: 6px 8px; font-size: 12px;">{icon} {ci.get('original_citation', '')[:60]}</td>
            <td style="padding: 6px 8px; font-size: 12px; text-align: center;">{"RETRACTED" if ci.get("is_retracted") else ("Inaccessible" if not ci.get("is_accessible", True) else "OK")}</td>
            <td style="padding: 6px 8px; font-size: 12px; text-align: center;">{ci.get('credibility_score', 0):.0f}</td>
        </tr>"""

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
        {"".join(f"<p style='color: #334155; font-size: 13px; line-height: 1.6;'>{p}</p>" for p in narrative.split(chr(10)+chr(10)) if p.strip())}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Claims Analysis</h2>" + claims_html if claims else ""}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Citation Health</h2><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #f1f5f9;'><th style='padding: 6px 8px; text-align: left; font-size: 12px;'>Citation</th><th style='padding: 6px 8px; text-align: center; font-size: 12px;'>Status</th><th style='padding: 6px 8px; text-align: center; font-size: 12px;'>Score</th></tr></thead><tbody>" + citations_html + "</tbody></table>" if citations else ""}
    """)


def render_researcher_report(profile_data: dict, narrative: str) -> str:
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
        pubs_html += f"""
        <tr>
            <td style="padding: 5px 8px; font-size: 11px;">{p.get('title', '')[:50]}</td>
            <td style="padding: 5px 8px; font-size: 11px;">{p.get('journal', '') or '—'}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: center;">{p.get('year', '—')}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: right;">{p.get('citation_count', 0)}</td>
            <td style="padding: 5px 8px; font-size: 11px; text-align: center;">{topic}</td>
        </tr>"""

    flags_html = ""
    if flags:
        flags_html = "<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Integrity Flags</h2><ul>"
        for f in flags:
            flags_html += f"<li style='font-size: 13px; color: #b45309; margin: 4px 0;'>{f}</li>"
        flags_html += "</ul>"

    return _wrap_html(f"Researcher Integrity Report — {name}", f"""
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #1e293b; margin: 0;">{name}</h2>
            <p style="color: #64748b; margin: 4px 0;">{institution}</p>
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
                <div style="font-size: 28px; font-weight: bold;">{profile_data.get('official_h_index') or '—'}</div>
            </div>
            <div style="flex: 1; background: #ecfdf5; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 14px; color: #10b981;">Adjusted h-index</div>
                <div style="font-size: 28px; font-weight: bold; color: #10b981;">{profile_data.get('adjusted_h_index') or '—'}</div>
            </div>
            <div style="flex: 1; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 14px; color: #64748b;">Self-citation</div>
                <div style="font-size: 28px; font-weight: bold;">{(profile_data.get('self_citation_rate') or 0) * 100:.1f}%</div>
            </div>
        </div>

        <h2 style="color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Executive Summary</h2>
        {"".join(f"<p style='color: #334155; font-size: 13px; line-height: 1.6;'>{p}</p>" for p in narrative.split(chr(10)+chr(10)) if p.strip())}

        {flags_html}

        {"<h2 style='color: #1e293b; font-size: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px;'>Publications</h2><table style='width: 100%; border-collapse: collapse;'><thead><tr style='background: #f1f5f9;'><th style='padding: 5px 8px; text-align: left; font-size: 11px;'>Title</th><th style='padding: 5px 8px; text-align: left; font-size: 11px;'>Journal</th><th style='padding: 5px 8px; text-align: center; font-size: 11px;'>Year</th><th style='padding: 5px 8px; text-align: right; font-size: 11px;'>Cites</th><th style='padding: 5px 8px; text-align: center; font-size: 11px;'>Topic</th></tr></thead><tbody>" + pubs_html + "</tbody></table>" if publications else ""}
    """)


def _wrap_html(title: str, body: str) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
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
    <div style="text-align: center; padding: 16px 0; border-bottom: 3px solid #10b981; margin-bottom: 24px;">
        <h1 style="color: #10b981; margin: 0; font-size: 24px;">ArtiProof</h1>
        <p style="color: #64748b; font-size: 12px; margin: 4px 0;">Research Integrity Platform</p>
    </div>
    <h1 style="color: #1e293b; font-size: 22px; text-align: center;">{title}</h1>
    <p style="text-align: center; color: #94a3b8; font-size: 12px;">Generated: {now}</p>
    {body}
    <div style="margin-top: 40px; padding-top: 16px; border-top: 1px solid #e2e8f0; text-align: center;">
        <p style="color: #94a3b8; font-size: 11px;">ArtiProof Research Integrity Platform — example.invalid</p>
    </div>
</body>
</html>"""
