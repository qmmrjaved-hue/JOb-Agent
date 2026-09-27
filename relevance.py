"""Relevance scoring.

Primary path: ask the Google Gemini API to score how well a posting matches the
candidate profile, on a 1 to 10 scale, and to say whether it reads as a job or a
postdoc. We call the REST endpoint directly so the only dependency is requests.

Fallback path: if Gemini is disabled, has no key, hits its rate limit, or errors,
we fall back to a simple keyword overlap score so the agent still works.
"""

from __future__ import annotations

import json
import re
import time

import requests

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _keyword_score(posting, keywords) -> int:
    """Very rough 1 to 10 score from keyword overlap. Used only as a fallback."""
    text = f"{posting.title} {posting.description}".lower()
    if not keywords:
        return 5
    hits = sum(1 for k in keywords if k.lower() in text)
    frac = hits / max(len(keywords), 1)
    return max(1, min(10, round(1 + frac * 9)))


def score_relevance(posting, candidate_profile: str, keywords, gemini_cfg: dict):
    """Return (score:int, posting_type:str, reason:str)."""
    enabled = gemini_cfg.get("enabled", True)
    api_key = (gemini_cfg.get("api_key") or "").strip()
    if not enabled or not api_key:
        s = _keyword_score(posting, keywords)
        return s, posting.posting_type, "Scored by keyword overlap (Gemini not configured)."

    model = gemini_cfg.get("model", "gemini-2.5-flash-lite")
    prompt = (
        "You are screening postings for a specific candidate.\n\n"
        f"CANDIDATE PROFILE:\n{candidate_profile}\n\n"
        f"POSTING TITLE: {posting.title}\n"
        f"ORGANIZATION: {posting.organization}\n"
        f"LOCATION: {posting.location} {posting.country}\n"
        f"POSTING DESCRIPTION:\n{posting.description[:4000]}\n\n"
        "Decide how genuinely this posting matches the candidate, and whether it "
        "is a general job or a postdoc/academic position. Reply with STRICT JSON "
        'only, no other text, in this exact shape: '
        '{\"score\": <integer 1-10>, \"type\": \"job\" or \"postdoc\", '
        '\"reason\": \"<one short sentence>\"}.'
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
    }
    url = _GEMINI_URL.format(model=model)
    # Retry a couple of times on rate limit (429) or transient errors.
    for attempt in range(3):
        try:
            resp = requests.post(
                url, params={"key": api_key}, json=body, timeout=40
            )
            if resp.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _parse_json(text)
            if parsed:
                score = int(parsed.get("score", 5))
                ptype = parsed.get("type", posting.posting_type)
                reason = parsed.get("reason", "")
                ptype = ptype if ptype in ("job", "postdoc") else posting.posting_type
                return max(1, min(10, score)), ptype, reason
        except Exception:
            time.sleep(3 * (attempt + 1))
    # If everything failed, fall back to keywords.
    s = _keyword_score(posting, keywords)
    return s, posting.posting_type, "Scored by keyword overlap (Gemini call failed)."


def _parse_json(text: str):
    text = text.strip()
    # Strip code fences if the model wrapped the JSON in ```.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
