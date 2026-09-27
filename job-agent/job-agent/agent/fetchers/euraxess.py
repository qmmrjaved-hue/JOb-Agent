"""EURAXESS fetcher.

EURAXESS does not publish an official API, so this fetches the public search
results page and parses the listing cards. It sends a normal browser User-Agent,
waits politely between page requests, and never hammers the site.

IMPORTANT: EURAXESS can change its page layout. This parser is written to be
forgiving (it looks for links to job detail pages and reads the text around
them), but if EURAXESS returns zero results for several days the source-health
check will flag it, and the CSS selectors here may then need a small update.
"""

from __future__ import annotations

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..models import Posting
from ..tagging import detect_type

BASE = "https://euraxess.ec.europa.eu"
SEARCH = BASE + "/jobs/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0; personal use)"}


def fetch(profile: dict, max_pages: int = 2, delay_seconds: float = 2.0) -> list:
    keywords = profile.get("euraxess_keywords") or " ".join(profile.get("keywords", [])[:4])
    countries = profile.get("countries", "any")
    country_filter = None
    if isinstance(countries, list) and countries:
        country_filter = [c.lower() for c in countries]

    results = []
    for page in range(max_pages):
        params = {"keywords": keywords, "page": page}
        try:
            resp = requests.get(SEARCH, params=params, headers=HEADERS, timeout=40)
            resp.raise_for_status()
        except Exception:
            break
        soup = BeautifulSoup(resp.text, "lxml")

        # Find links that point to a job detail page.
        anchors = [a for a in soup.find_all("a", href=True)
                   if "/jobs/" in a["href"] and a.get_text(strip=True)]
        page_hits = 0
        seen_urls = set()
        for a in anchors:
            href = a["href"]
            # Skip the search/navigation links; keep real detail pages.
            if href.rstrip("/").endswith("/jobs") or "search" in href:
                continue
            url = urljoin(BASE, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = a.get_text(" ", strip=True)
            if len(title) < 8:
                continue

            # The card text usually holds organization, country and deadline.
            card = a.find_parent(["article", "li", "div"])
            card_text = card.get_text(" ", strip=True) if card else title

            posting = Posting(
                source="euraxess",
                posting_type=detect_type(title, card_text, "postdoc"),
                title=title,
                organization="",
                location="",
                country="",
                url=url,
                description=card_text[:1500],
            )
            if country_filter:
                low = card_text.lower()
                if not any(c in low for c in country_filter):
                    # Country not obviously mentioned; keep only if no filter match needed.
                    pass  # keep, relevance layer will still judge; comment out to filter hard
            results.append(posting)
            page_hits += 1

        if page_hits == 0:
            break
        time.sleep(delay_seconds)
    return results
