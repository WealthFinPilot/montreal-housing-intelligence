# The market marts — what `fact_market` holds, and what may be done with it

> Written on 2026-08-25, at the close of session J3.5. Everything below was
> measured against the loaded archive; nothing is carried over from a plan.
>
> `docs/apciq.md` describes the SOURCE — the PDF, its licence, its defects.
> This file describes the MODEL built on it. Read the licence section of
> `docs/apciq.md` before putting any of these figures anywhere.

---

## 1. The two tables, and why there are two

| Table | Grain | Rows |
|---|---|---|
| `marts.fact_market` | quarter × geography × property type | 1 653 |
| `marts.fact_market_trailing_12m` | 12 months ending with a quarter × geography × property type | 1 653 |

1 653 is 29 quarters (2019 Q2 → 2026 Q2) × 19 geographies (the island and its
18 APCIQ sectors) × 3 categories. It is a full grid because the source prints a
full grid: a cell APCIQ cannot publish is printed as `**` or `-`, never
omitted.

**They are two tables and not one table with a period column.** Consecutive
rows of the trailing table overlap by nine months, so summing four of them
counts most sales four times. A period column would put that mistake one
mis-set slicer away in a report, where no dbt test can reach it. Two tables
make it impossible instead of detectable.

The trailing table is **not** a rolling sum of the quarterly one — see §3.

---

## 2. Three things that cannot be done with these rows

**1. `active_listings` never adds up across time.** Page 65 of the source:
« la moyenne des données mensuelles pour la période visée ». It is an average
of month-end counts. It adds across geographies, and a DAX measure that sums
four quarters of it produces a number describing nothing. Use an average over
the date dimension.

**2. The island row is not a nineteenth sector.** It is the total of the other
eighteen, published separately, so summing all 19 rows counts the island twice.
`is_island_aggregate` marks it without needing a join. It is not redundant with
the sectors either: they do not always add up to it exactly (2023 Q4 exceeds it
by 0.25 % to 1.07 %), and no aggregation of eighteen medians produces the
nineteenth.

**3. The `*_change_pct_yoy` columns are APCIQ's arithmetic, not ours.** Page 65:
« calculés par rapport au même trimestre de l'année précédente » — year over
year, never quarter over quarter. They are kept as published rather than
recomputed, because our own arithmetic would run on first-vintage figures and
would not agree. Which brings us to the finding of this session.

---

## 3. These figures are a vintage, and it is measurable

Each edition publishes its own quarter once and never revisits it, so every
figure in `fact_market` is what APCIQ printed at the time. That would be
unremarkable and invisible — except that the same editions also print a
12-month column, and comparing the two exposes it.

**Measured on 2026-08-25, over 1 482 comparable windows:**

| | |
|---|---:|
| published 12-month sales **below** the sum of its four quarters | 974 |
| **above** | 18 |
| exactly equal | 490 |
| on the island alone, above | **0 of 78** |
| island median gap | **−0.46 %** |
| island worst gap | **−1.67 %** |

Two cheaper explanations were eliminated before this was believed:

- **Not a window off by one quarter.** Read as `E-3..E`, 33.1 % of windows match
  exactly; shifted to `E-4..E-1`, 4.1 %. The source header reads
  « 12 derniers mois ».
- **Not a misread column.** `('sales', 'trailing_12m')` was never in
  `SECTOR_CONTROLLED` in `ingestion/apciq/parse.py`, so that column entered the
  database in J3.2 with no verdict attached. The J3.2 arithmetic was applied to
  it here: **the eighteen sectors add up to the island on 84 of 87
  comparisons**, the three failures being 2023 Q4, an edition already declared
  defective.

A parsing error does not produce a half-percent bias pointing one way across 29
editions. What remains belongs to APCIQ, and the source does not say what it is
— a promise to purchase later cancelled and removed, a restatement, something
else. **This document states it rather than explaining it.**

### What follows from it

- **Summing four quarters does not give APCIQ's 12-month figure**, and
  overstates it by about half a percent. When the 12-month figure is wanted,
  read the trailing table, which holds the one APCIQ publishes.
- The trailing table therefore carries information that cannot be derived. On
  counts, because of the above; on prices, because a twelve-month median is not
  the average of four quarterly medians and no arithmetic recovers it.
- `assert_trailing_12m_stays_under_the_sum_of_its_quarters.sql` holds the
  relationship under test: the gap must stay negative and within 3 %. The bound
  sits in the empty space between the worst observed value (1.67 %) and where a
  real change of behaviour would land — the same reasoning as the 1.5 size
  ratio of J3.4. The day it fails, the bound gets re-argued rather than nudged.

---

## 4. What is actually available, and where the holes are

Counts and listings are complete; prices are not. Of the 1 653 quarterly cells
per metric:

| Metric | Figures | Withheld `**` | Not printed |
|---|---:|---:|---:|
| sales | 1 653 | 0 | 0 |
| active listings | 1 653 | 0 | 0 |
| median price | 1 223 | 430 | 0 |
| average price | 1 223 | 430 | 0 |
| days on market | 1 223 | 405 | 25 |

`**` is not a gap in the reading. It is APCIQ declining to publish: « Nombre de
transactions insuffisant pour produire une statistique fiable ».

**The hole is plex.** By category, quarterly median prices:

| Category | Figures / 551 | Complete 29-quarter series (of 19 geographies) |
|---|---:|---:|
| condo | 529 | 17 |
| single-family | 394 | 8 |
| plex | 300 | 7, and 5 geographies with no series at all |

**The twelve-month table recovers 341 of the 430 withheld prices** — 22 condo,
164 plex, 155 single-family — because its sample is four times larger. Plex
goes from 300 usable prices to 464. Any sector-level analysis of plex or
single-family should expect to run on the trailing table.

The 25 not-printed cells are days-on-market rows of the 2019-era template. They
are a fourth state, distinct from `**`: nothing appeared on the page at all.

---

## 5. How a row says what it is worth

Every measure carries a `*_value_status`:

| Value | Meaning |
|---|---|
| `published` | a figure |
| `withheld` | `**` — the market exists, the statistic is not reliable enough to print |
| `nothing_to_report` | `-` — there is none of this here. L'Île-des-Sœurs has no plex |
| `not_printed` | nothing appeared on the page |

A withheld price and an absent price are different facts about the market, and
a dashboard showing both as a blank has lost the difference.

The two counted metrics also carry a `*_corroboration`, from the controls run
while reading the PDFs:

| Value | Meaning |
|---|---|
| `corroborated` | both J3.2 controls reconciled |
| `contradicted_on_its_page` | the page disagrees with itself; its reading is not settled |
| `not_reconciled_across_pages` | the page is coherent, but the 18 sectors do not match the island for this edition and category |
| `not_controlled_at_ingestion` | no verdict was recorded. **Not a synonym for "fine"** — see §3 |

**There is no corroboration column on prices or days on market, and that is not
an oversight.** Both controls are sums, and eighteen medians do not add up to a
nineteenth: no arithmetic available on these pages can check a median. A column
that always said `corroborated` would claim a verification that never happened.

### What the four flagged editions look like in the table

| Rows of `fact_market` | State |
|---:|---|
| 1 425 | fully corroborated |
| 171 | 2021 Q4, 2022 Q1, 2022 Q2 — active listings do not reconcile anywhere. **Their sales, prices and delays are sound and reconcile exactly** |
| 57 | 2023 Q4 — sectors exceed the island by 0.25 % to 1.07 % on sales while every page agrees with itself |

They are **in the table, marked**. Refusing them would have destroyed the sound
figures of those editions and the only trace of the defect at the same time —
the decision taken on 2026-08-23 and unchanged.

---

## 6. What guarantees this

| Test | What it would catch |
|---|---|
| `assert_fact_market_is_complete` | a missing or invented quarter × geography × category |
| `assert_fact_market_conserves_every_cell` | the pivot losing, duplicating or re-mapping a figure — 8 265 cells in, 8 265 out, compared on value **and** status |
| `assert_fact_market_sectors_add_up_to_the_island` | a figure moved between sectors, which leaves every row count and every stored verdict intact |
| `assert_trailing_sales_reconcile_to_the_island` | the same, on the column the parser never controlled |
| `assert_trailing_12m_stays_under_the_sum_of_its_quarters` | the vintage relationship of §3 changing sign or scale |
| `assert_property_types_still_match_the_source` | APCIQ adding or renaming a category |
| `assert_dim_date_has_no_gap` | a fact dated outside the date table, which in an imported Power BI model vanishes silently from every visual |

All seven were shown to fire, on 2026-08-25, by breaking the thing each is
meant to catch. The pivot mis-mapped: **conservation fails on 1 223 rows while
row count, uniqueness, relationships and statuses all stay green**. A sector
dropped: three tests fail and the table quietly becomes 1 566 rows. A declared
defect removed from the seed: three tests fail, including the J3.2 one.

---

## 7. What J4 must not do with these tables

1. **Do not aggregate a median.** There is no weighted median of the sectors,
   and there is no sector median of the census tracts. Affordability is
   computed by carrying the sector price down to the tracts as a stated
   assumption, never by averaging medians upward.
2. **Do not divide a 2026 price by a 2020 income without saying so.** The
   census figures are income year 2020; these prices run to 2026 Q2. The ratio
   is an assumption on display, not an observation.
3. **Do not sum `active_listings` over time**, and do not sum the island row
   with the sectors. Both are §2 above.
4. **Do not publish a figure from either table.** The licence printed on page
   65 of every edition forbids reproduction « en tout ou en partie, directement
   ou indirectement ». That covers a Power BI report published to the web,
   which exposes its whole semantic model. Nothing derived from these tables
   belongs in a versioned file either — which is why this session shipped no
   `sample_data/` extract, unlike J3.3 and J3.4.
