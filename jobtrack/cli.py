import argparse
import os
import sys
from datetime import date

from . import dashboard, db, fetch, llm, validate

DEFAULT_RESUME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resume.md")


def _print_issues(issues):
    for i in issues:
        print(f"  ! {i}")


def _salary(job):
    lo, hi = job["salary_min"], job["salary_max"]
    if lo is None and hi is None:
        return "-"
    if lo is None or hi is None:
        return f"${lo if lo is not None else hi:,}"
    return f"${lo:,}-${hi:,}"


def cmd_add(conn, args):
    posting, url = fetch.load(args.source)
    print("Extracting fields with Claude...")
    try:
        raw, meta = llm.extract(posting)
    except llm.LLMError as e:
        db.log_call(conn, "extract", False, error=str(e))
        sys.exit(f"error: {e}")
    try:
        job, issues = validate.check_extraction(raw, posting, date.today())
    except validate.ValidationError as e:
        db.log_call(conn, "extract", False, meta, error=str(e))
        sys.exit(f"rejected model output: {e}")
    dropped = sum(i.startswith("dropped") for i in issues)
    db.log_call(conn, "extract", True, meta, claims=validate.count_claims(raw, "extract"),
                dropped=dropped)
    job_id = db.add_job(conn, job, posting, url or args.url, issues)
    print(f"#{job_id}  {job['role']} @ {job['company']}")
    print(f"  location: {job['location'] or '-'} ({job['work_mode'] or '?'})   "
          f"deadline: {job['deadline'] or '-'}   salary: {_salary(job)}")
    print(f"  skills: {', '.join(job['skills']) or '-'}")
    _print_issues(issues)


def cmd_match(conn, args):
    job = db.get_job(conn, args.id)
    if not job:
        sys.exit(f"no job #{args.id}")
    if not os.path.exists(args.resume):
        sys.exit(f"resume not found: {args.resume} (copy resume.example.md to resume.md)")
    with open(args.resume, encoding="utf-8") as f:
        resume = f.read()
    print(f"Matching resume against #{job['id']} {job['role']} @ {job['company']}...")
    try:
        raw, meta = llm.match(job["posting"], resume, job["skills"])
    except llm.LLMError as e:
        db.log_call(conn, "match", False, error=str(e))
        sys.exit(f"error: {e}")
    try:
        m, issues = validate.check_match(raw, resume, job["skills"])
    except validate.ValidationError as e:
        db.log_call(conn, "match", False, meta, error=str(e))
        sys.exit(f"rejected model output: {e}")
    db.log_call(conn, "match", True, meta, claims=validate.count_claims(raw, "match"),
                dropped=sum(i.startswith("dropped") for i in issues))
    db.add_match(conn, job["id"], m, issues)
    _show_match(m, issues)


def _show_match(m, issues):
    cov = f"{m['coverage']}%" if m["coverage"] is not None else "n/a"
    print(f"  model score: {m['score']}/100   verified skill coverage: {cov}")
    print(f"  {m['summary']}")
    for s in m["matched"]:
        print(f"  + {s['skill']}: \"{s['evidence']}\"")
    for s in m["missing"]:
        print(f"  - {s}")
    if m["bullets"]:
        print("  tailored bullets:")
        for b in m["bullets"]:
            print(f"    * {b['rewritten']}")
            print(f"      (from: {b['source']})")
    _print_issues(issues)


def cmd_list(conn, args):
    jobs = db.list_jobs(conn, args.status)
    if not jobs:
        print("no jobs yet; try: python -m jobtrack add samples/posting1.txt")
        return
    print(f"{'id':>3}  {'status':<10} {'deadline':<10}  {'score':>5}  role @ company")
    for j in jobs:
        m = db.latest_match(conn, j["id"])
        score = str(m["score"]) if m else "-"
        print(f"{j['id']:>3}  {j['status']:<10} {j['deadline'] or '-':<10}  {score:>5}  "
              f"{j['role']} @ {j['company']}")


def cmd_show(conn, args):
    job = db.get_job(conn, args.id)
    if not job:
        sys.exit(f"no job #{args.id}")
    print(f"#{job['id']}  {job['role']} @ {job['company']}   [{job['status']}]")
    print(f"  location: {job['location'] or '-'} ({job['work_mode'] or '?'})   "
          f"deadline: {job['deadline'] or '-'}   salary: {_salary(job)}")
    print(f"  skills: {', '.join(job['skills']) or '-'}")
    if job["url"]:
        print(f"  url: {job['url']}")
    _print_issues(job["issues"])
    print("  history:")
    for e in db.events(conn, job["id"]):
        print(f"    {e['at']}  {e['status']}" + (f"  ({e['note']})" if e["note"] else ""))
    m = db.latest_match(conn, job["id"])
    if m:
        print("  latest match:")
        _show_match(m, m["issues"])


def cmd_status(conn, args):
    if not db.get_job(conn, args.id):
        sys.exit(f"no job #{args.id}")
    db.set_status(conn, args.id, args.status, args.note)
    print(f"#{args.id} -> {args.status}")


def cmd_stale(conn, args):
    jobs = db.stale(conn, args.days)
    if not jobs:
        print(f"nothing applied more than {args.days} days ago without a reply")
    for j in jobs:
        print(f"#{j['id']}  {j['role']} @ {j['company']}  last update {j['updated_at'][:10]}")


def cmd_stats(conn, args):
    rows = db.call_stats(conn)
    if not rows:
        print("no model calls yet")
    for r in rows:
        rate = f"{100 * r['dropped'] / r['claims']:.0f}%" if r["claims"] else "n/a"
        print(f"{r['task']:<8} calls={r['calls']} ok={r['ok']} avg={r['avg_s']}s "
              f"claims={r['claims'] or 0} dropped={r['dropped'] or 0} ({rate})")


def cmd_dashboard(conn, args):
    path = dashboard.write(conn, args.out)
    print(f"wrote {path}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="jobtrack", description="Job application tracker powered by Claude Code")
    p.add_argument("--db", default=db.DEFAULT_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a posting from a file, URL, or - for stdin")
    a.add_argument("source")
    a.add_argument("--url", help="original URL, if source is a pasted file")
    a.set_defaults(fn=cmd_add)

    m = sub.add_parser("match", help="score your resume against a job")
    m.add_argument("id", type=int)
    m.add_argument("--resume", default=DEFAULT_RESUME)
    m.set_defaults(fn=cmd_match)

    ls = sub.add_parser("list", help="list jobs")
    ls.add_argument("--status", choices=db.STATUSES)
    ls.set_defaults(fn=cmd_list)

    sh = sub.add_parser("show", help="show one job")
    sh.add_argument("id", type=int)
    sh.set_defaults(fn=cmd_show)

    st = sub.add_parser("status", help="update a job's status")
    st.add_argument("id", type=int)
    st.add_argument("status", choices=db.STATUSES)
    st.add_argument("--note")
    st.set_defaults(fn=cmd_status)

    sl = sub.add_parser("stale", help="applied jobs with no reply")
    sl.add_argument("--days", type=int, default=14)
    sl.set_defaults(fn=cmd_stale)

    sub.add_parser("stats", help="model call and drop-rate stats").set_defaults(fn=cmd_stats)

    d = sub.add_parser("dashboard", help="write an HTML dashboard")
    d.add_argument("--out", default="dashboard.html")
    d.set_defaults(fn=cmd_dashboard)

    args = p.parse_args(argv)
    conn = db.connect(args.db)
    try:
        args.fn(conn, args)
    finally:
        conn.close()
