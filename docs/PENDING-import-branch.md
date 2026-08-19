# Pending work on `import-success-stories`

## 1. Re-source 31 removed press-release rows (blocked, not finished)

The August 2026 import brought in 31 rows whose primary source was a Flock Safety
press release republished through a newspaper's wire section (`/online_features/press_releases/`,
`/region/flock-…`, `/news/national/flock-…`). Under the inclusion rules these cannot stand as a
primary source, so they were **removed** during the adversarial review.

A re-sourcing pass (find independent coverage → restore with a proper citation; remove only
what has none) was launched but **terminated on an API spend limit before returning results**.
Precedent from the earlier vendor pass: 15 of 17 such rows did have independent coverage, so a
meaningful number of these are probably real incidents worth restoring.

The row details are held locally (outside the repo, under `data/imports/`, which is gitignored)
and can be regenerated from the removed rows' ids in this branch's review commit. To resume: search for independent
coverage of each incident, verify it names Flock or the agency's LPR, and re-add with the
independent outlet as `source_url` and the release demoted to `additional_sources`.

## 2. Generic-ALPR stories (design decision needed)

5,753 rows from the same externally supplied spreadsheet describe ALPR successes without naming
Flock. That source list was shared with the maintainer in confidence and is kept **outside the
repository** (`data/imports/` is gitignored); it is excluded under the current "must identify
Flock" rule. Options discussed: a separate labeled
tier on the site; an enrichment pass identifying which agencies are Flock customers; or
broadening the site's scope to ALPRs generally.
