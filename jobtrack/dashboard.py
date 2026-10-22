"""Static HTML dashboard. Plain code, no model."""
import os
from collections import Counter
from datetime import date
from html import escape

from . import db

CSS = """
:root { --bg:#fafaf9; --fg:#1c1917; --muted:#78716c; --card:#fff; --line:#e7e5e4;
        --accent:#2563eb; --warn:#b45309; --bad:#b91c1c; --good:#15803d; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#1c1917; --fg:#f5f5f4; --muted:#a8a29e; --card:#292524; --line:#44403c;
          --accent:#60a5fa; --warn:#fbbf24; --bad:#f87171; --good:#4ade80; }
}
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px; background:var(--bg); color:var(--fg);
       font:15px/1.5 system-ui, sans-serif; }
main { max-width:1000px; margin:0 auto; }
h1 { margin:0 0 4px; font-size:24px; }
.sub { color:var(--muted); margin-bottom:20px; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:10px; margin-bottom:24px; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
.tile b { display:block; font-size:22px; }
.tile span { color:var(--muted); font-size:13px; }
.wrap { overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:8px; }
table { border-collapse:collapse; width:100%; min-width:640px; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
.pill { font-size:12px; padding:1px 8px; border-radius:99px; border:1px solid var(--line); white-space:nowrap; }
.stale { color:var(--warn); font-weight:600; }
.soon { color:var(--bad); font-weight:600; }
.skills { color:var(--muted); font-size:13px; }
"""


def write(conn, out_path):
    jobs = db.list_jobs(conn)
    stale_ids = {j["id"] for j in db.stale(conn)}
    counts = Counter(j["status"] for j in jobs)
    today = date.today()

    tiles = [("total", len(jobs))] + [(s, counts.get(s, 0)) for s in db.STATUSES if counts.get(s)]
    tiles.append(("need follow-up", len(stale_ids)))
    tile_html = "".join(f'<div class="tile"><b>{n}</b><span>{escape(k)}</span></div>'
                        for k, n in tiles)

    rows = []
    for j in jobs:
        m = db.latest_match(conn, j["id"])
        deadline = j["deadline"] or ""
        cls = ""
        if deadline and j["status"] == "saved":
            days_left = (date.fromisoformat(deadline) - today).days
            cls = "soon" if 0 <= days_left <= 7 else ""
        status = escape(j["status"]) + (' <span class="stale">follow up</span>'
                                        if j["id"] in stale_ids else "")
        score = f"{m['score']} <span class='skills'>({m['coverage']}% verified)</span>" if m else "-"
        rows.append(
            f"<tr><td>{j['id']}</td>"
            f"<td><b>{escape(j['role'])}</b><br>{escape(j['company'])}"
            f"<div class='skills'>{escape(', '.join(j['skills'][:8]))}</div></td>"
            f"<td><span class='pill'>{status}</span></td>"
            f"<td class='{cls}'>{escape(deadline) or '-'}</td>"
            f"<td>{score}</td>"
            f"<td>{escape(j['location'] or '-')}</td></tr>")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Tracker</title><style>{CSS}</style></head>
<body><main>
<h1>Job Tracker</h1>
<div class="sub">Generated {today.isoformat()}</div>
<div class="tiles">{tile_html}</div>
<div class="wrap"><table>
<thead><tr><th>#</th><th>Role</th><th>Status</th><th>Deadline</th><th>Fit</th><th>Location</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="6">No jobs yet.</td></tr>'}</tbody>
</table></div>
</main></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(out_path)
