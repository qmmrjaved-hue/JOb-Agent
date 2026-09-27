"""Small text-analysis helpers: type detection, deadlines, tags, salary.

These use plain keyword and date rules. They are deliberately simple and do not
call any API, so they always work and cost nothing.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as dateparser

# Words that suggest an academic / postdoc posting rather than an industry job.
_POSTDOC_HINTS = [
    "postdoc", "post-doc", "post doc", "postdoctoral", "fellowship", "fellow",
    "research associate", "research fellow", "phd", "faculty", "lecturer",
    "assistant professor", "associate professor", "principal investigator",
    "marie curie", "msca", "tenure",
]

_VISA_FUNDING_RULES = {
    "visa sponsorship": ["visa sponsor", "visa sponsorship", "sponsor a visa", "work permit", "relocation to"],
    "relocation support": ["relocation support", "relocation package", "relocation allowance", "moving allowance"],
    "fully funded": ["fully funded", "fully-funded", "full funding"],
    "funded position": ["funded position", "funding is available", "funded by", "grant-funded", "stipend"],
}

# Currency amounts, e.g. "£38,000", "45.000 EUR", "$50,000 per year", "SEK 400000"
_SALARY_PATTERN = re.compile(
    r"(?:(?:£|€|\$|kr|chf|sek|nok|dkk|usd|eur|gbp)\s?)[\d][\d.,]{2,}"
    r"|[\d][\d.,]{2,}\s?(?:eur|euros?|gbp|pounds?|usd|dollars?|sek|nok|dkk|chf|kr)",
    re.IGNORECASE,
)

# Deadline lines, e.g. "Application deadline: 15 January 2027", "closes 2027-01-10"
_DEADLINE_LABELS = [
    "application deadline", "apply before", "closing date", "deadline",
    "closes on", "closes", "last date", "applications close",
]


def detect_type(title: str, description: str, source_default: str) -> str:
    """Return 'postdoc' or 'job'. source_default is used when unsure."""
    text = f"{title} {description}".lower()
    if any(h in text for h in _POSTDOC_HINTS):
        return "postdoc"
    return source_default if source_default in ("job", "postdoc") else "job"


def extract_deadline(text: str) -> Optional[date]:
    """Best-effort deadline extraction. Returns a date or None."""
    if not text:
        return None
    low = text.lower()
    for label in _DEADLINE_LABELS:
        idx = low.find(label)
        if idx == -1:
            continue
        window = text[idx: idx + len(label) + 40]
        # Grab the chunk after the label and try to parse a date out of it.
        after = window[len(label):]
        try:
            dt = dateparser.parse(after, fuzzy=True, dayfirst=True)
            if dt and dt.date() >= date.today() - timedelta(days=1):
                return dt.date()
        except Exception:
            continue
    return None


def is_urgent(deadline: Optional[date], within_days: int = 14) -> bool:
    if not deadline:
        return False
    return date.today() <= deadline <= date.today() + timedelta(days=within_days)


def detect_visa_funding(text: str) -> list:
    if not text:
        return []
    low = text.lower()
    found = []
    for tag, needles in _VISA_FUNDING_RULES.items():
        if any(n in low for n in needles):
            found.append(tag)
    return found


def extract_salary(text: str) -> str:
    if not text:
        return ""
    m = _SALARY_PATTERN.search(text)
    return m.group(0).strip() if m else ""


def detect_deadline_tags(posting) -> None:
    """Fill deadline, urgent, tags and salary on a Posting, in place."""
    text = f"{posting.title} {posting.description}"
    posting.deadline = extract_deadline(text)
    posting.urgent = is_urgent(posting.deadline)
    posting.tags = detect_visa_funding(text)
    if not posting.salary:
        posting.salary = extract_salary(text)
