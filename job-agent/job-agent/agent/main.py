"""Main entry point. Run with:  python -m agent.main

Flags:
  --config PATH        use a different config file (default: config.yaml)
  --profile NAME       run only one search profile
  --weekly-summary     send a summary of the last 7 days instead of the daily new-only run
  --dry-run            do everything except send notifications (prints to screen)
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime

from .config import load_config
from .db import SeenDB
from .dedupe import dedupe_within, is_duplicate_of_seen
from .notify import build_digest, notify
from .relevance import score_relevance
from .tagging import detect_deadline_tags
from .fetchers import adzuna, euraxess, university


def _gather(profile: dict, cfg: dict, db: SeenDB) -> list:
    """Run every source for one profile, recording health and errors."""
    name = profile.get("name", "profile")
    postings = []

    def run_source(label, func, *args):
        try:
            found = func(*args)
        except Exception as e:
            db.record_run(name, label, 0, 0, error=str(e))
            print(f"  [{label}] ERROR: {e}")
            return []
        streak = db.update_source_health(label, len(found))
        note = f"  (WARNING: {streak} days with zero results)" if streak >= 5 else ""
        print(f"  [{label}] fetched {len(found)}{note}")
        return found

    postings += run_source("adzuna", adzuna.fetch, profile, cfg.get("adzuna", {}))
    postings += run_source("euraxess", euraxess.fetch, profile)
    for page in profile.get("university_pages", []) or []:
        label = f"university:{page.get('name','page')}"
        postings += run_source(label, university.fetch, page, profile)
    return postings


def _keep_type(posting, wanted: str) -> bool:
    if wanted == "both":
        return True
    if posting.posting_type == wanted:
        return True
    # Treat academic sources as postdoc-eligible even if the label guessed "job".
    if wanted == "postdoc" and posting.source.startswith(("euraxess", "university")):
        return True
    return False


def process_profile(profile: dict, cfg: dict, db: SeenDB, dry_run: bool):
    name = profile.get("name", "profile")
    wanted_type = profile.get("posting_type", "both")
    threshold = int(cfg.get("gemini", {}).get("relevance_threshold", 6))
    print(f"\n=== Profile: {name} ({wanted_type}) ===")

    postings = _gather(profile, cfg, db)
    postings = [p for p in postings if _keep_type(p, wanted_type)]
    postings = dedupe_within(postings)

    seen_keys = db.seen_keys(name)
    new_postings = [
        p for p in postings
        if not db.is_seen(name, p.make_id()) and not is_duplicate_of_seen(p, seen_keys)
    ]
    print(f"  {len(postings)} after filtering, {len(new_postings)} genuinely new")

    relevant = []
    for p in new_postings:
        score, ptype, reason = score_relevance(
            p, profile.get("candidate_profile", ""), profile.get("keywords", []),
            cfg.get("gemini", {}),
        )
        p.relevance_score, p.posting_type, p.relevance_reason = score, ptype, reason
        detect_deadline_tags(p)  # sets deadline, urgent, tags, salary
        db.mark_seen(name, p, notified=(score >= threshold))
        if score >= threshold:
            relevant.append(p)
    print(f"  {len(relevant)} above relevance threshold {threshold}")

    if relevant:
        subject = f"[Job Agent] {len(relevant)} new match(es): {name}"
        body = build_digest([p.to_dict() for p in relevant],
                            f"New postings for '{name}' on {datetime.now():%Y-%m-%d}")
        if dry_run:
            print("\n----- DRY RUN, would send -----\n" + body)
        else:
            ok = notify(cfg.get("notifications", {}), subject, body)
            print(f"  notification sent: {ok} (fallback logged if email failed)")
    db.record_run(name, "ALL", len(postings), len(relevant))


def weekly_summary(profile: dict, cfg: dict, db: SeenDB, dry_run: bool):
    name = profile.get("name", "profile")
    threshold = int(cfg.get("gemini", {}).get("relevance_threshold", 6))
    rows = db.recent_relevant(name, days=7, min_score=threshold)
    subject = f"[Job Agent] Weekly summary: {name} ({len(rows)} in last 7 days)"
    body = build_digest(rows, f"Weekly summary for '{name}'")
    if dry_run:
        print("\n----- DRY RUN weekly -----\n" + body)
    else:
        notify(cfg.get("notifications", {}), subject, body)
    print(f"  weekly summary: {len(rows)} postings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--weekly-summary", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    db = SeenDB(cfg.get("database", {}).get("path", "data/agent.db"))
    profiles = cfg.get("profiles", [])
    if args.profile:
        profiles = [p for p in profiles if p.get("name") == args.profile]
        if not profiles:
            print(f"No profile named {args.profile}")
            sys.exit(1)

    for profile in profiles:
        try:
            if args.weekly_summary:
                weekly_summary(profile, cfg, db, args.dry_run)
            else:
                process_profile(profile, cfg, db, args.dry_run)
        except Exception:
            print(f"Profile {profile.get('name')} crashed:\n{traceback.format_exc()}")

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
