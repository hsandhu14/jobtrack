"""Static HTML dashboard. Plain code, no model."""
import os
from collections import Counter
from datetime import date
from html import escape

from . import db, logos

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

STATUS_COLORS = {
    "saved": "#94a3b8", "applied": "#3b82f6", "interview": "#a855f7", "offer": "#22c55e",
    "rejected": "#ef4444", "ghosted": "#f59e0b", "withdrawn": "#64748b",
}

CSS = """
:root {
  --bg:#f6f7fb; --fg:#0f172a; --muted:#64748b; --card:#ffffff; --line:#e2e8f0;
  --chip:#f1f5f9; --good:#16a34a; --good-bg:#dcfce7; --warn:#d97706; --bad:#dc2626;
  --hero1:#4f46e5; --hero2:#0ea5e9; --ring-track:#e2e8f0; --shadow:0 1px 2px rgba(15,23,42,.06),0 4px 16px rgba(15,23,42,.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0b1020; --fg:#e2e8f0; --muted:#94a3b8; --card:#131a2e; --line:#1f2a44;
    --chip:#1b2440; --good:#4ade80; --good-bg:#14532d; --warn:#fbbf24; --bad:#f87171;
    --hero1:#4338ca; --hero2:#0369a1; --ring-track:#1f2a44; --shadow:0 1px 2px rgba(0,0,0,.4);
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 "Inter", system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color:inherit; text-decoration:none; }
main { max-width:1120px; margin:0 auto; padding:0 16px 48px; }

.hero { background:linear-gradient(120deg,var(--hero1),var(--hero2)); color:#fff; padding:32px 16px 72px; }
.hero-in { max-width:1120px; margin:0 auto; display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap; }
.hero h1 { margin:0; font-size:30px; letter-spacing:-.02em; }
.hero p { margin:4px 0 0; opacity:.85; }
.hero .date { font-size:13px; opacity:.8; }

.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:-48px; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; box-shadow:var(--shadow); }
.tile b { display:block; font-size:28px; letter-spacing:-.02em; }
.tile span { color:var(--muted); font-size:13px; }
.tile.alert b { color:var(--warn); }

h2 { font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:32px 0 12px; }

.pipe { display:flex; height:12px; border-radius:99px; overflow:hidden; background:var(--line); }
.pipe i { display:block; height:100%; }
.legend { display:flex; flex-wrap:wrap; gap:14px; margin-top:10px; font-size:13px; color:var(--muted); }
.legend span::before { content:""; display:inline-block; width:9px; height:9px; border-radius:50%; background:var(--c); margin-right:6px; }

.targets { display:grid; grid-template-columns:repeat(auto-fill,minmax(96px,1fr)); gap:10px; }
.target { position:relative; display:flex; flex-direction:column; align-items:center; gap:8px; padding:14px 6px 10px;
  background:var(--card); border:1px solid var(--line); border-radius:14px; font-size:12px; color:var(--muted);
  transition:transform .15s, box-shadow .15s, border-color .15s; }
.target:hover { transform:translateY(-2px); box-shadow:var(--shadow); border-color:var(--hero2); color:var(--fg); }
.target .logo { transition:transform .15s; }
.target:hover .logo { transform:scale(1.08); }
.target.on { color:var(--fg); border-color:var(--good); }
.target.on::after { content:"\\2713"; position:absolute; top:6px; right:8px; width:18px; height:18px; border-radius:50%;
  background:var(--good); color:#fff; font-size:11px; line-height:18px; text-align:center; font-weight:700; }

.logo { position:relative; flex:none; width:var(--s,44px); height:var(--s,44px); border-radius:12px; overflow:hidden;
  background:hsl(var(--h) 65% 50%); color:#fff; display:grid; place-items:center; font-weight:700; font-size:calc(var(--s,44px)*.38); }
.logo img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; background:#fff; padding:15%; }

.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px; box-shadow:var(--shadow);
  display:flex; flex-direction:column; gap:12px; border-top:4px solid var(--c); }
.head { display:flex; gap:12px; align-items:flex-start; }
.head .who { flex:1; min-width:0; }
.role { font-weight:650; line-height:1.3; }
.meta { color:var(--muted); font-size:13px; }
.ring { --p:0; flex:none; width:52px; height:52px; border-radius:50%; display:grid; place-items:center;
  background:conic-gradient(var(--rc) calc(var(--p)*1%), var(--ring-track) 0); }
.ring b { width:42px; height:42px; border-radius:50%; background:var(--card); display:grid; place-items:center; font-size:14px; }
.ring.none b { color:var(--muted); font-weight:400; }
.row { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
.pill { font-size:12px; font-weight:600; padding:2px 10px; border-radius:99px; color:#fff; background:var(--c); text-transform:capitalize; }
.flag { font-size:12px; font-weight:600; color:var(--warn); }
.chip { font-size:12px; padding:2px 8px; border-radius:6px; background:var(--chip); color:var(--muted); }
.chip.hit { background:var(--good-bg); color:var(--good); }
.chip.miss { background:transparent; border:1px dashed var(--line); }
.foot { display:flex; justify-content:space-between; gap:8px; font-size:13px; color:var(--muted); border-top:1px solid var(--line); padding-top:10px; margin-top:auto; }
.soon { color:var(--bad); font-weight:600; }
.cov { font-size:12px; color:var(--muted); }
.empty { padding:40px; text-align:center; color:var(--muted); background:var(--card); border:1px dashed var(--line); border-radius:16px; }
"""


def _logo(company, url=None, size=44):
    initials, hue = logos.monogram(company)
    domain = logos.domain_for(company, url)
    img = (f'<img src="{escape(logos.icon_url(domain))}" alt="" loading="lazy" '
           f'onerror="this.remove()">' if domain else "")
    return (f'<span class="logo" style="--h:{hue};--s:{size}px" aria-hidden="true">'
            f'{escape(initials)}{img}</span>')


def _deadline(deadline, status, today):
    if not deadline:
        return "No deadline"
    if status != "saved":
        return f"Deadline {escape(deadline)}"
    days = (date.fromisoformat(deadline) - today).days
    if days < 0:
        return f"Closed {escape(deadline)}"
    label = "Due today" if days == 0 else f"{days} day{'s' * (days != 1)} left"
    cls = " class='soon'" if days <= 7 else ""
    return f"<span{cls}>{label}</span>"


def _salary(job):
    lo, hi = job["salary_min"], job["salary_max"]
    if lo is None and hi is None:
        return ""
    k = lambda v: f"${v // 1000}k"
    if lo is None or hi is None or lo == hi:
        return k(lo if lo is not None else hi)
    return f"{k(lo)}–{k(hi)}"


def _card(job, match, is_stale, today):
    color = STATUS_COLORS.get(job["status"], "#94a3b8")
    where = " · ".join(escape(x) for x in [job["company"], job["location"] or "",
                                           (job["work_mode"] or "").capitalize()] if x)
    if match:
        p = match["score"]
        rc = "#22c55e" if p >= 75 else "#f59e0b" if p >= 50 else "#ef4444"
        ring = f'<div class="ring" style="--p:{p};--rc:{rc}" title="Model fit score"><b>{p}</b></div>'
        hits = {m["skill"] for m in match["matched"]}
        chips = "".join(f'<span class="chip {"hit" if s in hits else "miss"}">'
                        f'{"&#10003; " if s in hits else ""}{escape(s)}</span>' for s in job["skills"][:10])
        cov = f'<span class="cov">{match["coverage"]}% of skills verified in resume</span>' \
            if match["coverage"] is not None else ""
    else:
        ring = '<div class="ring none" style="--rc:transparent" title="Run jobtrack match"><b>&ndash;</b></div>'
        chips = "".join(f'<span class="chip">{escape(s)}</span>' for s in job["skills"][:10])
        cov = '<span class="cov">Not matched yet</span>'
    flag = '<span class="flag">&#9888; Follow up</span>' if is_stale else ""
    link = f'<a href="{escape(job["url"])}">Posting &rarr;</a>' if job["url"] else f"#{job['id']}"
    return f"""<article class="card" style="--c:{color}">
  <div class="head">{_logo(job["company"], job["url"])}
    <div class="who"><div class="role">{escape(job["role"])}</div><div class="meta">{where}</div></div>
    {ring}</div>
  <div class="row"><span class="pill">{escape(job["status"])}</span>{flag}{cov}</div>
  <div class="row">{chips}</div>
  <div class="foot"><span>{_deadline(job["deadline"], job["status"], today)}</span>
    <span>{_salary(job)}</span><span>{link}</span></div>
</article>"""


def write(conn, out_path):
    jobs = db.list_jobs(conn)
    stale_ids = {j["id"] for j in db.stale(conn)}
    counts = Counter(j["status"] for j in jobs)
    today = date.today()
    matches = {j["id"]: db.latest_match(conn, j["id"]) for j in jobs}
    scores = [m["score"] for m in matches.values() if m]

    active = sum(counts[s] for s in ("applied", "interview"))
    tiles = [("Tracked", len(jobs), ""), ("Active applications", active, ""),
             ("Interviews", counts["interview"], ""), ("Offers", counts["offer"], ""),
             ("Avg fit score", round(sum(scores) / len(scores)) if scores else "–", ""),
             ("Need follow-up", len(stale_ids), "alert" if stale_ids else "")]
    tile_html = "".join(f'<div class="tile {cls}"><b>{v}</b><span>{k}</span></div>'
                        for k, v, cls in tiles)

    total = len(jobs) or 1
    pipe = "".join(f'<i style="width:{100 * counts[s] / total:.2f}%;background:{c}" title="{s}"></i>'
                   for s, c in STATUS_COLORS.items() if counts[s])
    legend = "".join(f'<span style="--c:{c}">{s.capitalize()} {counts[s]}</span>'
                     for s, c in STATUS_COLORS.items() if counts[s])

    tracked = {logos.normalize(j["company"]) for j in jobs}
    targets = []
    for name in logos.load_targets(REPO_ROOT):
        on = " on" if logos.normalize(name) in tracked else ""
        href = logos.careers_url(name)
        tag, attr = ("a", f' href="{escape(href)}" target="_blank" rel="noopener"') if href else ("div", "")
        targets.append(f'<{tag} class="target{on}"{attr}>{_logo(name, size=40)}'
                       f'<span>{escape(name)}</span></{tag}>')

    order = {s: i for i, s in enumerate(["interview", "offer", "applied", "saved", "ghosted",
                                         "rejected", "withdrawn"])}
    jobs.sort(key=lambda j: (order.get(j["status"], 9), -(matches[j["id"]] or {"score": -1})["score"]))
    cards = "".join(_card(j, matches[j["id"]], j["id"] in stale_ids, today) for j in jobs) \
        or '<div class="empty">No jobs yet. Run <code>python -m jobtrack add posting.txt</code></div>'

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Tracker</title><style>{CSS}</style></head>
<body>
<header class="hero"><div class="hero-in">
  <div><h1>Job Tracker</h1><p>Postings read by Claude, every claim checked against the source.</p></div>
  <div class="date">Updated {today.strftime("%B %d, %Y").replace(" 0", " ")}</div>
</div></header>
<main>
<section class="tiles">{tile_html}</section>
<h2>Pipeline</h2>
<div class="pipe">{pipe}</div><div class="legend">{legend}</div>
<h2>Target companies</h2>
<div class="targets">{''.join(targets)}</div>
<h2>Applications</h2>
<div class="cards">{cards}</div>
</main></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(out_path)
