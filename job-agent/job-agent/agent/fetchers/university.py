"""Generic university / institute career-page fetcher.

You give it a page URL in the config. It downloads the page and collects links
whose text looks like a vacancy and mentions one of your keywords. This is a
best-effort, layout-independent approach: it will not be perfect on every site,
but it needs no per-site coding and is safe (read only, one request per page).

For sites where this misses too much, the cleanest fix is to point the URL at
the site's own filtered search results (for example the department's "vacancies"
page already filtered to your field).
"""

from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import Posting
from ..tagging import detect_type

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0; personal use)"}

# Link text containing any of these is treated as a likely vacancy link.
VACANCY_HINTS = [
    "postdoc", "post-doc", "postdoctoral", "fellow", "researcher", "research associate",
    "phd", "vacancy", "vacancies", "position", "job", "opening", "lecturer",
]


def fetch(page_cfg: dict, profile: dict) -> list:
    url = page_cfg.get("url", "")
    name = page_cfg.get("name", "university")
    default_type = page_cfg.get("type", "postdoc")
    if not url:
        return []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=40)
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    keywords = [k.lower() for k in profile.get("keywords", [])]
    results = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if len(text) < 8:
            continue
        low = text.lower()
        looks_like_vacancy = any(h in low for h in VACANCY_HINTS)
        matches_keyword = (not keywords) or any(k in low for k in keywords)
        if not (looks_like_vacancy and matches_keyword):
            continue
        link = urljoin(url, a["href"])
        if link in seen:
            continue
        seen.add(link)
        results.append(
            Posting(
                source=f"university:{name}",
                posting_type=detect_type(text, "", default_type),
                title=text,
                organization=name,
                location=page_cfg.get("country", ""),
                country=page_cfg.get("country", ""),
                url=link,
                description=text,
            )
        )
    return results
