# Open items

## Generic-ALPR stories (design decision needed)

An externally supplied list contains ~5,750 stories describing ALPR successes that do **not**
name Flock. They are excluded under the current "must identify Flock" rule, and the source
list is kept outside the repository (`data/imports/` is gitignored) because it was shared with
the maintainer in confidence.

Options if we want to use them:
1. A separate, clearly labeled tier on the site ("ALPR, vendor unspecified").
2. An enrichment pass cross-referencing each agency against known Flock deployments
   (EFF Atlas of Surveillance, DeFlock, Flock transparency portals) and promoting only
   confirmed Flock agencies.
3. Broaden the site's scope to ALPRs generally, with Flock as one filter.

## Response to IJ's "Database of ALPR Abuse"

https://ij.org/the-ij-database-of-alpr-abuse/ — maintainer wants a rebuttal section analyzing
its methodology and presentation. Maintainer writes the argument; analysis and charts to follow.

## Research page

A literature review of ALPR/camera research is drafted as a local mock (gitignored `drafts/`),
awaiting the maintainer's text.
