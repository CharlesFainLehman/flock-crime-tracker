# Proposal: Harvesting Flock Transparency Portals

*Drafted 2026-08-13. Status: proposal — not yet implemented.*

## What these portals are

Flock hosts standardized public transparency pages for client agencies at
`transparency.flocksafety.com/<agency-slug>` (e.g. `piedmont-ca-pd`). Verified against the
live Piedmont, CA portal, each page carries substantially more than usage policy boilerplate:

| Field | Piedmont example (Aug 2026) |
|---|---|
| Featured success stories | First-person officer narrative of a Jan 2026 stolen-truck case solved via ALPR search |
| Total cameras | 57 |
| Vehicles detected, last 30 days | 180,855 |
| Searches, last 30 days | 70 |
| Hotlist hits, last 30 days | 1,091 |
| Data retention | 60 days |
| Hotlist sources | California SVS, NCMEC Amber Alert |
| External agencies with access | ~150 named agencies (incl. LAPD, CHP, SF DA) |
| Search audit | Downloadable CSV of the last 30 days of searches, with stated reasons |
| Policy fields | Prohibited uses, audit cadence, human-verification rule |

## Why it's worth collecting

1. **A new incident source.** The featured success stories are Flock-assisted crime cases,
   often ones local news never covered — directly feeding the core database (clearly labeled
   `source: agency portal`, since they are agency-authored claims).
2. **A longitudinal usage panel that exists nowhere else.** Every stat is a rolling 30-day
   window; the history evaporates unless someone snapshots it. A monthly capture across
   agencies yields a unique panel — cameras, search volume, hotlist hits per agency over
   time — publishable in its own right.
3. **The sharing network.** Each portal names every external agency granted access. Tiny
   Piedmont (57 cameras) shares with ~150 agencies. Collected across portals, this is a
   national who-shares-with-whom graph — highly relevant to the current controversies over
   cross-jurisdiction Flock searches.
4. **Denominators.** Camera counts per agency/state let the incident database express rates,
   not just counts.

## The central constraint: access

The portals sit behind Cloudflare's JavaScript challenge. Verified today:

- Plain HTTP requests (what our GitHub Actions pipeline could do) receive **403**.
- The Internet Archive has **zero snapshots of the entire domain** — the Wayback crawler is
  evidently blocked too, so there is no archival backdoor and no historical record to mine.
  (This also strengthens the case in #2: nobody is preserving these numbers.)
- A real browser session loads everything fine; after the challenge, pages are fully
  server-rendered HTML — trivial to parse once you have them.

**What we should not do:** deploy challenge-solving/anti-bot-evasion tooling in CI. Beyond
ToS/legal exposure, a citable research database can't rest on circumvention.

## Proposed approach

### Phase 1 — Registry + first harvest (one session)
- **Build `data/portals.csv`** (agency, state, slug, url) by combining: DeFlock's
  crowdsourced portal links, EFF's Atlas of Surveillance agency list, and search-engine
  `site:transparency.flocksafety.com` enumeration. Portal count is likely in the hundreds.
- **Assisted browser harvest:** a browser-in-the-loop session (the in-app browser, driven
  page-by-page at human pace) captures each portal's HTML; a parser extracts the stats,
  sharing lists, and success stories into CSVs. Piedmont took ~5 seconds; a few hundred
  portals is one long session, resumable via the registry.
- **Parse + integrate:** success stories go through the existing Claude classify/dedupe
  path into the incidents table with an `agency portal` source label; stats land in new
  `portal_stats.csv` / `portal_sharing.csv` tables.

### Phase 2 — Monthly refresh
Repeat the assisted harvest monthly (a calendar reminder + one command; the session can run
while you do other things). Each snapshot appends to the panel with a `snapshot_date`.
Because windows are 30 days, monthly cadence captures the series with minimal loss.

### Phase 3 — Sanctioned access (parallel track)
Email Flock (and/or a few large client agencies) requesting bulk export or API access to
portal data for research use. Flock markets these portals as a transparency commitment; a
named think-tank researcher asking to *use* the transparency data is a reasonable ask. If
granted, Phases 1–2 collapse into a clean automated feed. Worst case, silence costs nothing.

### Site integration
- New "Usage statistics" section: agencies tracked, total cameras, aggregate 30-day search
  and hit volumes, a per-state deployment table (denominator for the incidents chart).
- Portal-sourced success stories appear in the main table with a distinct source badge.
- Sharing-network data published as CSV first; a network visualization is a later nicety.

## Schema sketch

```
portals.csv         agency, state, slug, url, first_seen, last_seen
portal_stats.csv    slug, snapshot_date, cameras, detections_30d, searches_30d,
                    hotlist_hits_30d, retention_days, hotlist_sources
portal_sharing.csv  slug, granted_to_agency, snapshot_date
(success stories → stories.csv with source_type = "agency portal")
```

## Risks and caveats

- **Selection bias:** portals are opt-in; participating agencies skew transparency-friendly.
  Any analysis must say so.
- **Agency-authored narratives:** success stories are self-reported wins — labeling them is
  non-negotiable for credibility.
- **Template drift:** Flock can change the page layout; the parser needs a validation step
  that flags parse failures rather than silently recording zeros.
- **Manual time cost:** until/unless Phase 3 lands, refreshes need a human-initiated session
  (~an hour a month, mostly unattended).
- **Access could tighten:** Cloudflare settings are Flock's call; Phase 3 is the hedge.

## Effort estimate

- Phase 1: registry build + parser + site section — one working session to build, one to
  harvest.
- Phase 2: ~1 hr/month, mostly waiting.
- Phase 3: one email + follow-ups.
