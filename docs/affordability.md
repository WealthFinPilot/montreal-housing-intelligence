# The affordability marts — what they compute, and on what

Written 2026-08-26, at the close of session J4.1. Read this before touching
`fact_affordability`, `fact_mortgage_scenario`, or any DAX built on them.

Companion to [`market.md`](market.md), which covers the price side, and to
[`geography.md`](geography.md), which covers how a census tract came to belong
to an APCIQ sector in the first place.

---

## 1. The two tables, and why there are two

| Table | Grain | Rows |
|---|---|---|
| `marts.fact_mortgage_scenario` | quarter × geography × property type | 1 653 |
| `marts.fact_affordability` | quarter × census tract × property type × household profile | 141 462 |

The split is not tidiness. **A monthly payment does not change when you look at
it through a different household profile.** Put it in the second table and it
repeats three times per tract-quarter-category, so a Power BI visual that sums
it returns three times the truth — and no dbt test reaches a Power BI visual.
Two tables make that impossible rather than merely detectable. It is the same
reasoning that produced two market tables in J3.5.

So the division is by *what a measure depends on*:

- depends on the **price** and the rules → `fact_mortgage_scenario`
  (down payment, insurance premium, loan, payment, income required)
- depends on the **household** → `fact_affordability`
  (income, price-to-income ratio, shortfall, verdict)

**One exception, deliberate and documented in the model.**
`income_required_lower_bound` is copied into `fact_affordability`, because the
shortfall is the difference between it and a household income, and reaching
across two grains from Power BI to fetch one scalar would be worse than the
repetition. It is **non-additive**: average it, take its minimum, never sum it.

`fact_affordability` holds exactly 542 × 29 × 3 × 3 rows. All four factors are
counted from upstream models by `assert_fact_affordability_is_complete.sql`,
never written as a literal, so adding an edition moves both sides together and
the assertion keeps meaning something.

---

## 2. The one assumption everything rests on

**The price is published for an APCIQ sector. The income is published for a
census tract. They do not share a grain.**

The tempting move is to average the forty tract incomes of a sector into one
sector income. It is arithmetic nonsense — eighteen medians do not average into
a nineteenth, weighted or not — and it would look exactly like an observation.

This model does the opposite. It carries the **sector price down to each of its
tracts** and computes the ratio there. That turns the problem into a single
assumption which can be stated, carried on every row, and rejected wholesale by
a reader who disagrees:

```
price_basis = 'apciq_sector_price_applied_to_tract'   -- on all 141 462 rows
```

### This was measured before it was decided

On 2026-08-26, on the 531 island tracts with a published income:

| Measure | Value |
|---|---|
| Share of tract-income variance that is **within** an APCIQ sector | **58.4 %** |
| Share **between** sectors | 41.6 % |
| Error from using the sector figure on a typical tract | **10.6 %** |
| …at the 90th percentile | **37.6 %** |
| …worst case | 210.5 % |
| Tracts more than 20 % away from their sector figure | **27.1 %** |
| Tracts more than 40 % away | 8.5 % |

The widest sector, number 11, runs from 23 400 $ to 172 000 $. Even the
tightest, number 17, runs from 45 600 $ to 67 000 $. Collapsing to the sector
throws away the larger half of the income signal.

### And it shows up again in the output

2026 Q2, condominium, couple profile: **the verdict changes from one tract to
another, at an identical price, in 17 of the 18 sectors.** Sector 12 has 2
affordable tracts out of 47; sector 15 has 24 out of 40. A sector-grain model
would have issued one verdict per sector and been wrong about a large part of
each. The opening measurement and the finished table agree by two independent
routes.

---

## 3. Where every rule comes from, and when it was read

No regulatory constant is written in SQL. Three seeds hold them, each row
carrying its own `source_url` and `retrieved_on`, because these figures change
by policy decision rather than by data drift, and a constant buried in a model
says neither where it came from nor when it was last checked.

| Seed | Rows | Holds |
|---|---|---|
| `mortgage_down_payment_bracket` | 4 | The minimum down payment, in marginal tranches |
| `mortgage_insurance_premium_band` | 11 | Premium by loan-to-value, at 25 and 30 years |
| `mortgage_underwriting_parameter` | 12 | GDS/TDS, qualifying rate, amortization, price caps, tax |

### The rules, as published

**Minimum down payment** (Financial Consumer Agency of Canada):

| Purchase price | Minimum down payment |
|---|---|
| 500 000 $ or less | 5 % |
| 500 000 $ to 1.5 M$ | 5 % of the first 500 000 $, then 10 % |
| 1.5 M$ or more | 20 % |

**There is a real cliff at 1.5 M$**, not a rounding: one dollar more on the
price adds 175 000 $ to the down payment, because the property stops being
insurable. The dashboard should show it rather than smooth it.

**Insurance premium** (CMHC), 25-year amortization, traditional down payment:
0.60 % up to 65 % LTV · 1.70 % · 2.40 % · 2.80 % · 3.10 % · **4.00 % from
90.01 % to 95 %** · 4.50 % with a non-traditional down payment. At the minimum
down payment nearly every row here sits in the 4.00 % band.

**Debt service** (CMHC): GDS 39 %, TDS 44 %.

**Qualifying rate** (CMHC Home Start eligibility sheet, verbatim): « The GDS and
TDS ratios must be calculated using an interest rate which is the greater of the
contract interest rate plus 2 per cent, or 5.25 per cent. » The same formula is
published by OSFI for *uninsured* mortgages; both are in the seed, separately,
with their own sources.

**Amortization** (CMHC, verbatim): « The maximum amortization period is 25
years; or 30 years if the LTV is greater than 80 % and the borrower is either:
(i) a first-time homebuyer or (ii) purchasing a newly built home. » The tables
compute the **25-year** scenario.

⚠️ **The four 30-year bands are seeded and nothing exercises them** — not the
marts, and not the down-payment what-if added on 2026-09-09, which reads the
25-year bands only. That was checked rather than assumed: every one of the
1 653 rows carries `amortization_years = 25`, and the single premium rate the
table has ever used is the 4.00 % band. A note written on 2026-08-31 said the
20 % threshold also puts a 30-year amortization out of reach; **it does not,
because 30 years was never within reach here in the first place.** Keeping the
down payment as the only moving variable is what makes the slider readable: two
variables moving together would let a reader attribute a change to the wrong
one.

### Two things in the seeds that are not published requirements

- **Half-yearly compounding.** The monthly rate is `(1 + annual/2)^(1/6) - 1`,
  not `annual/12`. The Interest Act permits a rate stated yearly *or*
  half-yearly, so half-yearly is **market convention, not law** — the seed row
  says `value_basis = 'market_convention'`. Using the simpler form would
  overstate every payment in the table.
- **Two of the four 30-year premium bands.** CMHC publishes only the range
  3.00 % to 4.70 % for Home Start. Both endpoints sit exactly 0.20 above their
  25-year band; the same 0.20 is carried to the two middle bands, which are
  marked `value_basis = 'derived_from_endpoint_surcharge'` rather than
  `published`.

### Positive control on the down payment rule

The seed reproduces both worked examples the Agency publishes, to the dollar:
400 000 $ → 20 000 $, and 600 000 $ → 35 000 $.

---


### One scenario in the mart, several on the page

`fact_mortgage_scenario` holds exactly one: the **legal minimum** down payment.
The column `down_payment_scenario` says so on every row, and that is why it
exists.

Since 2026-09-09 page 3 of the report lets the reader type a different amount
and recomputes the chain in DAX. **No grid of scenarios was pre-computed, and
the reason is not the row count.** A grid can only carry a *ratio* or a
*discrete amount*: the same 50 000 $ is a different percentage on each of the
751 distinct prices in the table, so a grid either answers a question nobody
asked — "what if I put down 10 %" — or discretises what a formula computes
exactly. The row count settles it either way: a six-step ratio grid would take
`fact_affordability` from 141 462 rows to **848 772**.

**What the DAX duplicates is the band-selection logic, not one published
value.** The two seeds are imported into the model and read with filters; no
rate, no threshold and no ratio is retyped. The control is
`scripts/report_oracle.py`, which computes the same chain in SQL — and, on every
run, feeds that chain the legal minimum and checks it reproduces this mart on
all 1 223 priced rows, to the cent. It did on 2026-09-09: zero differences on
the loan, the premium, the payment and the required income.

⚠️ **One published value *is* retyped, and it is named rather than hidden.**
The 80 % loan-to-value threshold above which insurance is compulsory appears
twice in `fact_mortgage_scenario.sql` and once more in the DAX. Decided on
2026-09-09: accepted, documented, and checked by the oracle rather than
promoted to a seed row. It is the one place this project's rule — no regulatory
constant in code — is knowingly bent.

**A typed down payment can be illegal, and the model refuses instead of
computing.** Below the legal minimum the loan-to-value passes 95 %, where **no
premium band exists**; a lookup that returns nothing reads as a premium of zero
and produces a loan larger than any lender would write. Measured on
2026-08-31, a naive probe did exactly that and produced a loan **1.23 times**
the legal one. The order of the tests is therefore part of the specification:
legality first, band second. With that order, "no band found" occurs **zero
times** across the whole table at every slider position from 0 to 300 000 $.

## 4. The rate is the contracted one

The payments come from **`FVI_MTG_RATE_5Y_FIX`**, the Bank of Canada's *5-year
fixed interest rate for a high-ratio mortgage* — 648 weekly observations since
2014-01-07. A buyer putting down the legal minimum **is** high-ratio, so this is
the rate for the loan actually being modelled.

`V80691335`, the **posted** 5-year rate, is carried in the same row rather than
dropped, with `posted_minus_contract_rate_points` beside it.

| 2026 Q2 | Posted | Contracted |
|---|---|---|
| 5-year rate | 6.090 % | **4.247 %** |
| Qualifying rate | 8.090 % | **6.247 %** |

A 1.84-point gap. Run through the qualifying rate and a 25-year amortization on
the median island condominium, it moves the required income by **15 %** — the
dollar figures are not reproduced here, for the reason given in section 5.4.
Worse than the gap itself:
CMHC states the qualifying rate on the **contract** rate, so stressing a posted
rate applies the two-point buffer twice.

Both series are weekly; the market table is quarterly. The rate used is the
**mean of the weekly observations inside the quarter**, and the observation
counts are carried — 9 to 14 per quarter across all 29, no quarter missing —
so a thin quarter cannot pass for a full one.

---

## 5. Four things that cannot be done with these rows

1. **Do not read `income_required_lower_bound` as the income required.** Gross
   debt service counts the mortgage payment **plus property tax, plus heating,
   plus half of any condo fees**. This project holds none of the three: the
   sixteen municipal tax rates are not identified, and condo fees exist only in
   listings, which are phase 2. The figure is a **floor**. A real applicant
   needs more, never less. This is also why `housing_burden_ratio` is absent
   rather than approximated.
2. **Do not divide 2026 by 2020 without saying so.** The income is census
   income year 2020, in 2020 constant dollars; the prices run to 2026 Q2.
   `income_year` and `price_year_minus_income_year` are on every row.

   **Since 2026-08-31 the gap is corrected as well as declared**, and the
   correction is a calculation, never an observation. The Montréal CPI (table
   `18100004`, CMA 462, All-items) restates the 2020 income into dollars of the
   displayed quarter, giving `household_income_indexed` — a **theoretical
   median income**. `household_income` is untouched and remains the reference.

   Three things about that correction, none of them optional to state:

   - **No source publishes income below the CMA after 2021.** The full
     Statistics Canada catalogue was swept on 2026-08-31: 8 267 cubes, and the
     27 carrying "census tract" all end in 2021. The T1FF reaches income year
     2023 but stops at CMA 462, which is not the Island. So today's income
     cannot be observed at this grain by anyone, at any price.
   - **The assumption is that incomes followed consumer prices, and it is
     wrong by a measured amount.** Checked once against the Canadian Income
     Survey (`11100190`, CMA 462, 2024 constant dollars): the error is between
     **−0.4 % and +1.3 % over 2021-2024**, and **+7.8 % on 2019**, where the
     cause is named — 2020 was the peak of pandemic transfers, not a normal
     year. That series is a control, measured once and written down here; it
     is not ingested and nothing depends on it.
   - **Indexing does not repair the median-of-medians problem, and does not
     pretend to.** The CPI moves the whole island by one factor, so a tract
     that gentrified since 2020 is invisible to it. Cost measured on the 529
     tracts publishing both 2015 and 2020: **4.2 % on the median tract**, 12.1 %
     at the 90th percentile, 10 tracts of 529 beyond 20 %. Compare with the
     10.6 % median error that made J4.1 refuse a sector-grain income — two and
     a half times less damaging, and it corrects a known error rather than
     creating one.

   A quarter without three published CPI months has **no factor at all**:
   `income_index_basis` reads `not_indexed`, `household_income_indexed` is
   null, and it is never 1.0. 2026 Q3 is already in that state.
3. **Do not sum anything that depends only on the price.** The rate, the
   payment and the required income repeat across the three profiles by
   construction.
4. **Do not publish a figure derived from these tables that can be inverted
   back into a price.** The price inside them is APCIQ's, and page 65 of every
   edition forbids reproduction « en tout ou en partie, directement ou
   **indirectement** ». A price-to-income ratio times a published census income
   gives the price back.

   **The rule was settled on 2026-09-13 and is now enforced rather than
   stated**: a figure may appear in a tracked file only if it cannot be inverted
   into an APCIQ price. Shares, counts, rates, rate gaps, CPI factors and
   percentage changes pass; prices, price-to-income ratios **in level** and
   required incomes in dollars do not. `scripts/check_apciq_figures.py` checks
   it against the figures actually in the database, and runs inside
   `check-secrets.sh`. See `limitations.md` limitation 4.

---

## 6. What is available, and where the holes are

- **430 of the 1 653** sector-quarter-category combinations have no published
  median price (`**` in the source). Those rows exist, carry
  `median_price_value_status`, and produce a null ratio — never a zero.
- **11 of the 541 tracts** have no published income: the near-empty ones
  suppressed under the Statistics Act, seven of which hold no population at
  all. They keep their rows. Nothing is interpolated and nothing is borrowed
  from a neighbour.
- **Three household profiles, out of the 77 the census publishes.** Coverage of
  the 77 runs from 530 tracts down to 0, and 20 of them have fewer than half.
  The three kept — all households, one person, couple of two — are at 530 of
  541 each. `assert_household_profiles_still_match_the_source.sql` fails if any
  of them drops below 500, which is the middle of a measured gap: the next best
  profiles sit at 529, 525 and 524, and the ones that collapse sit at 250 and
  below.
- **40 tracts carry `assignment_method = 'neighbourhood_polygon'`.** APCIQ does
  not publish where its line between Côte-des-Neiges and Notre-Dame-de-Grâce
  runs; the City's 2014 sociological boundary is substituted. That is the
  largest single assumption in the geography and it reaches 170 583 people.
  See `geography.md`.

### What the table says today

2026 Q2, condominium, 513 tracts with both a price and an income. **Counts
only**: a median price-to-income ratio multiplied by a census income — which
Statistics Canada licenses for redistribution — returns the APCIQ price, so the
ratios themselves are not reproduced in this file. Section 5.4.

| Profile | Tracts meeting the income floor |
|---|---|
| Couple, two persons | 179 of 513 |
| All households | 78 of 513 |
| One person | **1 of 513** |

The spread between the three is the point: on the same tracts, at the same
prices, a single-person household clears the floor almost nowhere on the island
while a two-person couple clears it in roughly a third of it.

---

## 7. What guarantees this

`dbt build --full-refresh`: **PASS=268, ERROR=0**. 115 pytest tests, unchanged
by this session — no Python was touched except the series catalogue.

Four singular tests do the work the structural ones cannot:

| Test | Catches |
|---|---|
| `assert_affordability_carries_the_price_and_income_it_claims` | Either lookup wired to the wrong thing |
| `assert_fact_affordability_is_complete` | A join that multiplies or drops rows |
| `assert_affordability_never_invents_a_missing_figure` | A ratio computed from a missing input |
| `assert_household_profiles_still_match_the_source` | A relabelled census dimension |

**All four positive controls were run, and all four fire.**

| Sabotage | What saw it |
|---|---|
| Price taken from the **neighbouring sector** | **18 structural tests stayed green.** Only the conservation test failed |
| An en dash changed to a hyphen in one census label | The build stopped |
| `coalesce(income, 0)` slipped into the model | Two tests failed |
| The zero-weight bridge row let back in | The completeness test saw it |

The first one matters most, and it repeats the lesson of J3.5 exactly: row
count, uniqueness, relationships and accepted values saw **nothing** wrong with
a table whose every price came from the wrong place.
