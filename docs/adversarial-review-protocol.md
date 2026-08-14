# Adversarial database review protocol

Run after each major data ingest (first run: post-backfill, 2026-08). Independent Claude
reviewer instances — fresh context, no knowledge of the classification decisions — are
prompted to *break* the database, not to defend it. Flags are consolidated and verified
before any row is changed; all removals are recorded in the git history.

## Review dimensions

1. **False positives (news).** Rows that fail the inclusion rule: camera-error or
   wrongful-stop stories counted as successes; privacy/policy stories; vendor press
   releases with no concrete incident; generic LPR stories that never identify Flock;
   speculative camera involvement ("may have," "could help").
2. **Duplicates.** Same real-world incident appearing as multiple rows — syndicated
   coverage across outlets/states, incident-date drift between reports, follow-up
   coverage (arrest → trial → sentencing) creating repeat rows.
3. **Field accuracy.** Crime-type miscodes; state/city errors; impossible dates (future,
   pre-2017); outcome or camera-role claims not supported by the summary.
4. **Source spot-check.** For a random sample plus every flagged row: fetch the source
   URL and confirm the row's fields match what the article actually says (catches
   extraction hallucinations). Note dead links.
5. **Court records.** Civil suits or policy litigation misclassified as criminal use;
   filings where Flock appears only in passing; per-case duplicate filings that should
   be consolidated.

## Mechanism

- The database is sharded into batches (~80 rows); each batch goes to an independent
  reviewer agent with the dimensions above and no access to this session's history.
- Reviewers return structured flags: row id, dimension, severity (remove / fix / verify),
  reason, and the evidence quoted.
- Flags are consolidated; "remove" and "fix" flags are re-verified by a second
  independent agent checking the source before action.
- The maintainer approves the final change list; edits land as a single reviewed commit.

## Standing quality notes

- Known failure class (caught 2026-08-13): camera-error stories misread as successes.
  The classifier prompt now excludes these; reviewers should still hunt for survivors.
- Court records classified from snippets (2026-08) have sparse crime_type fields —
  absence of a crime type there is a known gap, not a flag.
