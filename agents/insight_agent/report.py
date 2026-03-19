"""HTML report renderer for the Insight Agent."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

_RISK_COLOR = {"HIGH": "#e53e3e", "MEDIUM": "#dd6b20", "LOW": "#38a169"}
_RISK_BG = {"HIGH": "#fff5f5", "MEDIUM": "#fffaf0", "LOW": "#f0fff4"}

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    color: #1a202c;
    background: #f7fafc;
    padding: 24px;
    line-height: 1.6;
}
.card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }
h3 { font-size: 14px; font-weight: 600; margin: 16px 0 6px; color: #4a5568; }
.meta { color: #718096; font-size: 13px; margin-bottom: 6px; }
.meta span { margin-right: 18px; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .4px;
    text-transform: uppercase;
}
.risk-badge { color: #fff; }
a { color: #3182ce; text-decoration: none; }
a:hover { text-decoration: underline; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #edf2f7; text-align: left; padding: 8px 10px; font-weight: 600; color: #4a5568; }
td { padding: 7px 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:last-child td { border-bottom: none; }
.job-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 12px; overflow: hidden; }
.job-header { background: #edf2f7; padding: 8px 12px; display: flex; align-items: center; gap: 10px; }
.job-name { font-weight: 600; }
.job-stage { color: #718096; font-size: 12px; }
.job-body { padding: 12px; }
pre {
    background: #1a202c;
    color: #e2e8f0;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 12px;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
    margin-top: 6px;
}
.analysis-body { white-space: pre-wrap; font-size: 13px; line-height: 1.75; color: #2d3748; }
.history-row td:first-child { font-weight: 600; }
.footer { text-align: center; color: #a0aec0; font-size: 12px; margin-top: 8px; }
"""


def _esc(s: Any) -> str:
    return html.escape(str(s))


def _job_rows(failed_jobs: list[dict]) -> str:
    rows = []
    for j in failed_jobs:
        name = _esc(j.get("name", ""))
        stage = _esc(j.get("stage", ""))
        reason = _esc(j.get("failure_reason", ""))
        duration = _esc(j.get("duration", ""))
        url = _esc(j.get("web_url", "#"))
        log_tail = _esc(j.get("log_tail", "")[-2000:])
        rows.append(f"""
        <div class="job-card">
            <div class="job-header">
                <span class="job-name">{name}</span>
                <span class="job-stage">stage: {stage}</span>
                <span style="margin-left:auto;color:#718096;font-size:12px">{duration}s &nbsp;·&nbsp; <a href="{url}" target="_blank">View Job</a></span>
            </div>
            <div class="job-body">
                <div class="meta"><strong>Failure reason:</strong> {reason}</div>
                <div><strong>Log tail:</strong><pre>{log_tail}</pre></div>
            </div>
        </div>""")
    return "\n".join(rows)


def _history_rows(history: list[dict]) -> str:
    if not history:
        return "<tr><td colspan='4' style='color:#718096'>No recent failures found.</td></tr>"
    rows = []
    for p in history[:20]:
        pid = _esc(p.get("id", ""))
        branch = _esc(p.get("branch", ""))
        created = _esc(str(p.get("created_at", ""))[:10])
        duration = _esc(p.get("duration", ""))
        rows.append(
            f"<tr class='history-row'>"
            f"<td>#{pid}</td><td>{branch}</td><td>{created}</td><td>{duration}s</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def render_html_report(
    *,
    pipeline_id: int,
    branch: str,
    triggered_by: str,
    pipeline_url: str,
    failed_jobs: list[dict],
    analysis: str,
    risk: str,
    history: list[dict],
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    risk_color = _RISK_COLOR.get(risk, "#dd6b20")
    risk_bg = _RISK_BG.get(risk, "#fffaf0")

    job_section = _job_rows(failed_jobs)
    history_section = _history_rows(history)
    analysis_escaped = _esc(analysis)
    branch_esc = _esc(branch)
    triggered_esc = _esc(triggered_by)
    url_esc = _esc(pipeline_url)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pipeline #{pipeline_id} — Insight Report</title>
<style>{_CSS}</style>
</head>
<body>

<div class="card" style="border-left: 4px solid {risk_color}; background: {risk_bg}">
    <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap">
        <h1>Pipeline #{pipeline_id} Failed</h1>
        <span class="badge risk-badge" style="background:{risk_color}">{risk} recurrence risk</span>
    </div>
    <div class="meta" style="margin-top:8px">
        <span>Branch: <strong>{branch_esc}</strong></span>
        <span>Triggered by: <strong>{triggered_esc}</strong></span>
        <span>Failed jobs: <strong>{len(failed_jobs)}</strong></span>
        <span><a href="{url_esc}" target="_blank">View Pipeline →</a></span>
    </div>
</div>

<div class="card">
    <h2>Claude Analysis</h2>
    <div class="analysis-body">{analysis_escaped}</div>
</div>

<div class="card">
    <h2>Failed Jobs ({len(failed_jobs)})</h2>
    {job_section}
</div>

<div class="card">
    <h2>Recent Failure History ({len(history)} pipelines)</h2>
    <table>
        <thead>
            <tr><th>Pipeline</th><th>Branch</th><th>Date</th><th>Duration</th></tr>
        </thead>
        <tbody>
            {history_section}
        </tbody>
    </table>
</div>

<div class="footer">Generated by Insight Agent · {generated_at}</div>

</body>
</html>"""
