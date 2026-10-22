"""Turn a file path, URL or stdin into plain posting text. No model involved."""
import sys
import urllib.request
from html.parser import HTMLParser

MAX_CHARS = 30_000


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html):
    p = _TextExtractor()
    p.feed(html)
    return "\n".join(p.parts)


def load(source):
    """Return (text, url_or_None)."""
    if source == "-":
        text, url = sys.stdin.read(), None
    elif source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0 jobtrack"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
        text, url = html_to_text(body), source
    else:
        with open(source, encoding="utf-8") as f:
            text, url = f.read(), None
    text = text.strip()
    if len(text) < 100:
        raise ValueError("posting text is too short; if this is a JS-heavy site, paste the text into a file")
    return text[:MAX_CHARS], url
