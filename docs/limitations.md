# Limitations — what this model may not be made to say

Every limitation below is **measured or sourced**, never estimated, and each one
names the column, test or file that carries it in the model. Where a figure
appears, it was recomputed against the live database on **2026-09-13** rather
than quoted from an earlier session.

[`methodology.md`](methodology.md) says how each number is made. This document
says what it cannot support. They are meant to be read together.

Three severities, and they mean different things:

| | Meaning |
|---|---|
| **Blocking** | A conclusion drawn past this is simply wrong. No wording fixes it. |
| **Material** | The figure is usable, but a specific sentence is forbidden. |
| **Noted** | A real constraint, measured, that a reader should know about. |

---

## Index

| # | Limitation | Severity |
|---|---|---|
| 1 | The price is a sector's; the income is a tract's | **Blocking** |
| 2 | "X % of sectors" is not "X % of Montrealers" | **Blocking** |
| 3 | `income_required_lower_bound` is a floor, not a requirement | **Blocking** |
| 4 | APCIQ figures may not be published, even indirectly | **Blocking** |
| 5 | The income is from 2020 and cannot be observed later | **Material** |
| 6 | One boundary is assumed, and it places 170 583 people | **Material** |
| 7 | Quarterly figures are a vintage: 12 months ≠ four quarters | **Material** |
| 8 | Four editions contradict themselves, and are loaded anyway | **Material** |
| 9 | 27.5 % of sector cells carry no price at all | **Material** |
| 10 | The contracted rate stopped publishing on 2026-06-02 | **Material** |
| 11 | Every figure on the affordability page assumes one type and one quarter | **Material** |
| 12 | 26 of 34 places show a larger territory than the one asked for | **Material** |
| 13 | No listings: no area, no price per square foot, no condo fees | **Material** |
| 14 | Association, never cause | **Material** |
| 15 | 476 people are drawn in a sector that does not count them | Noted |
| 16 | 11 tracts publish no income, and stay empty | Noted |
| 17 | History starts in 2019 Q2, not 2015 | Noted |
| 18 | Revisions overwrite: no publication history is kept | Noted |
| 19 | The shortfall map scale is calibrated on the archive, not on the slice | Noted |
| 20 | Power BI runs in Import mode, republished by hand | Noted |
| 21 | Three known debts in the model, none of them silent | Noted |

---

## 1. The price is a sector's; the income is a tract's — **Blocking**

APCIQ publishes a median price for each of **18 sectors**. Statistics Canada
publishes a median income for each of **541 census tracts**. They do not share a
grain, and no arithmetic joins them without an assumption.

**What is forbidden:** averaging the tract incomes of a sector into "the income
of that sector". Eighteen medians do not average into a nineteenth, weighted or
not, and the result would look exactly like an observation.

**What the model does instead:** it carries the sector price **down to each
tract** and computes the ratio there — one assumption, stated on all 141 462
rows as `price_basis = 'apciq_sector_price_applied_to_tract'`, which a reader
can reject wholesale.

**What that choice costs, measured before it was made:** **58.4 % of
tract-income variance sits *within* an APCIQ sector.** Using the sector figure
on a typical tract is off by **10.6 %**, 37.6 % at the 90th percentile, and
27.1 % of tracts are more than 20 % away.

**Detail:** [`affordability.md`](affordability.md) section 2.

---

## 2. "X % of sectors" is not "X % of Montrealers" — **Blocking**

`Share of tracts affordable` counts **census tracts**, not people. A tract
counts as affordable when **its median household** clears the bar for **the
median property of its sector** — two medians, never a population. Inside a
tract that fails, up to half the households are above the median.

**What is forbidden:** any sentence of the form "N % of Montrealers can afford".
The model cannot produce it. It would need the full income distribution, and
table 98100058 publishes medians only.

**The exact wording that is both strong and verifiable:** *in 2026 Q2, in
**99.2 % of the island's census tracts**, a single person on their
neighbourhood's median income cannot buy their sector's median condominium,
with the minimum down payment and no other capital.*

**What carries it:** `Method note`, permanently on screen.

---

## 3. `income_required_lower_bound` is a floor, not a requirement — **Blocking**

Gross debt service counts the mortgage payment **plus property tax, plus
heating, plus half of any condo fees**. This project holds none of the three:
the sixteen municipal tax rates are not identified, and condo fees exist only in
listings, which are phase 2.

**What is forbidden:** reading the column as "the income required". A real
applicant needs **more**, never less. The name says so, in the model, where a
report author reads it — not only here.

**Consequence:** `housing_burden_ratio` is **absent rather than approximated**.
Publishing it would require inventing two of its three terms.

**Detail:** [`affordability.md`](affordability.md) section 5, point 1.

---

## 4. APCIQ figures may not be published, even indirectly — **Blocking**

Page 65 of every edition: « Toute reproduction de l'information qui s'y
retrouve, en tout ou en partie, directement ou **indirectement**, est strictement
interdite sans l'autorisation préalable écrite du titulaire du droit d'auteur. »

A written request was sent before 2026-08-25. **No answer as of 2026-09-13.**

**The operative rule, decided 2026-09-13: a figure may appear in a tracked file
only if it cannot be inverted into an APCIQ price.**

| Publishable | Not publishable |
|---|---|
| a share of tracts, a count, a percentage change | a median or average price |
| a rate, a rate gap, a CPI factor | a price-to-income ratio **in level** |
| a row count, a coverage rate | a required income **in dollars** |

The second column is not a matter of taste: **a price-to-income ratio times a
published census income gives the price back**, and census income is
redistributable under the Statistics Canada licence. That is reproduction
"indirectly" in the sense of page 65.

**What enforces it:** `bash scripts/check-secrets.sh` sweeps every tracked file
against the figures actually loaded in `raw.apciq_barometer_statistic`. The
control has a positive control of its own: planting a real median price in a
copy of a document makes it fire.

**What follows from it:**
- The whole git history was rewritten on 2026-08-23 to remove APCIQ figures.
- A `.pbix` that has loaded APCIQ figures **is never committed**; `*.pbix` is in
  `.gitignore`.
- `sample_data/` carries StatCan and city extracts only. **The proof for the
  market layer is the test suite, not a sample file.**

**The one debt this rule exposed is paid.** Price-to-income ratios in level had
been sitting in `powerbi/report-design.md` since 2026-08-30. They were removed on
2026-09-13 and the acceptance cases now point to `scripts/report_oracle.py`,
which computes them against the database instead of freezing them in a file.
The control was re-run on 2026-09-14: no APCIQ figure in any of the 184 tracked
text files it searches.

**Detail:** [`apciq.md`](apciq.md) section 1, [`market.md`](market.md)
section 7.4.

---

## 5. The income is from 2020 and cannot be observed later — **Material**

Census income year **2020**; prices run to **2026 Q2**. The gap on each row runs
from **−1 to +6 years** — negative for the three quarters of 2019, where the
ratio divides a price by an income from its own future.

**This is not a gap anyone can close.** The full Statistics Canada catalogue was
swept on 2026-08-31: **8 267 cubes, and the 27 carrying "census tract" all end
in 2021.** The T1FF reaches income year 2023 but stops at CMA 462, which is not
the island.

**What the model does:** restates the 2020 income by the Montréal CPI into
dollars of the displayed quarter — a **theoretical median income**, factor
×0.990089 to ×1.261609 across the archive, carried by `income_index_basis`.
`household_income` is untouched and remains the reference.

**What is forbidden:** calling the restated figure an observation, or comparing
two quarters without saying which basis is displayed. And **never substituting
1.0 for a missing factor** — a quarter without three published CPI months reads
`not_indexed`, with its reason, because 1.0 would assert that no inflation
occurred.

**What the restatement is worth, measured once:** against the Canadian Income
Survey, the error runs **−0.4 % to +1.3 % over 2021-2024**, and **+7.8 % on
2019** — 2020 being the peak of pandemic transfers, not a normal year.

⚠️ **Indexing does not repair limitation 1 and does not claim to.** One factor
moves the whole island, so a tract that gentrified since 2020 is invisible to
it — 4.2 % on the median tract.

**What it changes, and it is most of the headline** (condominium × couple, share
of evaluable tracts counted as **distinct tracts**, the way the report counts
them, measured 2026-09-14): the share of affordable tracts falls from 93.2 % to
**35.0 %** when read in 2020 dollars, but only from 92.5 % to **78.1 %** once
restated. **Three quarters of the fall is the frozen income, not the market.**

**And the 2022 Q2 break survives the restatement** — **−15.6 points** in 2020
dollars, still **−9.6 points** restated.

*(Counting fact rows instead gives 34.9 %, 78.2 % and −15.8: the one genuinely
shared tract, `4620511.02`, holds two rows. Both counts are arithmetic; only the
distinct-tract count is what the report displays, so a document quoting the row
count would disagree with the screen.)* The break belongs to the market; the
slope belongs to the vintage.

---

## 6. One boundary is assumed, and it places 170 583 people — **Material**

APCIQ splits two boroughs between two sectors each. One of those lines is
published by nature, the other is not, and they must not be lumped together:

| Borough | Sectors | Status |
|---|---|---|
| Verdun | 4 and 10 | **The line is water.** Not an assumption. 22 tracts. |
| Côte-des-Neiges–Notre-Dame-de-Grâce | 7 and 8 | **APCIQ publishes nowhere where it runs.** |

For CDN–NDG the city's **2014 sociological neighbourhood boundary** is
substituted — a line drawn for community consultation, not for real estate. It
places **40 tracts and 170 583 people, 8.5 % of the island.**

**What is forbidden:** presenting a sector 7 or sector 8 figure as resting on a
published boundary.

**What carries it:** `assignment_method = 'neighbourhood_polygon'` on every
affected row, and `boundary_is_assumed` on the map shapes, bounded by a test to
exactly 2 shapes.

**And there is no APCIQ median price for the borough CDN–NDG at all** — two
medians of two overlapping-but-different populations do not combine into one.
The bridge returns two rows rather than one confident wrong number.

**Detail:** [`geography.md`](geography.md) sections 4 and 7.

---

## 7. Quarterly figures are a vintage: 12 months ≠ four quarters — **Material**

APCIQ's published 12-month total is systematically **smaller** than the sum of
its own four published quarters: **974 windows out of 1 482**, and **0 times out
of 78 at the island level**, median gap −0.46 %, worst −1.67 %.

Two duller explanations were eliminated before this one was believed: the window
is not shifted by a quarter (33.1 % exact matches against 4.1 %), and the column
is not misread (84 sector→island sums exact out of 87).

**What is forbidden:** summing four quarters and calling the result APCIQ's
annual figure. It overshoots by roughly half a percent.

**What makes it impossible rather than detectable:** the 12-month figures live
in a **separate table**, `fact_market_trailing_12m`. A `period_type` column
would have left the mistake one mis-set slicer away, and **no dbt test reaches a
Power BI report.**

**The same fact from the other end:** APCIQ's own year-over-year percentages do
not recompute from our levels. On island sales, 31 exact agreements out of 75,
signed mean gap **+0.68 point**, the published figure always larger — APCIQ
divides by a year-ago figure it has since revised down. **The counts drift; the
medians do not** (834 of 992, signed gap ≈ 0).

**Detail:** [`market.md`](market.md) section 3.

---

## 8. Four editions contradict themselves, and are loaded anyway — **Material**

Measured across all 29 editions, 1 363 controls, 83 failures on 4 editions —
and they are not of the same kind:

| Editions | What fails | Usable? |
|---|---|---|
| 2021 Q4, 2022 Q1, 2022 Q2 | **Active listings reconcile nowhere** — not across pages, not sectors against island (−45 %) | **No inventory figure at any geography.** Sales, prices and delays are exact. |
| 2023 Q4 | Sectors exceed the island by 0.25 % to 1.07 % on quarterly sales; every page is self-consistent 19 times out of 19 | Yes, if said. |

**Why they were loaded rather than refused:** rejecting them would have
destroyed 3 420 figures whose prices and sales reconcile to the digit — **and
the only trace of the defect at the same time**. A control that merely raises an
exception leaves nothing behind when it passes: six months later, nobody can
tell a verified edition from one that was never checked.

**What carries it:** `sales_corroboration` and `active_listings_corroboration`
on every row (57 rows per affected edition), plus the seed
`apciq_known_publisher_defect`, which fails in **both** directions — on an
undeclared failure, and on a declaration that no longer matches anything. The
second direction matters more: an unreviewed waiver is how a workaround becomes
permanent.

**Detail:** [`apciq.md`](apciq.md) section 7.

---

## 9. 27.5 % of sector cells carry no price at all — **Material**

Of the 1 566 sector cells, **430 have no published median price**, and **all 430
carry a sales count and a listing count anyway.** A half-empty KPI row is the
normal state of this data, not a symptom.

| Property type | Sector cells without a price |
|---|---|
| Plex | **48.1 %** |
| Single-family | 30.1 % |
| Condominium | 4.2 % |

Counted the way a reader meets it: **100 of the 541 tracts never have a plex
price in any of the 29 quarters**, 5 never have a single-family price, and
**none is ever missing a condominium price.**

**What is forbidden:** reading a blank as a zero, or as "no market". APCIQ
withholds a median when there were too few transactions to publish one.
`median_price_value_status` distinguishes `published` from `withheld`.

⚠️ **This is where the blank/zero trap lives.** In DAX, `AVERAGE` over an empty
set returns `BLANK()`, and `BLANK() <= income` is **true** for any income. The
mechanism has surfaced **ten times** in this project. Every measure comparing an
aggregate to a threshold needs an explicit `NOT ISBLANK`.

---

## 10. The contracted rate stopped publishing on 2026-06-02 — **Material**

`FVI_MTG_RATE_5Y_FIX` is the rate the whole mortgage chain computes on. Measured
2026-09-13:

| Series | Last observation | Days since | Usual gap | Largest gap ever |
|---|---|---|---|---|
| `FVI_MTG_RATE_5Y_FIX` | **2026-06-02** | **103** | 7 days | **7 days** |
| `V80691335` (posted) | 2026-09-09 | 4 | 7 days | 7 days |
| `V39079` (policy) | 2026-09-08 | 5 | 1 day | 5 days |

In 596 observations that series never once went more than 7 days without
publishing. It has now gone **fourteen and a half weeks**, while the other two
series ingested by the same pipeline on the same day are current. **The pipeline
is fine; the source has gone quiet.**

Valet answers HTTP 200 and says nothing about a discontinuation. **Suspended,
withdrawn or late is unknown, and is guessed nowhere.**

**What is forbidden:** presenting the mortgage scenario for a quarter APCIQ
publishes after this date as if it had a contracted rate.

⚠️ **Nothing says this on screen any more.** `Rate freshness warning` was
removed from page 4 on 2026-09-12. **dbt freshness stays green on it**, because
freshness answers a different question — whether *our ingestion* is recent, not
whether *the source* still publishes.

---

## 11. Every figure on the affordability page assumes one type and one quarter — **Material**

Page 3 of the report computes as if exactly one property type and exactly one
quarter were selected. The slicers are set to single-select, **and a slicer
setting is one click from being changed.**

What happens then was measured:

| If the reader releases… | Effect |
|---|---|
| the property type | average required income **+49 %**; sectors within reach fall from 7 to **2** |
| the quarter | sectors within reach rise from 7 to **14** |

**Every one of those pages looks correct.** Nothing errors, nothing blanks.

⚠️ `Slice warning` was written for exactly this and **removed from the screen on
2026-09-12**. The measure still exists in the model, read by no visual. This
limitation is the only thing that now states the assumption.

---

## 12. 26 of 34 places show a larger territory than the one asked for — **Material**

APCIQ prices a **sector**, and a sector usually holds several administrative
entities. Reading it the reassuring way — "32 of 34 entities resolve to exactly
one sector" — invites the wrong conclusion. Counted in the direction that
matters:

| Entities also shown when one is picked | Entities |
|---|---|
| none — the sector holds only it | **8 of 34** |
| one more | 10 |
| two more | 1 |
| three more | 8 |
| **six more** | **7** |

Picking Beaconsfield returns the figures of **seven municipalities**. Picking
Westmount returns Hampstead, Mont-Royal and Outremont with it.

**What is forbidden:** labelling a filtered figure with the name the reader
clicked. Naming what is actually on screen is **a permanent requirement for
twenty-six of thirty-four**, not a courtesy for two edge cases.

⚠️ **And a sector name is not a place.** Sector 9 is called "Centre" and
contains Hampstead, Mont-Royal, Outremont and **Westmount** — none of them
central. Sector names must never be read as geography.

**Detail:** [`geography.md`](geography.md) section 4.

---

## 13. No listings: no area, no price per square foot, no condo fees — **Material**

Listings are phase 2 and the MVP works without them by design. What their
absence removes, all of it named in the original brief:

- **No living area**, therefore **no price per square foot** — so the brief's
  question "are dwellings getting smaller, or only dearer?" cannot be answered.
- **No condo fees**, which is one of the three missing terms of limitation 3.
- **No bedroom or configuration grain**: the condominium analysis stops at the
  property type.
- **No asking price**, therefore no asking-versus-sale gap and no listing-event
  history.

**What must be carried into phase 2 rather than discovered there:** a listing
observed is not a market — what is advertised is a biased sample of what exists.
And **a withdrawn listing is not a sale**: it may have sold, expired, been
withdrawn, or been relisted under another identifier. No automatic
qualification, ever.

**Also out of scope by decision:** individual transactions (phase 3), the MAMH
assessment roll (extracted on disk, deliberately not loaded — and a municipal
assessment **is not a sale price**), and the five-variable FTB score of the
brief's section 25.

---

## 14. Association, never cause — **Material**

The project relates interest rates, prices, volumes, inventory and time on
market. Those are **statistical relationships**. Nothing here identifies a
causal effect: no instrument, no natural experiment, no control for what else
moved.

**What is forbidden:** "rates caused prices to fall". Write "prices fell over a
period when rates rose", or "the two are associated".

**A concrete reason to be careful here:** a price-to-income ratio **contains no
interest rate at all**. Between 2021 Q4 and 2023 Q4 the qualifying rate went
from 5.25 % to 7.59 %, the **median ratio on the restated income fell 4.5 %**,
and the share of affordable tracts fell **26.5 points**, from 82.8 % to 56.3 %. A reader watching only the ratio would
conclude that housing had improved.

---

## 15. 476 people are drawn in a sector that does not count them — Noted

A tract genuinely split between two sectors is **counted** in both, by
population weight (92.9 / 7.1), but a map can only **paint** it once. The
drawing rule puts it in the sector holding the majority of its inhabitants.

**Cost, measured:** **476 people, 0.0237 % of the island, on 2 tracts.** The
figures and the drawing stop applying the same rule for those two.

**What carries it:** `is_drawn_in_this_sector`, and a test bounding the effect
to 1 % of the island — **an order-of-magnitude guard, not a validation of the
0.0237 %**, and the test says so.

The same 476 people are also named after the wrong place in map tooltips, by a
third majority rule. **The three majority rules are deliberately not shared**,
and a fourth was refused outright: applying one to the 34 administrative places
would file 39 % of Verdun under a foreign figure.

---

## 16. 11 tracts publish no income, and stay empty — Noted

11 of the 541 tracts have no 2020 income: **suppressed at source** under the
Statistics Act, and they are the near-empty ones (populations of 0 to 30). Seven
have no population at all.

**They stay empty.** No interpolation, no borrowing from a neighbour. They are
simply not evaluable, and `household_income_status = 'suppressed'` says which.

In practice, on 2026 Q2 condominium, **513 tract rows out of 542 are evaluable**
— 18 lack a price, 11 lack an income.

⚠️ **The suppression is not uniform across household profiles.** Sweeping all 77
size × type combinations, published counts run from **0 to 530**. The three
profiles the model uses are all at 530, deliberately — but a sample of
well-populated profiles says nothing about the coverage of a 77-value dimension.

---

## 17. History starts in 2019 Q2, not 2015 — Noted

The brief targeted 2015. The APCIQ quarterly archive does not reach further back
than **2019 Q2** — 29 consecutive quarters, verified 2026-08-21. Accepted as
sufficient and displayed rather than hidden.

Bank of Canada series are unaffected and start in 2015 here, which means **the
rate history is longer than the market history**. Any chart putting them side by
side must not suggest the market series is missing data before 2019.

---

## 18. Revisions overwrite: no publication history is kept — Noted

The raw layer keeps the latest value of an observation; a revised figure
replaces the previous one. `updated_at` moves only when a value actually
changed, so it means "the source revised this" rather than "the pipeline ran
again".

**What is forbidden:** any statement about what a source said at an earlier
date. This project analyses the market; it does not audit its sources.

---

## 19. The shortfall map scale is calibrated on the archive, not on the slice — Noted

**Measured and consciously not corrected.** The diverging scale of the page 2
map is fixed at −60 000 $ / +150 000 $, clipping 1.31 % and 3.05 % **of the
103 854 rows of the archive**. But the map shows **one slice at a time**, and on
2026 Q2: **27.2 % of shapes are clipped at the red end**, and 55.5 % sit in the
outer red third. On plex for a single person, **313 shapes of 317**.

Across the nine type × profile slices, **the median ratio of the widest slice is
4.37 times that of the narrowest**. One fixed scale cannot serve nine
distributions that far apart. *(The ratios themselves are not written here: a
price-to-income ratio in level is invertible into an APCIQ price — see
limitation 4. A ratio of two ratios is not.)*

**What is forbidden:** comparing the intensity of two different slices.

Should the question reopen, measurement already eliminates the obvious fix: a
**symmetric** auto scale starves the weak arm to 12-16 % of the palette on 4 of
the 9 slices.

---

## 20. Power BI runs in Import mode, republished by hand — Noted

No gateway, no scheduled refresh, no DirectQuery — deliberately. The analytical
grain is quarterly, so freshness is not the issue, and "Publish to web" is
incompatible with DirectQuery in any case.

**Consequence:** a report file is a snapshot. It shows the data of the last
manual republication, not of the database.

**And the report file itself is never committed** — see limitation 4.

---

## 21. Three known debts in the model, none of them silent — Noted

Written down so they are not rediscovered as surprises:

1. **`('sales', 'trailing_12m')` never got a parser verdict.** The column
   entered the database in J3.2 outside `SECTOR_CONTROLLED`, and it is the
   column the vintage finding of limitation 7 rests on.
   `assert_trailing_sales_reconcile_to_the_island.sql` applies the sector→island
   control to it **in SQL**, which is how the finding could be believed. Paying
   it properly costs a re-read of the 29 PDFs.
2. **The 80 % loan-to-value threshold lives in three places** — twice in
   `fact_mortgage_scenario.sql`, once in DAX — and none of them says where it
   comes from. This is the one place where the rule "no regulatory constant in
   code" is knowingly bent. The control is `scripts/report_oracle.py`.
3. **The 30-year amortization bands are seeded and nothing exercises them.**
   Every one of the 1 653 rows carries `amortization_years = 25`. They are not
   wrong, they are unused — and an unused seed row is a rule nobody is checking.

---

## What guarantees the rest

Everything not listed above is guarded by something that fails loudly: **321
dbt tests** — the `PASS=353` of a build also counts its 25 models and 7 seeds —
and **140 pytest tests**, of which a set run against the real
database inside a transaction that is always rolled back.

Positive controls are run on the guards themselves rather than assumed — and
**twice they found holes in the tests rather than confirming them**: a
de-duplication removed without the test noticing, and a majority rule inverted
while 39 tests stayed green because the ceiling it was measured against was a
magnitude, not a rule.

**A green test on an empty table proves nothing** — that sentence was written in
this repository before it happened, and it happened anyway.
