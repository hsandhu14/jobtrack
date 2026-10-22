"""Company -> domain lookup for dashboard logos. Plain code, no model.

Logos are not stored in the repo; the dashboard loads each company's icon
from its domain at view time and falls back to a colored monogram.
"""
import hashlib
import os
import re
from urllib.parse import quote, urlparse

# name -> (domain, careers page)
KNOWN = {
    "microsoft": ("microsoft.com", "https://careers.microsoft.com"),
    "amazon": ("amazon.com", "https://www.amazon.jobs"),
    "aws": ("aws.amazon.com", "https://www.amazon.jobs"),
    "google": ("google.com", "https://www.google.com/about/careers/applications/"),
    "alphabet": ("abc.xyz", "https://www.google.com/about/careers/applications/"),
    "meta": ("meta.com", "https://www.metacareers.com"),
    "apple": ("apple.com", "https://jobs.apple.com"),
    "netflix": ("netflix.com", "https://jobs.netflix.com"),
    "nvidia": ("nvidia.com", "https://www.nvidia.com/en-us/about-nvidia/careers/"),
    "stripe": ("stripe.com", "https://stripe.com/jobs"),
    "salesforce": ("salesforce.com", "https://careers.salesforce.com"),
    "expedia": ("expediagroup.com", "https://careers.expediagroup.com"),
    "expedia group": ("expediagroup.com", "https://careers.expediagroup.com"),
    "zillow": ("zillow.com", "https://www.zillow.com/careers/"),
    "uber": ("uber.com", "https://www.uber.com/us/en/careers/"),
    "airbnb": ("airbnb.com", "https://careers.airbnb.com"),
    "databricks": ("databricks.com", "https://www.databricks.com/company/careers"),
    "anthropic": ("anthropic.com", "https://www.anthropic.com/careers"),
    "openai": ("openai.com", "https://openai.com/careers"),
    "t-mobile": ("t-mobile.com", "https://careers.t-mobile.com"),
    "boeing": ("boeing.com", "https://jobs.boeing.com"),
    "adobe": ("adobe.com", None),
    "oracle": ("oracle.com", None),
    "ibm": ("ibm.com", None),
    "intel": ("intel.com", None),
    "amd": ("amd.com", None),
    "qualcomm": ("qualcomm.com", None),
    "cisco": ("cisco.com", None),
    "tesla": ("tesla.com", None),
    "spotify": ("spotify.com", None),
    "shopify": ("shopify.com", None),
    "snowflake": ("snowflake.com", None),
    "linkedin": ("linkedin.com", None),
    "github": ("github.com", None),
    "atlassian": ("atlassian.com", None),
    "doordash": ("doordash.com", None),
    "lyft": ("lyft.com", None),
    "pinterest": ("pinterest.com", None),
    "palantir": ("palantir.com", None),
    "coinbase": ("coinbase.com", None),
    "robinhood": ("robinhood.com", None),
    "figma": ("figma.com", None),
    "cloudflare": ("cloudflare.com", None),
    "datadog": ("datadoghq.com", None),
    "mongodb": ("mongodb.com", None),
    "redfin": ("redfin.com", None),
    "tableau": ("tableau.com", None),
    "workday": ("workday.com", None),
    "costco": ("costco.com", None),
    "starbucks": ("starbucks.com", None),
    "nike": ("nike.com", None),
}

# Popular SWE employers shown in the dashboard's target strip.
# Override with a targets.txt file (one company per line) in the repo root.
DEFAULT_TARGETS = ["Microsoft", "Amazon", "Google", "Meta", "Apple", "Nvidia", "Netflix",
                   "Stripe", "Salesforce", "Databricks", "Anthropic", "Expedia", "Zillow",
                   "T-Mobile", "Uber", "Airbnb"]

# Hosts that belong to job boards, not the employer, so they say nothing about the logo.
JOB_BOARDS = ("greenhouse.io", "lever.co", "linkedin.com", "indeed.com", "myworkdayjobs.com",
              "workday.com", "ashbyhq.com", "smartrecruiters.com", "icims.com", "glassdoor.com",
              "handshake", "wellfound.com", "ziprecruiter.com", "jobvite.com")

_SUFFIX = re.compile(r"[,.]?\s+(inc|llc|ltd|corp|corporation|co|company|technologies|labs?)\.?$")


def normalize(company):
    name = company.lower().strip()
    while True:
        stripped = _SUFFIX.sub("", name).strip()
        if stripped == name:
            return name
        name = stripped


def domain_for(company, url=None):
    """Best-guess employer domain, or None."""
    entry = KNOWN.get(normalize(company))
    if entry:
        return entry[0]
    if url:
        host = (urlparse(url).hostname or "").removeprefix("www.")
        if host and not any(board in host for board in JOB_BOARDS):
            parts = host.split(".")
            return ".".join(parts[-2:]) if len(parts) > 2 else host
    return None


def careers_url(company):
    entry = KNOWN.get(normalize(company))
    return entry[1] if entry else None


def icon_url(domain):
    return f"https://www.google.com/s2/favicons?domain={quote(domain)}&sz=128"


def monogram(company):
    """Initials plus a stable hue, for the fallback badge."""
    words = [w for w in re.split(r"[\s\-&]+", company) if w]
    initials = "".join(w[0] for w in words[:2]).upper() or "?"
    hue = int(hashlib.md5(company.lower().encode()).hexdigest(), 16) % 360
    return initials, hue


def load_targets(repo_root):
    path = os.path.join(repo_root, "targets.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if names:
            return names
    return DEFAULT_TARGETS
