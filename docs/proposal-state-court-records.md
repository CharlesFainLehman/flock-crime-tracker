# Proposal: State trial-court records — options and costs

*Drafted 2026-09-16. Status: proposal — not yet implemented.*

## Summary

- The court-records table is almost entirely federal. 15 of its 16 rows are federal district-court
  filings from RECAP. State trial courts, where nearly all Flock-assisted prosecutions happen, are
  absent.
- No vendor sells full-text search over state criminal trial-court documents at national scale.
  Aggregators hold docket sheets. They hold documents only where a court publishes them or a
  customer paid to pull them. Westlaw's trial-court document collection is civil-only. Tyler's
  re:SearchTX excludes criminal cases and forbids bulk collection.
- Keyword discovery ("Flock" mentioned anywhere) therefore reaches three things: appellate
  opinions (already covered, but under-queried), docket-entry text, and whatever documents an
  aggregator has already OCR'd.
- Recommended order: (A) fix the free layer, $0; (B) run two zero-cost yield tests; (C) if the
  tests find state records, subscribe to Docket Alarm at $99/month and build a weekly API sweep
  modeled on `pipeline/courts.py`; (D) build news-to-case matching for the 41% of incidents that
  name a defendant. Skip Westlaw, Lexis, Bloomberg Law, Trellis, UniCourt, and re:Search unless
  free access already exists or a research price appears.

## 1. The gap, measured

`pipeline/courts.py` queries CourtListener weekly with six phrases (`"flock safety"`,
`"flock camera"`, `"flock cameras"`, `"flock lpr"`, `"flock alpr"`, `"flock license plate"`)
against RECAP (federal PACER documents) and opinions.

| Source | Candidates seen | Rows in `court_records.csv` |
|---|---|---|
| RECAP (federal filings) | 357 | 15 |
| Opinions (all courts) | 37 | 1 (*State v. Duhart*, Ohio Ct. App.) |

The 1,740 news incidents span 46 states. Nearly all were charged in state court.

**Where Flock appears in a state criminal file, and whether it is online:**

1. Search-warrant applications and affidavits. Sealed until executed, often kept in a separate
   warrant docket, rarely online anywhere.
2. Charging documents and probable-cause affidavits. PDFs online in some counties; excluded in
   others (Indiana posts only sentencing orders; Minnesota withholds complaints).
3. Suppression motions, responses, and orders. Online where e-filed documents are public.
4. Trial-court written rulings. Rare; most rulings are oral or minute entries.
5. Appellate opinions. Covered by CourtListener.

**Known misses (checked 2026-09-16):**

- *Commonwealth v. Bell*, Norfolk Circuit Court, 2024-05-10. Judge Jamilah LeCruise suppressed
  Flock evidence obtained without a warrant. Reported by the Virginian-Pilot. Not in the table.
- *Commonwealth v. Church*, Norfolk Circuit Court (suppression granted, relying on *Bell*), reversed
  by the Court of Appeals of Virginia, No. 0737-25-1, 2025-10-14. The opinion is a PDF on
  vacourts.gov. A CourtListener search for "flock" in that court returns nothing.
- *State v. Simonson*, Washington Court of Appeals, January 2026 (Flock image on a public road held
  not a search). No CourtListener hit for "flock" in that court.

**Query gap on CourtListener** (v4 search API, 2026-09-16):

| Query | Opinions | RECAP dockets |
|---|---|---|
| Union of the six current phrases | 42 | 303 |
| `flock AND ("license plate" OR "plate reader" OR alpr OR lpr)` | 60 | — |
| Widened query, minus the six phrases | **29** | 270 (noisy) |

The 29 extra opinions include Texas Court of Appeals cases (*White v. State*, *Taylor v. State*)
whose text says "Flock" without "Flock Safety" or "Flock camera".

**Classifier yield is suspect.** 36 of 37 opinion candidates were rejected. Most are criminal
appeals (*State v. X* in Ohio; *X v. State* in Indiana, Texas, Georgia; Tennessee CCA), where
Flock evidence in the prosecution is the likely reason the word appears. One plausible cause:
`fetch_opinion_text` requests only `plain_text`, and many scraped opinions carry text only in
`html` or `html_with_citations`, so the classifier sees a 500-character snippet and rejects.
Check this before spending money.

**CourtListener trial-court scope.** 68 state appellate courts and 51 state supreme courts have
opinion scrapers. Only 7 state trial courts do (Maine Superior; New York Supreme, County, District,
Justice, and City Courts; Texas Business Court). Other trial-level opinions arrive irregularly
(e.g. *ACLU of Massachusetts v. Massachusetts State Police*, Mass. Superior Court, 2026-09-02).
There are no state dockets.

## 2. What each tool offers

"Verified" means read on the vendor's own page on 2026-09-16. "Reported" means third-party
listings (library guides, review sites) that may be stale.

| Tool | What is searchable | State criminal trial coverage | Automation | Price | Verdict |
|---|---|---|---|---|---|
| **Westlaw** | Docket sheets (captions). "Trial Court Documents": selected pleadings and motions from selected state trial courts, **civil cases only** (Boston College law library guide). | None for documents. | No API. Contract bars systematic downloading. | Verified self-serve: $256.75/mo single state, $399.75/mo all states + federal (firms ≤10 attorneys; 12% off 2-yr, 18% off 3-yr). | Not useful for this. |
| **Lexis+ / CourtLink** | Dockets from 4,000+ federal, state, and local courts; documents retrieved per case. | Varies by court; documents cost extra. | No API for research. | Reported: from ~$171/mo; CourtLink documents $7–$61 each. Official price is quote-based. | Manual only. Not worth buying for this. |
| **Bloomberg Law** | Dockets from 1,000+ state courts. Keyword search over "Dockets & Documents". Alerts on saved searches. Underlying filings limited; retrieval fees passed through. | Varies by court. | No API in a standard seat (an enterprise dockets API exists, quote-based). Contract bars automation. | Reported: $350–500/user/mo; quote-based. | Best of the big three for a manual monthly keyword sweep plus alerts, only if a login already exists. |
| **UniCourt** | Docket entries and case metadata across 4,000+ courts in 40 states; documents "fees may apply". | Varies by state. State pages describe criminal coverage for some states (Florida, Virginia, California); the Georgia page lists civil, family, and probate only. | API is Enterprise-only, custom price. | Verified: Personal $59/mo (10 case searches/mo, 1 user), Professional $199/mo (50), Premium $399/mo (200, 5 users). Enterprise: quote. | Web plans are useless for sweeps (search quotas). API price unpublished; ask for a research rate. |
| **Trellis** | Dockets, rulings, and documents; docket text searchable. Documents purchasable in 22 counties (AZ, CA, GA, IL, PA, WA), requestable in Los Angeles and Cook. | Coverage matrix lists civil, family, and probate. No criminal column. | API sold separately, custom price. | Verified: Research $139.95/mo, Research + Judge Analytics $209.95/mo, both **California only**, 75 content views/mo, up to 3 accounts. All states = enterprise contract. | Not a fit. |
| **Docket Alarm** (Clio / vLex) | 675M dockets and documents. OCR full-text search over documents it holds. State coverage in 40+ states, "county-level civil and criminal dockets" (marketing; the coverage explorer needs a browser session). | Documents exist only where a court publishes them or a user pulled them. Criminal share unknown. | Documented REST API. Any account can authenticate. `search/` "no additional cost"; `searchdirect/` queries a court live by party or case number, no fees. Pricing table has no API row: confirm the $99 plan includes it. | Verified: Free (5 actions/week); Pay-as-you-go $39.99/mo + $4/document; Flat-fee $99/user/mo, unlimited documents; state-court document fees billed separately; Enterprise from 5 users. | The one paid tool that can be automated cheaply. Yield unknown until tested. |
| **Tyler re:Search** (re:SearchTX, re:SearchIL, …) | Texas statewide docket and document access for e-filed cases. | **re:SearchTX has all case types except criminal.** | No API. Terms §2.6 (verified): "Data scraping of the platform, access by and use of automated data collection tools on the platform, and other forms of programmatic or bulk data collection for commercial use are prohibited. You agree not to access or use re:Search for bulk data collection or aggregation purposes without prior approval." | Free for the public. | Unusable for this. |
| **CourtListener** | Opinions (state appellate, some trial), RECAP (federal only), free API. | Trial-level opinions from 7 courts. No dockets. | Yes; token is free; rate-limited. | $0. | Keep. Widen queries; fix text fetch (Proposal A). |
| **judyrecords** | Free web search over 770M cases aggregated from state and county portals; case metadata and docket entries. | Broad, uneven; data source shown per case. | "Programmatic access to judyrecords is permitted exclusively through the judyrecords API." Full-Text API (750M cases) and Structured Objects API (725M cases, 1.4B parties) on request: api@judyrecords.com. Price unpublished. | $0 web; API unknown. | Cheapest candidate for national docket-text discovery. Test by hand first. |
| **Free state and county portals** | Case lookup by name or number; documents in some places. | Indiana MyCase: criminal documents online = sentencing orders only. Minnesota MCRO: all criminal-case documents except complaints and police reports; pending cases without a conviction are hidden from name search. Franklin County (Columbus) CIO: criminal and civil dockets; "Efforts to mine large quantities of data from CIO without prior approval … will be detected and stopped." Orange County FL: non-confidential documents including criminal (AOSC16-14). Harris County TX District Clerk eDocs: records and documents search; criminal document scope unverified. Fulton County GA: docket information only. | Low-volume lookups only; terms differ per county. | $0. | For case matching (Proposal D), not for keyword discovery. |

## 3. Proposals

### A. Fix and widen the free layer — $0, one session

1. Add widened queries: `flock AND ("license plate" OR "plate reader" OR alpr OR lpr)`, plus
   `"flock hit"`, `"flock search"`, `"flock system"`, `"flock data"`, `"flock footage"`,
   `"flock image"`. Measured effect: +29 opinions, +270 RECAP dockets (noisy; the classifier
   filters, at ≈ $0.005 per document).
2. Make `fetch_opinion_text` fall back to `html_with_citations` or `html` (tags stripped) when
   `plain_text` is empty. Re-run the 37 opinion candidates with a `--reclassify-opinions` flag
   that ignores `seen_court_ids.json` for opinion keys.
3. Expected result: dozens of state appellate records (Ohio, Texas, Indiana, Georgia, Virginia,
   Tennessee), each documenting Flock use in a state prosecution. This is the largest gain per
   dollar on the list.

**Status (2026-09-18): implemented and run.** `pipeline/courts.py` now has the seventh query,
`highlight=on` (the search snippet is the matching passage, not the document's first 500
characters), opinion text taken from whichever field CourtListener populated (`plain_text`, then
the HTML/XML fields), excerpts centred on the first Flock mention when a document exceeds 12,000
characters, text fetch in `--from-file` mode whenever the token is set, document-level dedupe
(CourtListener carries one case under several docket ids and one opinion under several
clusters; a filing is now identified by court, case, date, and docket entry number, so the same
document cannot become two rows), `--reclassify-opinions`, and `--reclassify-low` (re-runs the
documents behind snippet-only rows and updates or removes them in place). The `Court records
update` workflow gained `reclassify_opinions` and `reclassify_low` inputs, runs on the branch it
is dispatched from, and deploys Pages only from `main`.

The cause of the 36-of-37 rejections was simpler than the text-field hypothesis: the August
opinion candidates were classified in `--from-file` mode, which sent the classifier only the
search snippet, and without highlighting that snippet was the opinion's caption.

Full sweep with re-classification, run 2026-09-18 (GitHub Actions, about 4 hours, 482 candidates,
0 errors, 15 rate-limit waits):

| | Before | After |
|---|---|---|
| Rows in `court_records.csv` | 16 | 119 (after removing 28 same-document duplicates the run produced) |
| State appellate opinions | 1 | 20 |
| Federal filings (RECAP) | 15 | 99 |
| Distinct cases among rows added | — | 91 |

The 19 added opinions: 14 of the 37 August candidates (previously all rejected) plus 5 found by
the widened query or newer than the August sweep. Courts: Ohio Court of Appeals 10, Texas Courts
of Appeals 4, Supreme Court of Georgia, Supreme Court of Kansas, Indiana Court of Appeals,
Appellate Court of Illinois, Court of Appeals of Virginia. Added rows by confidence: 66 high,
16 medium, 21 low. All 351 rejections sampled were correct (civil suits against Flock, public
records disputes, an amicus brief, Flock in passing).

**CourtListener quota (found 2026-09-18).** The token behind `COURTLISTENER_TOKEN` has a daily
request quota. Run 1 (about 130 searches and 480 document fetches over four hours) exhausted it
partway through: document-text fetches started failing after roughly 400 calls, and a second run
that evening got `429` with `Retry-After` of about 71,600 seconds (20 hours) on its first search.
Consequences: 83 of run 1's rejections (38 opinions, 45 federal filings) were made on a search
snippet, not the document, and are wrong to trust; the sweep now leaves such candidates out of
the seen set, so they are retried, and `--retry-rejected` recovers the ones already marked. A
`--collect-only` search followed by a `--from-file` classification keeps each run inside the
quota. This also caps any Proposal C design that leans on CourtListener document text: budget
a few hundred API calls per day, or ask Free Law Project for a higher limit.

Known defects in the added rows, for the next adversarial review:

- 21 rows are snippet-only ("low") and 11 have an empty summary, because the document text
  fetch returned nothing late in the run (the quota, above). Four Texas Court of Appeals
  opinions found by the widened query were rejected for the same reason. Recovery runs are
  scheduled for after the quota resets: a search-only run, unmarking the 83 snippet-only
  rejections, then a from-file run with `reclassify_low`.
- One investigation can produce many rows: 22 of the 99 federal rows are E.D. Wisconsin
  search-warrant applications, most from one 2023 Milwaukee robbery investigation, each
  affidavit reciting the same Flock hits. Rows are documents, not cases; state counts drawn
  from this table overstate Wisconsin.
- Co-defendant dockets carry the same complaint under different case names (e.g. *United States
  v. Davis* and *United States v. Ostrowski*, E.D. Wis., 2025-06-24); the signature dedupe does
  not catch these.
- *Tovar v. Rodriguez* (N.D. Tex.) is a civil rights suit alleging a detective misstated Flock
  data in a homicide arrest affidavit. It documents Flock use in a criminal investigation, but
  it is a contestability item under the review protocol: keep, annotate, or remove is the
  maintainer's call.

### B. Zero-cost yield tests — about two hours, before any subscription

1. Docket Alarm free account (5 actions per week): search `"Flock Safety"` and `"Flock camera"`
   limited to state courts. Record total hits, court mix, share that is criminal, and whether hits
   are documents or docket entries. Two weeks of free actions suffice.
2. judyrecords, by hand: same phrases. Record whether matches come from docket-entry text (e.g.
   "Motion to Suppress Flock …") and the state mix. If useful, email api@judyrecords.com for
   Full-Text API terms and a research price.
3. Bloomberg Law, Westlaw, or Lexis: only if a login already exists. Run the same keyword search
   over dockets and documents; count state criminal hits.

Decision rule: build C only if a test shows roughly 25 or more state criminal records, or a steady
weekly flow of new ones.

**Status (2026-09-18): needs the maintainer, about 15 minutes.** Neither test can run from the
pipeline. Docket Alarm requires an account (email verification, acceptance of its terms) and
blocks non-browser access to its search pages. judyrecords permits programmatic access only
through its API. Search-engine `site:` queries against docketalarm.com, judyrecords.com,
unicourt.com, and trellis.law for "Flock Safety" returned no indexed pages, which says nothing
either way.

Steps:

1. docketalarm.com, free account. Search `"Flock Safety"`, then `"Flock camera"`, filtered to
   state courts. Record: total hits, which courts, criminal versus civil, and whether hits are
   documents or docket entries. The free plan allows 5 actions a week, so two searches and three
   document views per week.
2. judyrecords.com. Search the same two phrases. Record whether the matched text is a docket
   entry (for example "Motion to Suppress Flock …") or only a case title, and the state mix.
3. Send this to api@judyrecords.com:

> Subject: Full-Text API terms for a public research database
>
> I maintain flockstopscrime.com, a public, daily-updated database of criminal cases in which
> Flock Safety license-plate cameras were used. I want to use the judyrecords Full-Text API to
> find state trial-court cases whose docket entries mention "Flock". Expected volume: a weekly
> search of about seven phrases, retrieving the matching case records (a few hundred a year).
> Could you send the API terms, pricing (a research or non-commercial rate if one exists), and
> confirm whether docket-entry text is in the full-text index?

Record the counts in this section when done.

### C. Automated Docket Alarm sweep — $99/month plus document fees; one session to build

- Weekly GitHub Actions job `pipeline/state_courts.py`, same shape as `courts.py`: call `search/`
  with the query set, filter to state courts, dedupe by docket and document id in
  `data/seen_state_court_ids.json`, download new documents (unlimited on the flat-fee plan;
  state-court pay documents are billed separately, so cap spend per run in code), extract text
  with `pdftotext` (OCR only when a PDF has no text layer), classify with the existing prompt
  (Haiku 4.5: $1 per million input tokens, $5 per million output; ≈ $0.005 per document), match
  to news stories, and append to `court_records.csv`.
- Citation: `source_url` points to Docket Alarm, which is paywalled. Store court, case number,
  document title, and filing date in the row so a reader can verify at the courthouse or with a
  free Docket Alarm account (5 views per week). Where the county portal is public, link there.
- Confirm with Docket Alarm sales that API use is covered by the $99 plan. Their API docs say any
  account can authenticate and `search/` has no added cost, but the pricing table lists no API
  row. If the API is enterprise-only (5+ seats), C is off the table at roughly $500+/month.
- Cost: subscription $1,188/yr; state document fees unknown (budget $10–30/month, capped in
  code); Claude ≈ $5–20/yr; Actions minutes free on a public repository.
- Yield: unknown. Docket Alarm's OCR corpus is customer-driven and skews civil. That is why B
  comes first.

### D. News-to-case matching — outcomes for the news database; two sessions to build

- 722 of 1,740 incident summaries (41%) name a charged person. For each: extract name, state,
  county (from city), and incident date; find the criminal docket; record court, case number,
  charges, disposition, and disposition date; pull any document whose docket text mentions Flock
  or "suppress".
- Lookup channels, in order: Docket Alarm `searchdirect/` party search (live court query, no
  fees, if C is in place); free state and county portals where documents are public (Minnesota
  MCRO, Florida clerks, Harris County TX, Indiana MyCase for dispositions); manual for the rest.
  Automated portal lookups only where terms allow. Franklin County forbids mining without
  approval: ask first, or use their public-records request.
- Output: `data/case_outcomes.csv` (`story_id, court, case_number, charges, disposition,
  disposition_date, source_url, confidence`). Site: an outcome badge on the news table.
- Cost: $0 beyond C, or labor only. At about 5 minutes per manual lookup, 722 cases is roughly
  60 hours. The top five states (CA 171, GA 154, TX 139, OH 120, WA 117 incidents) hold 40% of
  rows, but California, Georgia, and Washington mostly do not publish criminal documents online,
  so automation covers less than half of the total. Plan for a manual tail.
- Value: converts "arrest" rows into conviction or dismissal outcomes, the most common follow-up
  question about any arrest database. It does not depend on vendor keyword coverage, because the
  case is identified from the news report, not from a search for "Flock".

### E. Sanctioned research access — parallel track, cost is a few emails

- Ask UniCourt, Trellis, and Docket Alarm / vLex for research pricing on a keyword feed ("Flock"
  mentions in state criminal dockets), stating the public database and the institution. Ask
  judyrecords for API terms. Ask Free Law Project whether state docket data is on their roadmap.
- If any of these grants access, C collapses into a clean feed and D gets a cheap lookup channel.

### Not proposed

- Scraping re:SearchTX, county portals with anti-mining terms, or Westlaw, Lexis, and Bloomberg
  Law. Contract terms forbid it, and the database's credibility depends on clean sourcing (see
  `proposal-transparency-portals.md`).
- Enterprise data licenses (UniCourt, Trellis, Bloomberg dockets API) at list price. All are
  quote-based. Inference from their web-plan prices: expect five figures per year for coverage
  that is thin in criminal cases.

## 4. Cost summary

| Option | Build | Recurring cost | Recurring labor | Yield certainty |
|---|---|---|---|---|
| A. Free layer | 1 session | $0 | none | High: +29 opinions measured; classifier re-run likely adds more |
| B. Yield tests | 2 hours | $0 | none | Produces the numbers for C |
| C. Docket Alarm sweep | 1 session | $1,188/yr + document fees + ≈ $10 Claude | near zero | Unknown until B |
| D. Case matching | 2 sessions | $0 with C; labor otherwise | monthly batch; manual tail | High for outcomes; Flock documents only where portals publish them |
| E. Research access | emails | $0 to unknown | none | Unknown |
| Big-three manual sweep | none | $2,000–6,000/yr | 1–2 hours/month | Moderate: docket text plus some documents |

## 5. Risks

- **Paywalled sources.** Vendor links shift the verification burden to readers. Mitigate with full
  citation fields and public-portal links where they exist.
- **Low recall on docket text.** Most suppression motions are titled generically. Docket-text
  discovery finds only the ones that name Flock in the entry.
- **Name-matching errors in D.** Require state, county, and a date window; review low-confidence
  matches by hand; publish nothing below "medium".
- **Terms drift.** Vendor terms and county rules change. Re-check yearly.
- **Uneven coverage.** Every vendor covers some courts and not others. Record which courts are
  covered so counts are not read as national rates.

## Sources (checked 2026-09-16)

- CourtListener v4 API: search counts and court lists, `https://www.courtlistener.com/api/rest/v4/`
- Westlaw self-serve plans: `https://sales.legalsolutions.thomsonreuters.com/en-us/products/westlaw-advantage/plans-pricing`
- Westlaw Trial Court Documents civil-only: Boston College law library guide, `https://lawguides.bc.edu/c.php?g=350895&p=2367361`
- Lexis / CourtLink pricing (reported): `https://spellbook.com/learn/lexisnexis-pricing`, `https://www.vaquill.ai/blog/legal-research-costs-what-firms-pay`
- Bloomberg Law dockets and pricing (reported): `https://help.bloomberglaw.com/docs/blh-040-dockets.html`, `https://lawguides.bc.edu/c.php?g=350895&p=2367361`, `https://www.trustradius.com/products/bloomberg-law/pricing`
- UniCourt pricing and coverage: `https://unicourt.com/pricing`, `https://unicourt.com/coverage`, `https://unicourt.com/courts/state-georgia`
- Trellis plans, coverage, documents: `https://trellis.law/plans`, `https://trellis.law/coverage`, `https://support.trellis.law/coverage-1`
- Docket Alarm pricing and API: `https://www.docketalarm.com/pricing`, `https://www.docketalarm.com/api/v1/`, `https://www.docketalarm.com/api`
- re:SearchTX terms and scope: `https://research.txcourts.gov/CourtRecordsSearch/Assets/site/termsAndConditions/TX_TermsAndConditions.html`, `https://guides.sll.texas.gov/court-records`
- judyrecords: `https://www.judyrecords.com/api`, `https://www.judyrecords.com/terms`, `https://www.judyrecords.com/info`
- Indiana MyCase document access: `https://www.in.gov/courts/help/mycase/access`
- Minnesota MCRO: `https://mncourts.gov/access-case-records/mcro`
- Franklin County CIO: `https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/`
- Orange County FL: `https://myeclerk.myorangeclerk.com/`
- Norfolk rulings: `https://www.govtech.com/public-safety/virginia-judge-rejects-alpr-evidence-without-warrant`, `https://www.vacourts.gov/static/opinions/opncavwp/0737251.pdf`
- Haiku 4.5 pricing: Anthropic price list, $1 / $5 per million input / output tokens
