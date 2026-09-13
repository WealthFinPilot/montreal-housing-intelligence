# Methodology — from a published figure to a verdict on screen

This document walks the chain **once, end to end**, and says at every step which
of three things a number is: **observed** (a source published it), **derived**
(we computed it from observations, by a rule stated here), or **assumed** (we
chose it, and a reader may reject it).

It does not repeat the detail. Four documents already hold that, and each step
below names the one that owns it:

| Document | Owns |
|---|---|
| [`data-sources.md`](data-sources.md) | The seven datasets, their grain, licence and access |
| [`geography.md`](geography.md) | The three carvings of the island, and the bridges between them |
| [`apciq.md`](apciq.md) | What the Baromètre publishes, and where it contradicts itself |
| [`market.md`](market.md) | `fact_market`, and what may not be done with it |
| [`affordability.md`](affordability.md) | The mortgage chain, the seeds, and the profiles |

What each figure is *not* allowed to support is in
[`limitations.md`](limitations.md). The two documents are meant to be read
together: this one says how a number is made, that one says what it cannot be
made to say.

---

## 1. The three labels, and why they are not decoration

Principle 2 of the brief: *always distinguish observed data, derived data and
assumption*. In this project that distinction is carried in **columns**, not in
prose, because prose does not reach a Power BI report.

| Label | Carried by | Example |
|---|---|---|
| Observed | the value itself, plus a `*_value_status` | `median_price` with `median_price_value_status = 'published'` |
| Derived | a `*_basis` column naming the rule | `income_index_basis = 'cpi_rmr462'` |
| Assumed | a `*_basis` column naming the choice | `price_basis = 'apciq_sector_price_applied_to_tract'` |

A reader who rejects an assumption can filter it out. A reader who rejects a
sentence in a README cannot.

---

## 2. The chain

```
   OBSERVED                        DERIVED                     ASSUMED
   ────────                        ───────                     ───────

   APCIQ Baromètre  ─────────►  fact_market          (1)
   quarterly, 18 sectors        29 quarters × 19 areas
   + island                     × 3 property types
        │
        │                                                 sector price
        │                                                 carried down
        ▼                                                 to each tract  (4)
   StatCan census  ──────────►  bridge tables        (2)        │
   2020 income, 541 tracts      tract ↔ sector ↔ place          │
        │                                                       ▼
        │                       household_income_indexed   fact_affordability
        ▼                       restated by CPI      (3)   541 tracts × 29 qtrs
   StatCan CPI     ──────────►        │                    × 3 types × 3 profiles
   monthly, CMA 462                   │                          ▲
                                      └──────────────────────────┤
   Bank of Canada  ──────────►  fact_mortgage_scenario           │
   contracted 5y rate           payment, required income   (5)───┘
                                        ▲
                                        │
                                 3 seeds of published
                                 lending rules         (6)
```

The numbered steps are the six sections below.

---

## 3. Step 1 — The market figures *(observed)*

**Source.** The APCIQ *Baromètre résidentiel*, one PDF per quarter, 29 editions
from **2019 Q2 to 2026 Q2**. The archive does not reach 2015; that perimeter is
a documented decision, not an omission.

**Grain.** Quarter × area × property type. Nineteen areas: the eighteen APCIQ
sectors plus the island total, which is **published separately and is not their
sum** — `is_island_aggregate` marks it so no visual adds it to the other
eighteen. Three property types: condominium, single-family, plex.

**What is read.** Table 2 of each sector page, for five measures: sales count,
active listings, median price, average price, days on market — plus the
year-over-year change percentages **as APCIQ printed them**, never recomputed.

**How it is read.** The PDF contains no table object. A positional parser
recalibrates on every page, because Power BI sized each of APCIQ's tables to its
own content and the column positions move from edition to edition *and from page
to page*. Cells are **assigned to the nearest column**, never cut by fixed
bounds: a bound silently drops what falls between two bands, an assignment
places everything and refuses loudly what it cannot place.

**How it is checked.** Two independent controls, both stored as rows rather than
raised as exceptions:

- `page_table1_vs_table2` — did we read *this page* correctly? Two totals
  printed centimetres apart, read with the same column markers.
- `sectors_vs_island` — is the *source* consistent from one page to the next?

Only one is a hard stop: the sales control on a page. Everything else loads with
its verdict attached, because a source defect and a reading defect are different
problems and refusing the edition would destroy the only trace of the first.

**Detail:** [`apciq.md`](apciq.md) sections 3, 5 and 6.

### Two properties of these figures that change how they may be used

**They are a vintage.** APCIQ's published 12-month total is systematically
*smaller* than the sum of its own four published quarters — 974 windows out of
1 482, and **0 times out of 78 at the island level**, median gap −0.46 %. Two
duller explanations were eliminated before this one was believed: the window is
not shifted by a quarter, and the column is not misread. Summing four quarters
therefore does not reproduce APCIQ's annual figure and overshoots it by roughly
half a percent. The 12-month figures live in a **separate table**,
`fact_market_trailing_12m`, precisely so that no slicer can add them up.

**Not every cell carries a price.** Of the 1 566 sector cells, **430 (27.5 %)
have no published median price** — 48.1 % on plex, 30.1 % on single-family,
4.2 % on condominium — and **all 430 carry a sales count and a listing count
anyway**. A half-empty KPI row is the normal state of this data, not a symptom.

**Detail:** [`market.md`](market.md) sections 2 and 3.

---

## 4. Step 2 — The geography *(observed, with two declared exceptions)*

Three incompatible carvings of one island have to be reconciled:

| Carving | Count | Published by |
|---|---|---|
| APCIQ sectors | 18 | APCIQ, composition on page 6 |
| Administrative entities (boroughs + linked cities) | 34 | Ville de Montréal |
| Census tracts | 541 | Statistics Canada |

**The island is not defined by a polygon.** It is census division **2466** — 16
subdivisions matching the 16 municipalities exactly. The perimeter is written
`csd_uid LIKE '2466%'`, with no spatial join at all. And `csd_uid` is `'24'`
plus the MAMH municipal code, so the three sources join on **published codes**,
never on names that look alike.

**Membership is never decided by a polygon edge.** Two agencies drew the same
shoreline differently: 18 of the 541 tract polygons overflow the city's
administrative limits by up to 6.6 % of their own area, while all 3 228
dissemination-area representative points fall inside. A published code decides;
failing that, a representative point; never an edge.

**And the representative point is itself falsifiable.** Statistics Canada also
publishes each dissemination area's land area — an area cannot fit in a space
smaller than itself. That check refuted one tract that only *looked* shared (its
point had landed 10.9 m on the wrong side) and confirmed the one that genuinely
is.

**The two exceptions**, both declared on the row that carries them:

- APCIQ splits two boroughs. Verdun is split between sectors 4 and 10 — **that
  line is water**, and is not an assumption.
- CDN–NDG is split between sectors 7 and 8, and **APCIQ publishes nowhere where
  that line runs.** The city's 2014 sociological neighbourhood boundary is
  substituted for it. `assignment_method = 'neighbourhood_polygon'` carries it,
  and it places **40 tracts and 170 583 people** — 8.5 % of the island.

**Detail:** [`geography.md`](geography.md) sections 1 to 4 and 7.

---

## 5. Step 3 — The income *(observed)*

**Source.** Census 2021, table 98100058, income year **2020**, at census-tract
grain. **Total income, before tax** — the base a lender's gross-debt-service
rule looks at. After-tax income is loaded in staging and deliberately unused:
it answers a different question, and the two are not interchangeable.

**Coverage.** 530 of the 541 tracts publish an income. The other **11 are
suppressed at source** under the Statistics Act, and they are the near-empty
ones (populations of 0 to 30). They stay empty: no interpolation, no borrowing
from a neighbour.

**A trap specific to this table.** The symbol `...` ("not applicable") prints
the digit **`0`**, not a blank cell; `x` (suppressed) leaves the cell blank.
Reading "blank means missing" keeps 18 404 median incomes of **0 $** per
measure. And they cannot be swept out by discarding zeros, because 19 385
household *counts* are genuinely zero. **Only the symbol separates the two
cases**, so conversion is driven by the symbol, never by the look of the value.

### Why the income stays at the tract, and the price comes down to meet it

The price is published for a sector, the income for a tract. Averaging forty
tract medians into one sector income is arithmetic nonsense that would look
exactly like an observation. So the model does the opposite: it **carries the
sector price down to each of its tracts**, which turns the problem into a single
assumption that every row states —

```
price_basis = 'apciq_sector_price_applied_to_tract'
```

This was measured before it was chosen: **58.4 % of tract-income variance is
*within* an APCIQ sector**, and using the sector figure on a typical tract is
off by **10.6 %**, 37.6 % at the 90th percentile.

**Detail:** [`affordability.md`](affordability.md) section 2.

---

## 6. Step 4 — The restated income *(derived)*

The income is from 2020; the prices run to 2026 Q2. **No source publishes income
below the CMA after 2021** — the full Statistics Canada catalogue was swept:
8 267 cubes, and the 27 carrying "census tract" all end in 2021. Today's income
cannot be observed at this grain by anyone, at any price.

So it is restated rather than left stale, and the restatement is a calculation
that never pretends to be an observation:

```
household_income_indexed = household_income × (CPI of the quarter / CPI base 2020)
```

- **Index:** Statistics Canada table `18100004`, CMA 462 (Montréal), All-items,
  vector `41692876`, coordinate `13.2.0.0.0.0.0.0.0.0`, unit `2002=100`.
- **Base:** the average of the twelve months of 2020 = **133.6917**.
- **Range of the factor across the archive:** ×0.990089 (2019 Q2) to ×1.261609
  (2026 Q2). The factor is **below 1 before 2020** — deflating toward the past
  is the same operation, not a special case.
- **A quarter without three published CPI months gets no factor at all.**
  `income_index_basis` reads `not_indexed` and the indexed income is null. It is
  **never 1.0**, because 1.0 would assert that no inflation occurred.

Three things stated rather than buried:

1. The displayed income is **theoretical**. The word is in the measure name, the
   column header and the on-screen note, not only here.
2. The assumption is that incomes followed consumer prices, and it is wrong by a
   **measured** amount: checked once against the Canadian Income Survey
   (`11100190`), the error runs **−0.4 % to +1.3 % over 2021-2024**, and +7.8 %
   on 2019 — where the cause is named, 2020 being the peak of pandemic
   transfers.
3. Indexing moves the whole island by one factor, so it **does not repair** the
   median-of-medians problem and does not claim to.

**Detail:** [`affordability.md`](affordability.md) section 5, point 2.

---

## 7. Step 5 — The mortgage scenario *(assumed, from published rules)*

### The rate is the contracted one

Two Bank of Canada mortgage series are ingested and kept apart by two flags that
are never both true:

| Series | What it is | Flag |
|---|---|---|
| `V80691335` | Conventional 5-year — a **posted** rate, what banks advertise | `is_posted_rate` |
| `FVI_MTG_RATE_5Y_FIX` | 5-year fixed for a **high-ratio** mortgage — **contracted** | `is_contracted_rate` |

The scenario computes on the **contracted** rate, because a buyer putting down
the legal minimum is a high-ratio borrower by definition — exactly the loan this
series prices. The gap is not cosmetic: 1.84 points on 2026 Q2, worth about
15 % of the required income. And CMHC states the qualifying rate **on the
contract rate**, so stressing a posted rate applies the buffer twice.

Both rates sit on the **same row** of `fact_mortgage_scenario`, with
`posted_minus_contract_rate_points` beside them — a gap you subtract rather than
a caveat you remember.

### Every regulatory constant comes from a seed, never from SQL

Three seeds, each row carrying its own `source_url` and `retrieved_on`, because
these change by policy decision rather than by data drift.

| Parameter | Value | Applies to |
|---|---|---|
| Gross debt service (GDS) | **39 %** | insured homeowner loan |
| Total debt service (TDS) | 44 % | insured homeowner loan |
| Qualifying rate | **max(contract + 2 pts, 5.25 %)** | insured homeowner loan |
| Amortization used | **25 years** | insured homeowner loan |
| Compounding | **2 per year** | Canadian fixed-rate market convention |
| Maximum insurable price | 1 000 000 $ up to 80 % LTV · **1 500 000 $** above | insured homeowner loan |
| Premium taxed in Quebec | yes | premium payable in Quebec |

Minimum down payment is marginal by tranche (5 % to 500 000 $, then 10 %, then
20 % at 1.5 M$), and the insurance premium comes from an 11-band table keyed on
loan-to-value. **There is a real cliff at 1.5 M$**: one dollar more adds
175 000 $ to the down payment, because the property stops being insurable.

Two published controls, reproduced to the dollar: 400 000 $ → 20 000 $ and
600 000 $ → 35 000 $.

⚠️ **The 30-year amortization bands are seeded and nothing exercises them.**
Every one of the 1 653 rows carries `amortization_years = 25`.

### The chain, in order

```
price
  → minimum down payment        (bracket seed, marginal tranches)
  → loan-to-value
  → insurance premium           (band seed, keyed on LTV, taxed in Quebec)
  → loan amount
  → qualifying rate             (max(contract + 2, 5.25))
  → monthly payment             (semi-annual compounding, 25 years)
  → income_required_lower_bound (payment ÷ GDS 39 %, annualised)
```

**The order of the tests matters and is not incidental.** Legality is tested
*before* the premium band is looked up. That makes two dangerous branches cease
to exist rather than be caught: above the legal minimum a loan-to-value cannot
exceed 95 %, and above 1.5 M$ a high LTV already means "below the minimum". Both
were verified to return zero rows at seven slider positions.

### ⚠️ The name of the output is the warning

`income_required_lower_bound` is a **floor**. Gross debt service counts the
mortgage payment *plus property tax, plus heating, plus half of any condo fees*.
This project holds none of the three: the sixteen municipal tax rates are not
identified, and condo fees exist only in listings, which are phase 2. A real
applicant needs **more**, never less. That is also why `housing_burden_ratio`
is absent rather than approximated.

**Detail:** [`affordability.md`](affordability.md) sections 1, 3 and 4.

---

## 8. Step 6 — The verdict *(derived from an assumption)*

`fact_affordability` holds **141 462 rows** = 541 tracts (+1 shared) × 29
quarters × 3 property types × 3 household profiles.

The three profiles are **declared**, not discovered, and all three publish an
income in 530 of 541 tracts, so no visual has an unexplained hole:

| Code | Household size | Household type |
|---|---|---|
| `total` | Total | Total |
| `one_person` | 1 person | Non-census-family households |
| `couple` | 2 persons | One couple, with or without children |

Two verdict columns exist, and both are computed **in SQL**:

- `meets_income_requirement` — against the observed 2020 income.
- `meets_income_requirement_indexed` — against the restated income. **This is
  the one the report displays.**

They are computed in the model rather than left to DAX for a measured reason: on
2026-08-30 two definitions of one threshold coexisted in the report and
**diverged on 44 of 87 slices**. One definition, in one place, with a control
that fires.

### Two facts about the shape of this verdict

**A price-to-income ratio contains no interest rate**, and that is why the map
colours the shortfall instead. Between 2021 Q4 and 2023 Q4 the qualifying rate
went from 5.25 % to 7.59 %: the **median ratio fell 4.4 %** while the share of
affordable tracts fell **26.7 points**. A reader watching only the ratio would
conclude housing had improved.

**Two independent columns agree exactly**: `meets_income_requirement_indexed`
and `income_shortfall_indexed < 0` disagree on **0 rows out of 103 854**.

---

## 9. What the report adds on top

Three conventions exist only in the Power BI layer and are therefore stated
here, since nothing in the database carries them.

**Green means favourable to a first-time buyer, not "up".** A falling price is
green; a lengthening time-on-market is green (more time to decide); rising sales
are red (more competition). Without this stated, a green arrow on a falling
price reads as a bug.

**The change badges compare the previous calendar quarter, and three of the four
metrics are seasonal.** Measured over 21 transitions per metric at the island
level: sales rise 18 times out of 21 from Q1 to Q2 and fall 18 out of 21 from Q2
to Q3; listings rise 19 out of 21 from Q1 to Q2; days-on-market falls in 19 of
21. **Median price is the exception**: it rises 19 times out of 21 from Q1 to
Q2, like the others, but only 13 out of 21 fall back from Q2 to Q3 — it goes up
and stays up. That is a trend, not a cycle. The badge therefore names the
quarter it compares, rather than implying a direction.

⚠️ **APCIQ also publishes its own year-over-year percentages, and they do not
reproduce from our levels.** On island sales, only 31 of 75 agree exactly after
rounding, with a **signed** mean gap of +0.68 point, the published figure always
the larger. That is the vintage of section 3 seen from the other end: APCIQ
divides by a year-ago figure it has since revised downward, while this project
holds the first publication. On median price the agreement is 834 of 992 and the
signed gap is ≈ 0 — **the counts drift, the medians do not.**

**Detail:** [`../powerbi/report-design.md`](../powerbi/report-design.md).

---

## 10. Three majority rules, and why they are not one rule

The same word covers three different decisions, applied to three different
things. They are deliberately **not** shared, and substituting one for another
was measured and rejected in each case.

| Rule | Decides | Cost, measured |
|---|---|---|
| Population weight | how a shared tract's people split between two sectors | the one genuinely shared tract splits 92.9 / 7.1 |
| `is_drawn_in_this_sector` | which single sector paints a tract on a map | **476 people, 0.0237 % of the island, on 2 tracts** |
| `admin_place_name` | which place name a tract's tooltip shows | the same 476 people, on the same 2 tracts |

And a fourth case where a majority rule was **refused**: the 34 administrative
places. Verdun splits 61/39 between two sectors and CDN–NDG 59/40 — applying a
majority there would file 39 % of Verdun under a foreign figure. Three orders of
magnitude separate that from 0.0237 %: **the same rule cannot serve both
levels.**

---

## 11. Reproducing any figure in this document

Every number above comes from the live database or from a file in this
repository, and none is quoted from memory.

```bash
bash scripts/tunnel-start.sh        # reach the database
bash scripts/dbt.sh build           # rebuild everything, with its tests
python scripts/report_oracle.py     # what every KPI on the report must read
```

`report_oracle.py` is the control that matters for the report: it computes from
the marts what each card should display, so a visual with the right shape and
the wrong number cannot pass unnoticed. `scripts/generate_erd.py` rebuilds the
data-model diagram from `information_schema` and the dbt YAML, so it cannot
quietly become false after a migration.

The **proof**, throughout, is the test suite rather than a sample file: the
APCIQ licence forbids reproducing its figures, so `sample_data/` carries
StatCan and city extracts only.
