"""Data model for a single job or postdoc posting."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


@dataclass
class Posting:
    # Where it came from and what it is
    source: str                      # e.g. "adzuna", "euraxess", "university:Lund"
    posting_type: str                # "job" or "postdoc"
    title: str
    organization: str = ""
    location: str = ""
    country: str = ""
    url: str = ""
    description: str = ""

    # Filled in later by the intelligence layer
    deadline: Optional[date] = None
    urgent: bool = False
    salary: str = ""
    tags: list = field(default_factory=list)          # e.g. ["fully funded", "visa sponsorship"]
    relevance_score: Optional[int] = None
    relevance_reason: str = ""
    profile: str = ""                # which search profile matched this

    def make_id(self) -> str:
        """A stable id so we can tell if we have seen this posting before.

        We prefer the URL because it is the most stable field. If there is no
        URL we fall back to the title plus organization.
        """
        basis = (self.url or (self.title + "|" + self.organization)).strip().lower()
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.make_id()
        if self.deadline:
            d["deadline"] = self.deadline.isoformat()
        return d
