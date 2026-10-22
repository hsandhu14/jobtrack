"""The only module that talks to the model.

Everything returned from here is UNTRUSTED. Callers must pass it through
validate.py before storing or showing it.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time

MODEL = os.environ.get("JOBTRACK_MODEL", "sonnet")
TIMEOUT_S = 240


class LLMError(Exception):
    pass


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "role": {"type": "string"},
        "location": {"type": ["string", "null"]},
        "work_mode": {"type": ["string", "null"], "enum": ["onsite", "hybrid", "remote", None]},
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "deadline": {"type": ["string", "null"]},
        "salary_min": {"type": ["integer", "null"]},
        "salary_max": {"type": ["integer", "null"]},
    },
    "required": ["company", "role", "location", "work_mode", "required_skills",
                 "deadline", "salary_min", "salary_max"],
}

EXTRACT_SYSTEM = """You are the extraction step of a job-application tracker.
The user message contains one job posting. Return its fields as JSON matching the schema.

Rules:
- Use null for anything the posting does not state. Never guess.
- required_skills: concrete technical skills, languages, frameworks and tools.
  Copy each one using the exact wording from the posting. No soft skills.
- deadline: YYYY-MM-DD, or null if no application deadline is stated.
- salary_min / salary_max: annual USD as integers, or null. Convert hourly by x2080.
- work_mode: onsite, hybrid, remote, or null."""

MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "summary": {"type": "string"},
        "matched": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"skill": {"type": "string"}, "evidence": {"type": "string"}},
                "required": ["skill", "evidence"],
            },
        },
        "bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"source": {"type": "string"}, "rewritten": {"type": "string"}},
                "required": ["source", "rewritten"],
            },
        },
    },
    "required": ["score", "summary", "matched", "bullets"],
}

MATCH_SYSTEM = """You are the matching step of a job-application tracker.
The user message contains <skills> (the job's required skills), <posting> and <resume>.

Return JSON matching the schema:
- score: 0-100, how well the resume fits the posting.
- summary: 1-2 sentences explaining the score.
- matched: one entry per skill from <skills> that the resume demonstrates.
  "skill" must be copied exactly from <skills>. "evidence" must be an exact,
  verbatim quote from <resume> (a phrase or line) that shows it.
- bullets: up to 3 lines from the resume rewritten to target this posting.
  "source" must be copied verbatim from <resume>. "rewritten" may reword and
  reorder but must not add any fact, number, tool or claim not in "source"."""


def find_claude():
    """Locate the Claude Code CLI: env var, PATH, then the VS Code extension's bundled binary."""
    if os.environ.get("JOBTRACK_CLAUDE"):
        return os.environ["JOBTRACK_CLAUDE"]
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    pattern = os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude*")
    candidates = glob.glob(pattern)
    if candidates:
        return max(candidates, key=os.path.getmtime)
    raise LLMError("Claude Code CLI not found. Install it or set JOBTRACK_CLAUDE.")


def parse_envelope(stdout):
    """Pull the structured output out of `claude -p --output-format json`."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"CLI did not return JSON: {stdout[:200]!r}") from e
    if envelope.get("is_error"):
        raise LLMError(f"model call failed: {envelope.get('result')}")
    out = envelope.get("structured_output")
    if out is None:
        try:
            out = json.loads(envelope.get("result") or "")
        except json.JSONDecodeError as e:
            raise LLMError("no structured output in response") from e
    if not isinstance(out, dict):
        raise LLMError("structured output is not an object")
    return out, {"cost_usd": envelope.get("total_cost_usd")}


def call(system, user_text, schema):
    """Run one headless, tool-less Claude call. Returns (raw_output, meta)."""
    cmd = [
        find_claude(), "-p", "Process the input above and respond with the JSON.",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt", system,
        "--tools", "",
        "--no-session-persistence",
        "--model", MODEL,
    ]
    start = time.monotonic()
    try:
        # Run from a temp dir so no project CLAUDE.md leaks into the model's context.
        proc = subprocess.run(cmd, input=user_text, capture_output=True, text=True,
                              encoding="utf-8", timeout=TIMEOUT_S, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"model call timed out after {TIMEOUT_S}s") from e
    if proc.returncode != 0 and not proc.stdout:
        raise LLMError(f"CLI exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    out, meta = parse_envelope(proc.stdout)
    meta["duration_ms"] = int((time.monotonic() - start) * 1000)
    return out, meta


def extract(posting):
    return call(EXTRACT_SYSTEM, posting, EXTRACT_SCHEMA)


def match(posting, resume, skills):
    user = (f"<skills>\n" + "\n".join(skills) + "\n</skills>\n\n"
            f"<posting>\n{posting}\n</posting>\n\n<resume>\n{resume}\n</resume>")
    return call(MATCH_SYSTEM, user, MATCH_SCHEMA)
