"""Adzuna fetcher. Uses the free public Adzuna API.

Get a free app id and key at https://developer.adzuna.com/ and put them in your
environment as ADZUNA_APP_ID and ADZUNA_APP_KEY (config.yaml reads them).

Note: Adzuna only covers a fixed set of countries (listed below). For countries
it does not cover (for example Sweden), rely on the EURAXESS and university
fetchers instead.
"""

from __future__ import annotations

import requests

from ..models import Posting
from ..tagging import detect_type

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Countries Adzuna supports (two-letter codes).
SUPPORTED = {
    "gb", "us", "at", "au", "be", "br", "ca", "ch", "de", "es",
    "fr", "in", "it", "mx", "nl", "nz", "pl", "sg", "za",
}


def fetch(profile: dict, adzuna_cfg: dict, max_days_old: int = 3) -> list:
    app_id = (adzuna_cfg.get("app_id") or "").strip()
    app_key = (adzuna_cfg.get("app_key") or "").strip()
    if not (app_id and app_key):
        return []

    what = profile.get("adzuna_what") or " ".join(profile.get("keywords", [])[:4])
    countries = profile.get("countries", "any")
    if countries in ("any", "", None) or not isinstance(countries, list):
        country_codes = list(SUPPORTED)
    else:
        country_codes = [c.lower() for c in countries if c.lower() in SUPPORTED]

    results = []
    for country in country_codes:
        try:
            resp = requests.get(
                API.format(country=country, page=1),
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": 50,
                    "what": what,
                    "max_days_old": max_days_old,
                    "content-type": "application/json",
                },
                timeout=40,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        for r in data.get("results", []):
            title = r.get("title", "") or ""
            desc = r.get("description", "") or ""
            posting = Posting(
                source="adzuna",
                posting_type=detect_type(title, desc, "job"),
                title=title.strip(),
                organization=(r.get("company", {}) or {}).get("display_name", "") or "",
                location=(r.get("location", {}) or {}).get("display_name", "") or "",
                country=country.upper(),
                url=r.get("redirect_url", "") or "",
                description=desc.strip(),
            )
            # Adzuna gives numeric salary bounds when available.
            smin, smax = r.get("salary_min"), r.get("salary_max")
            if smin or smax:
                posting.salary = f"{int(smin) if smin else ''}-{int(smax) if smax else ''}".strip("-")
            results.append(posting)
    return results
