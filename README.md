# Flock Camera Crime Tracker

A daily-updated database of news stories in which [Flock Safety](https://www.flocksafety.com/)
cameras (automatic license plate readers) assisted in solving or preventing a crime, published
as a static site via GitHub Pages.

## How it works

1. **Discovery** — each day, candidate articles are pulled from the
   [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) and Google News
   RSS using searches like `"Flock Safety" camera` and `"Flock camera" arrest`
   ([pipeline/fetch.py](pipeline/fetch.py)).
2. **Classification** — each new article's text is extracted and classified by Claude
   (Haiku 4.5) as qualifying or not. Qualifying means the article describes a *concrete incident*
   in which a Flock camera played a role in an investigation, arrest, recovery, or prevention.
   Privacy/policy debates, procurement news, and Flock press releases are excluded.
   Structured fields (date, city, state, crime type, camera role, outcome, summary) are
   extracted at the same time ([pipeline/classify.py](pipeline/classify.py)).
3. **Deduplication** — stories covering the same incident (same state, nearby dates) are
   checked by the model and merged into a single entry with multiple source links
   ([pipeline/dedupe.py](pipeline/dedupe.py)).
4. **Publishing** — the database lives in [data/stories.csv](data/stories.csv); the site in
   `site/` is regenerated from it and deployed to GitHub Pages
   ([pipeline/build_site.py](pipeline/build_site.py)).

The daily job runs via GitHub Actions ([.github/workflows/daily.yml](.github/workflows/daily.yml));
its commit history is an audit log of what was added each day.

## Caveats

- Entries reflect claims made in news reports, which typically rely on police statements.
  Inclusion is not independent verification of the camera's role.
- Coverage is limited to English-language outlets indexed by GDELT/Google News; the database
  understates the true count of such incidents.
- Classification is automated; some errors in either direction are inevitable. Corrections
  can be made by editing `data/stories.csv` directly.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # console.anthropic.com
python pipeline/run_daily.py           # one daily update
python pipeline/backfill.py --start 2019-01   # historical backfill (one-time)
python pipeline/build_site.py          # rebuild site/ from the CSV only
```

The backfill checkpoints monthly (via `data/seen_urls.json`), so it is safe to interrupt
and rerun.
