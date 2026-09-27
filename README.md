# Job and Postdoc Search Agent

An automated agent that checks job and postdoc sources every day and emails you
only the new postings that genuinely match your profile. It uses Google Gemini
to score how well each posting fits you, so you are not flooded with noise.

It is built to run in the cloud on a free schedule, so it works even when your
own computer is switched off. Everything lives in this one folder, so you can
move it to another computer by copying the folder.

## What it does each day

1. Fetches postings from Adzuna (general jobs), EURAXESS (academic and postdoc
   posts), and any university career pages you list.
2. Removes anything it has already shown you, including near-duplicates reposted
   with slightly different titles.
3. Asks Gemini to score each new posting from 1 to 10 against your profile, and
   to say whether it is a job or a postdoc.
4. Tags deadlines (flagging anything closing within 14 days as urgent), and
   visa, relocation and funding mentions, and pulls out salary or funding where
   stated.
5. Emails you a digest of only the matches above your chosen score. Optionally
   also sends a phone push via ntfy. Once a week it sends a summary.

## What you need (all free)

- A free GitHub account (this is where it runs, in the cloud).
- Adzuna API keys: register at https://developer.adzuna.com/ and copy your
  Application ID and Application Key.
- A Google Gemini API key: get one free at https://aistudio.google.com/apikey
- A Gmail App Password for sending the emails: in your Google Account turn on
  2-Step Verification, then create an App Password (16 characters). Use that as
  the email password, not your normal login password.
- Optional, for phone push: the free ntfy app (https://ntfy.sh), then pick a
  private topic name.

## Recommended setup: run in the cloud with GitHub Actions

This is the option that runs even when your computer is off.

1. Create a new private repository on GitHub.
2. Upload the entire contents of this folder to that repository (you can drag
   the files into the GitHub web uploader).
3. In the repository, open Settings, then "Secrets and variables", then
   "Actions", and add these repository secrets (one at a time):
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
   - `GEMINI_API_KEY`
   - `EMAIL_USERNAME`  (your Gmail address)
   - `EMAIL_PASSWORD`  (the 16-character App Password)
4. Edit `config.yaml` in the repository and change:
   - `notifications.email.to` to the inbox where you want the alerts,
   - the `countries`, `keywords` and `university_pages` if you want.
5. Open the "Actions" tab and enable workflows if GitHub asks. The schedule is
   already set (daily at 06:00 UTC, weekly summary on Mondays).
6. To test immediately, open the "Job Agent" workflow and click "Run workflow".
   Check your email and the run log.

That is all. From then on it runs itself every day.

## Running it on your own computer instead (optional)

You only need this if you want to run it manually or test locally.

1. Install Python 3.11 or newer.
2. In this folder run: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your real keys.
4. Copy `config.example.yaml` to `config.yaml` if you do not already have one,
   and set `notifications.email.to`.
5. Test without sending anything: `python -m agent.main --dry-run`
6. Real run: `python -m agent.main`
7. Weekly summary: `python -m agent.main --weekly-summary`

On your own computer a daily run only happens while the computer is on, which is
why GitHub Actions is the better home for it.

## Configuring your searches

All of this is in `config.yaml`, which you can edit without touching any code.

- `posting_type`: `job`, `postdoc`, or `both`.
- `candidate_profile`: a paragraph about you. Gemini reads this to judge fit, so
  the more accurate it is (including what is NOT a fit), the better the scoring.
- `keywords`: words used for the searches and for the fallback scoring.
- `countries`: a list of two-letter codes, or `any` for a global search.
- `adzuna_what` and `euraxess_keywords`: the search terms sent to each source.
- `university_pages`: a list of career pages to scan. Point these at real
  vacancy pages, ideally already filtered to your field.
- You can add more profiles under `profiles:` to run several independent
  searches (for example one for postdocs and one for industry jobs), each with
  its own memory of what it has seen.

Change the score cutoff with `gemini.relevance_threshold` (1 to 10). A higher
number means fewer, stricter matches.

## Notifications

- Email is the main channel and is on by default.
- To also get a phone push, install the ntfy app, choose a private topic name,
  set `notifications.ntfy.enabled: true` and put your topic in `config.yaml`.
- If an email ever fails to send, the message is written to
  `logs/notifications.log` so nothing is lost.

## How it remembers what it has seen

The agent keeps a small database at `data/agent.db`. When it runs on GitHub, the
workflow commits this file back to the repository after each run, so the memory
carries over from day to day and travels with the folder to any computer.

## Moving to another computer

Copy the whole folder (or clone the GitHub repository). Your keys are not in the
folder, so on the new machine you either recreate the `.env` file or, if you run
it on GitHub, nothing changes at all because it runs in the cloud.

## Costs

Everything here is designed for free tiers: GitHub Actions, Adzuna, Gemini
(Flash-Lite), Gmail sending, and ntfy. Keep the schedule to once a day and the
volume stays well within the free limits.

## Troubleshooting

- No email arrived: check that `EMAIL_PASSWORD` is a Gmail App Password, not your
  normal password, and that `notifications.email.to` is set. Look in the Actions
  run log and in `logs/notifications.log`.
- EURAXESS returns nothing for several days: the site layout may have changed.
  The run log will warn after 5 empty days. The selectors in
  `agent/fetchers/euraxess.py` may then need a small update.
- Adzuna returns nothing for a country: Adzuna only covers a fixed set of
  countries (see the list in `agent/fetchers/adzuna.py`). Sweden, for example,
  is not covered by Adzuna, so Swedish postdocs come from EURAXESS and the
  university pages instead.
- Gemini rate limit: the free tier has limits. The agent retries and then falls
  back to keyword scoring, so it keeps working.

## Folder structure

```
job-agent/
  config.yaml              your working settings (profile, countries, keywords)
  config.example.yaml      template to copy
  .env.example             template for local secrets
  requirements.txt         Python dependencies
  README.md                this file
  .github/workflows/daily.yml   the daily cloud schedule
  data/agent.db            memory of seen postings (created on first run)
  agent/
    main.py                orchestrates a full run
    config.py              loads config and fills in secrets
    models.py              the Posting data structure
    db.py                  SQLite store and source health
    dedupe.py              fuzzy de-duplication
    relevance.py           Gemini scoring with keyword fallback
    tagging.py             deadlines, urgency, visa and funding tags, salary
    notify.py              email and ntfy, with a log fallback
    fetchers/
      adzuna.py            Adzuna API
      euraxess.py          EURAXESS search (scraper)
      university.py        generic career-page scanner
```
