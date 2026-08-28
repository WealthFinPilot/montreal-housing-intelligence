# Report design

Four pages, and every measure they need. The connection, the tables and the
relationships are in [README.md](README.md); build the model there first.

---

## 1. What this report has to say

One finding carries the report, and it was measured on 2026-08-27 against the
finished tables:

> For a two-person couple looking at a condominium, the share of island census
> tracts whose median household income reaches the required income falls from
> **93.2 % in 2019 Q2 to 34.9 % in 2026 Q2**.

The fall is not smooth, and the report should not smooth it. It is gradual
until 2022 Q1, drops by sixteen points in a single quarter — 2022 Q2 — keeps
falling to a floor around 30 % in late 2023, then moves sideways between 34 %
and 40 % for the two and a half years since. A line chart by quarter shows all
of that; the same chart grouped by year hides the break entirely.

Three forces are tangled in that number and the report must keep them apart,
because a reader will otherwise assume it is all price:

* prices rose,
* the contracted mortgage rate moved,
* **the income did not move at all** — it is the 2020 census, unindexed, for
  every quarter from 2019 to 2026.

The third one is not a detail to disclose at the bottom of a page. It is the
reason `income_year` and `price_year_minus_income_year` sit on every row of
`fact_affordability`, and the reason page 2 shows the gap rather than mentioning
it.

---

## 2. The four pages

### Page 1 — Market

*What actually happened, at the grain APCIQ publishes.*

| Element | Field or measure |
|---|---|
| Slicer | `dim_property_type[name_en]`, single select, **required** |
| Slicer | `dim_date[quarter_label]` |
| KPI row | `Sales (island, as published)`, `Median price`, `Days on market`, `Active listings (island)` — visual filter `Sector[geography_type] is island` |
| Line | `Median price` by `dim_date[quarter_label]` — same visual filter |
| Bar | `Median price` by `Sector[name]`, sorted descending — visual filter `Sector[geography_type] is apciq_sector` |
| Table | `Sector[name]`, `Median price`, `Price status`, `Sales (sectors)` — same as the bar |

**The bar ranks the eighteen sectors by price, and it did not always.** It was
first specified as `Sales (sectors)` by sector; that chart is dominated by how
large a sector is — sector 1 spans seven municipalities — so it mostly restates
the housing stock, and a tall bar reads as a hot market when it means a big one.
`Median price` is not confounded that way, each bar is one figure APCIQ printed,
and it answers the question the page asks. `Sales (sectors)` keeps two jobs
elsewhere: the reconciliation control, and page 4, where the axis is time and a
sector compared with itself is no longer confounded by its size.

⚠️ **A sector whose median APCIQ withheld has no bar, and a missing bar reads as
a zero.** That is why the table beside it carries `Price status`: the bar gives
the ranking, the table says why a place is empty. Never the bar alone. Switch
the property type to Plex and the effect is immediate.

**Every visual on this page carries a geography filter, and none of them is
optional.** The bar and the table exclude the island so it does not sit beside
its own eighteen parts. The KPI row and the line do the opposite for a different
reason: `Median price` and `Days on market` count the rows left standing
and return blank above one, so without `is island` they would read blank on a
page that has nineteen geographies in scope. The two island measures carry their own
island filter and are indifferent to it.

**Single select on property type is not a preference.** `Median price` returns
blank whenever the selection covers more than one published cell, which is what
happens the moment two property types are in play. That is deliberate — see
section 3 — and a required single-select slicer is what turns a confusing blank
into an obvious control.

**Both slicers are load-bearing, and the quarter one is the less obvious of the
two.** `Median price`, `Price context`, `Price status` and `Days on market`
return blank above one surviving row. With the
island filter and one property type but *no* quarter, twenty-nine rows survive —
one per published quarter — so the price and the days-on-market cards read
blank. The quarter slicer is not a convenience; it is what makes half the page
non-empty. Set it to **Dropdown** (Format > Slicer settings > Options > Style),
single select, and leave the newest quarter selected when saving.

**Then set every interaction by hand, because the page has two geographic zones
that exclude each other.** The KPI cards and the price line accept only the
island row; the bar and the table accept only the eighteen sectors. Left on
their defaults, a click in one zone filters the other to
`island AND apciq_sector`, which is the **empty set** — the cards read `--`, the
line vanishes, the table empties. That is not a rendering fault and the values
are not merely small: there is nothing left to show.

It also looks different depending on the target, which is worth knowing before
diagnosing it. A chart that receives a selection **cross-highlights**: it keeps
its full height in a pale tint and paints the selected share solid, so an empty
selection reads as bars that have gone faint rather than as bars that have gone.
A table cannot highlight — it can only be filtered — so it simply empties.

**Format > Edit interactions**, then set each source visual in turn:

| Source clicked | KPI cards | Price line | Sector bar | Table |
|---|---|---|---|---|
| Property type slicer | Filter | Filter | Filter | Filter |
| Quarter slicer | Filter | **None** | Filter | Filter |
| Price line | **None** | — | **None** | **None** |
| Sector bar | **None** | **None** | — | Filter |
| Table | **None** | **None** | None | — |

Three rules produce that table. **The two slicers drive everything**, because
they are the only controls whose scope is the whole page. **The price line
drives nothing**: its axis is the quarter, which the slicer already governs, and
it is meant to stand still as the history behind the selected quarter. **Nothing
crosses between the zones**, in either direction. The one cross-filter left
alive is bar → table, which is the only pair that shares a scope: click a sector
in the bar, read its row in the table.

**The date dimension is wider than this page, and stays that way.** `dim_date`
starts on 2015-01-01 because the Bank of Canada series are daily and weekly from
then; page 4 uses those years. `fact_market` starts in 2019 Q2. Narrowing the
dimension would amputate page 4, so the quarters with no market data are removed
per visual — the slicer carries a visual filter
`Sales (island, as published) is not blank` — never from `dim_date` itself.

### Page 2 — Affordability

*The same market, read against what households earn, at the census tract.*

| Element | Field or measure |
|---|---|
| Slicers | property type (single select), `dim_household_profile[name_en]`, quarter |
| KPI | `Share of tracts affordable`, `Tracts evaluated`, `Income required, lower bound (mean)` |
| Line | `Share of tracts affordable` by `dim_date[quarter_label]` — **the finding** |
| Bar | `Share of tracts affordable` by `Sector[name]` |
| Table | `Census Tract[name]`, `Price to income (median)`, `Income required, lower bound (mean)`, `Verdict` |
| Card | `Income vintage warning` |
| Card | `Grain warning` |

`Grain warning` prints only when a census tract is filtering, which is exactly
when a market measure on the same page would be repeating a sector total once
per tract. Put it in the title of any visual that mixes the two grains.

### Page 3 — First-time buyer

*The decision question of section 31 of the brief.*

**This page is at the SECTOR grain, and page 2 is at the census tract. That is
not an inconsistency — it is the answer to two different questions.**

Page 2 compares the required income to the income households in each tract
actually earn, and that varies from tract to tract inside one sector: it is why
the model is built at the tract at all. Page 3 compares the required income to
**one income the user types in**, which is the same everywhere. Since the
required income depends only on the price, and the price is the sector's, every
tract of a sector returns the identical verdict.

Measured on 2026 Q2, condominium, couple, at 95 000 $: **every one of the
eighteen sectors is either all of its tracts or none of them.** A table of 541
rows here would show 541 copies of eighteen answers and imply a precision that
does not exist. So the page is built on the sector, and the tract count appears
only as coverage.

| Element | Field or measure |
|---|---|
| What-if slicer | `Income input` (see section 5) |
| Slicers | property type (single select), quarter |
| KPI | `Sectors within reach of this income`, out of `Sectors priced` |
| Bar | `Income required, lower bound (mean)` by `Sector[name]`, with a constant line at `Income input Value` |
| Table | `Sector[name]`, `Income required, lower bound (mean)`, `Verdict for this income`, `Tracts priced` |
| Card | `Down payment assumption` |
| Card | `Grain warning` |

Page filter: `Sector[geography_type] is apciq_sector`.

**The constant line is the whole page.** A bar chart of required income per
sector, cut by a horizontal line at the income the user typed, answers "where
can I buy" in one glance and shows *by how much* each sector misses — which a
green/red verdict throws away.

**A sector can vanish from this page.** Montréal-Nord publishes no condominium
median in 2026 Q2, so it has no required income and no verdict. `Sectors priced`
is on the KPI row for that reason: a count of sectors within reach means nothing
without the count of sectors that had a price at all.

**`Down payment assumption` is not decoration.** Every figure on this page
assumes the legal *minimum* down payment, because that is the only scenario
`fact_mortgage_scenario` carries. A reader with 50 000 $ saved is not modelled,
and the card is what stops the page from implying otherwise.

### Page 4 — Macro

*The conditions the market moved in — and the distinction the whole model rests on.*

| Element | Field or measure |
|---|---|
| Slicer | `dim_date[calendar_year]` |
| Line | `Rate (mean of period)` by `dim_date[date_key]`, legend `dim_interest_rate_series[rate_kind]` |
| KPI | `Posted minus contract (points)` |
| Combo | `Sales (sectors)` as columns by quarter, `Contract rate (mean)` as line |
| Card | `Rate grain warning` |
| Table | `dim_interest_rate_series[series_label]`, `rate_kind`, `frequency`, `what_it_is` |

The last table is the page. Three series that all look like "the interest rate"
on a chart are three different things, and the posted one — the one most
reports would have used — stood **1.84 points above** the contracted one in
2026 Q2, which moves the required income by about 15 %.

**The combo chart mixes a daily/weekly series with a quarterly one.** That is
section 22 of the brief in one visual. `Rate grain warning` states the number of
observations behind each average, so the chart cannot imply the weekly series
was observed as often as the daily one.

**The three series do not end on the same day, and the last quarter is where it
shows.** Measured on 2026 Q2: the policy rate has 64 observations spanning the
whole quarter, the posted rate 13 ending 24 June, the contracted rate only 9
ending 2 June. The contracted series is published with a lag, so the most recent
quarterly average rests on nine weeks where the others rest on thirteen. Show
`first_obs` and `last_obs` per series in the table, and treat the newest point
of any rate line as provisional rather than as a shorter quarter.

---

## 3. Measures

**Every measure below lives in one table: `_Measures`.** The recipe is the one
Microsoft documents for a measures-only table, and step 3 is the one that is
easy to get wrong:

1. **Home > Enter data**. Leave the grid empty, name the table `_Measures`,
   **Load**. It arrives with one column, `Column1`.
2. Create the measures, setting *Measure tools > Home table = `_Measures`* on
   each one.
3. **Hide `Column1` — do not delete it.** A table needs its column; what makes
   it read as a measures table is that the column is hidden, not that it is
   gone. Right-click `Column1` in the Data pane > *Hide*.
4. Collapse and reopen the Data pane with the arrow at its top. `_Measures`
   then sits at the top of the list, with a calculator icon.

A measure holds no data of its own — it reads whatever its expression names, and
the table it is stored in has no effect on the result. Storing them all in one
place is therefore free, and it is what stops them scattering across four fact
tables, where finding one means remembering which table it happened to be
created in six months ago.

The single exception is `Income input Value`, which Power BI generates inside
the parameter table it creates for you (section 5). Leave it there.
### 3.1 Grouping, and the numbering that was tried and dropped

Measures keep plain names. They are grouped in the Fields pane by **display
folder**, set in *Model view > Properties pane > Display folder*:

| Group | Display folder | Reads from |
|---|---|---|
| Grain guards | `Guards` | filter state, `fact_affordability` |
| Market | `Market` | `fact_market` |
| Affordability | `Affordability` | `fact_affordability` |
| Rates | `Rates` | `fact_interest_rate`, `dim_interest_rate_series` |
| First-time buyer | `First-time buyer` | `fact_affordability`, `Income input` |

**A two-digit code in front of each name was specified on 2026-08-28 and dropped
the same day, after building page 1 with it.** The intent was to control the
order inside each folder, since the Fields pane sorts alphabetically. The cost
was measured rather than guessed: the code is part of the measure name, so it
surfaces in every card title, every table header and every tooltip, and removing
it means one *Rename for this visual* per visual, forever, on a report that has
four pages. Ordering inside a folder of five or six measures is not worth a
rename on every visual that will ever be built.

What the folders give without the code: five groups instead of one flat list of
twenty-six, and a name that reads the same in the model and on the page.

### 3.2 Index

Every measure, its group, what it reads, its format, and where it is used.
**This table is the formatting reference** — there is no second list to keep in
step with it.

| Group | Measure | Home table | Reads from | Format | Page |
|---|---|---|---|---|---|
| Guards | `Grain warning` | `_Measures` | filter state of `Census Tract` | Text | 2, 3 |
| Guards | `Income vintage warning` | `_Measures` | `fact_affordability` | Text | 2 |
| Market | `Sales (island, as published)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1 |
| Market | `Sales (sectors)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1, 4 |
| Market | `Sectors minus island (sales)` | `_Measures` | the two `Sales` measures | Whole number | 1 |
| Market | `Median price` | `_Measures` | `fact_market` | Currency, 0 dec., thousands sep. | 1 |
| Market | `Price context` | `_Measures` | `fact_market` | Text | 1 |
| Market | `Price status` | `_Measures` | `fact_market` | Text | 1 |
| Market | `Days on market` | `_Measures` | `fact_market` | Whole number | 1 |
| Market | `Active listings (island)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1 |
| Affordability | `Tracts evaluated` | `_Measures` | `fact_affordability` | Whole number | 2 |
| Affordability | `Tracts affordable` | `_Measures` | `fact_affordability` | Whole number | 2 |
| Affordability | `Share of tracts affordable` | `_Measures` | the two `Tracts` measures | Percentage, 1 dec. | 2 |
| Affordability | `Income required, lower bound (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2, 3 |
| Affordability | `Price to income (median)` | `_Measures` | `fact_affordability` | Decimal, 1 dec. | 2 |
| Affordability | `Verdict` | `_Measures` | `fact_affordability` | Text | 2 |
| Rates | `Rate (mean of period)` | `_Measures` | `fact_interest_rate` | Decimal, 2 dec. | 4 |
| Rates | `Contract rate (mean)` | `_Measures` | `Rate (mean of period)`, `dim_interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted rate (mean)` | `_Measures` | `Rate (mean of period)`, `dim_interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted minus contract (points)` | `_Measures` | the two rate means | Decimal, 2 dec. | 4 |
| Rates | `Rate grain warning` | `_Measures` | `fact_interest_rate` | Text | 4 |
| First-time buyer | `Sectors priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Sectors within reach of this income` | `_Measures` | `fact_affordability`, `Income input` | Whole number | 3 |
| First-time buyer | `Tracts priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Verdict for this income` | `_Measures` | `fact_affordability`, `Income input` | Text | 3 |
| First-time buyer | `Down payment assumption` | `_Measures` | nothing — a constant string | Text | 3 |
| — | `Income input Value` | `Income input` | the slicer selection | Currency, 0 dec. | 3 |

### 3.3 Build order

Five measures reference another measure, and one group references a table that
section 5 creates. Typing them out of order gets a red squiggle and no
explanation, so build in this order:

| Order | Create | Because |
|---|---|---|
| 1 | `Sales (island, as published)`, `Sales (sectors)` | `Sectors minus island (sales)` subtracts one from the other |
| 2 | the rest of the Market group | independent |
| 3 | `Tracts evaluated`, `Tracts affordable` | `Share of tracts affordable` divides one by the other |
| 4 | the rest of the Affordability group | independent |
| 5 | `Rate (mean of period)` | the two rate means wrap it in `CALCULATE` |
| 6 | `Contract rate (mean)`, `Posted rate (mean)` | `Posted minus contract (points)` subtracts one from the other |
| 7 | `Posted minus contract (points)`, `Rate grain warning` | independent |
| 8 | **the `Income input` parameter (section 5)** | two First-time buyer measures read `'Income input'[Income input Value]` |
| 9 | the First-time buyer group | — |
| 10 | the two Grain guards | independent; they only need `fact_affordability` and the `Census Tract` table |

**Build a group, then build its page, then check the number.** Each group has a
figure already measured against the database, and the report has to reproduce it
or something is wrong upstream of the visual:

| After group | Check | Expected |
|---|---|---|
| Market | `Sectors minus island (sales)` across every quarter | zero everywhere except 2023 Q4, where it is about 0.3 % — reproduced on 2026-08-28 |
| Affordability | `Share of tracts affordable`, condominium, couple, by quarter | 93.2 % in 2019 Q2 falling to 34.9 % in 2026 Q2 |
| Rates | `Posted minus contract (points)`, 2026 Q2 | about 1.84 points |
| First-time buyer | page 3 at 95 000 $, condominium, 2026 Q2 | each of the eighteen sectors is all of its tracts or none |

These are the same figures section 1 and section 2 of this file quote. A visual
that disagrees with them is not a new finding — it is a filter in the wrong
place, and catching it at the end of a group is much cheaper than at the end of
the report.

---
### A. Grain guards

The model has two geography dimensions on purpose. `Sector` reaches the market
facts, `Census Tract` reaches only affordability. Nothing in Power BI stops a
user from putting a tract on an axis beside a market measure — the total would
simply repeat, once per tract, looking like data. These two measures make that
visible.

```dax
Grain warning =
IF (
    ISFILTERED ( 'Census Tract' ),
    "No market figure exists at the census tract. APCIQ publishes for a sector; "
        & "affordability carries that sector price down to each of its tracts as a stated assumption."
)
```

```dax
Income vintage warning =
VAR Gap = SELECTEDVALUE ( fact_affordability[price_year_minus_income_year] )
RETURN
    IF (
        NOT ISBLANK ( Gap ),
        "Income is the 2020 census, unindexed. This price is "
            & Gap & " year(s) later."
    )
```

### B. Market — on `fact_market`

```dax
Sales (island, as published) =
CALCULATE (
    SUM ( fact_market[sales_count] ),
    fact_market[is_island_aggregate] = TRUE ()
)
```

```dax
Sales (sectors) =
CALCULATE (
    SUM ( fact_market[sales_count] ),
    fact_market[is_island_aggregate] = FALSE ()
)
```

Two measures rather than one that decides for itself. The island row and the
eighteen sector rows describe the same sales; adding them counts everything
twice. A measure that guessed which the user meant would be right most of the
time, which is worse than a name that cannot be misread.

```dax
Sectors minus island (sales) =
[Sales (sectors)] - [Sales (island, as published)]
```

This one is the J3.2 reconciliation control, on screen. It should read zero.
On 2023 Q4 it does not, by about 0.3 % — a publisher defect that is declared in
`apciq_known_publisher_defect` and tested in dbt. Showing it beats explaining
it.

```dax
Median price =
VAR PublishedCells = COUNTROWS ( fact_market )
RETURN
    IF ( PublishedCells = 1, SUM ( fact_market[median_price] ) )
```

**This measure returns blank rather than an average, and that is the point.**
There is no weighted median of eighteen sectors and no sector median of forty
tracts — `docs/market.md` section 7 states it. `SUM` over a single published
cell is that cell; over several it would be nonsense, and `AVERAGE` would be
nonsense that looks reasonable. The total row of any table using it is blank,
correctly: a column of medians has no total.

⚠️ **A consequence to build around, not to discover on the page.** `COUNTROWS`
counts the rows the visual leaves standing. One property type and one quarter
still leave **nineteen** rows — the island plus the eighteen sectors — so the
measure returns blank on any visual that does not also filter the geography.
`Median price`, `Price context`, `Price status` and `Days on market` therefore
need a visual-level filter
`Sector[geography_type] is island` on the page 1 KPI row and on the price line,
exactly as the bar and the table carry `is apciq_sector`.
`Sales (island, as published)` and `Active listings (island)` carry
their own island filter and do not need it.

```dax
Price context =
VAR PublishedCells = COUNTROWS ( fact_market )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( PublishedCells ), "No figure published for this selection.",
        PublishedCells = 1, BLANK (),
        "Select one property type, one period and one area. A median cannot be averaged across "
            & PublishedCells & " published cells."
    )
```

```dax
Price status =
SELECTEDVALUE ( fact_market[median_price_value_status], "mixed" )
```

`withheld` means APCIQ printed `**`: too few transactions to publish a median.
It is not a missing value and it is not zero — it is the publisher declining to
answer, and the report says so rather than leaving a gap.

```dax
Days on market =
VAR PublishedCells = COUNTROWS ( fact_market )
RETURN
    IF ( PublishedCells = 1, SUM ( fact_market[days_on_market] ) )
```

```dax
Active listings (island) =
CALCULATE (
    SUM ( fact_market[active_listings] ),
    fact_market[is_island_aggregate] = TRUE ()
)
```

Never sum this across quarters. APCIQ defines active listings as *the average of
the monthly figures for the period* (page 65), so consecutive quarters overlap
in meaning and adding them produces a quantity that does not exist.

### C. Affordability — on `fact_affordability`

```dax
Tracts evaluated =
CALCULATE (
    DISTINCTCOUNT ( fact_affordability[ct_uid] ),
    NOT ISBLANK ( fact_affordability[meets_income_requirement] )
)
```

`meets_income_requirement` is null in the mart whenever the price or the income
is missing — `fact_affordability.sql` sets it that way on purpose. `NOT ISBLANK`
is therefore the exact predicate for "this tract could be evaluated at all", and
it is the denominator of `Share of tracts affordable`.

```dax
Tracts affordable =
CALCULATE (
    DISTINCTCOUNT ( fact_affordability[ct_uid] ),
    fact_affordability[meets_income_requirement] = TRUE ()
)
```

```dax
Share of tracts affordable =
DIVIDE ( [Tracts affordable], [Tracts evaluated] )
```

**Always show `Tracts evaluated` beside it.** The denominator moves:
condominium is evaluable on 95 % of rows, plex on 60 %, because APCIQ withholds
plex medians in five sectors entirely. A percentage whose base is unstated
invites the reader to compare two numbers that do not rest on the same tracts.

```dax
Income required, lower bound (mean) =
AVERAGE ( fact_affordability[income_required_lower_bound] )
```

**A lower bound, and a mean — both words are load-bearing.** The 39 % GDS ratio
also counts property tax, heating and half of condo fees; this project has none
of the three, so a real applicant needs *more*, never less. And the figure is
never additive: averaging tracts is meaningful, summing them is not. Set
*Summarize by = None* on the underlying column.

```dax
Price to income (median) =
MEDIAN ( fact_affordability[price_to_income_ratio] )
```

```dax
Verdict =
VAR Meets = SELECTEDVALUE ( fact_affordability[meets_income_requirement] )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Meets ), "No published price",
        Meets, "Within reach",
        "Out of reach"
    )
```

### D. Rates — on `fact_interest_rate` and `dim_interest_rate_series`

```dax
Rate (mean of period) =
AVERAGE ( fact_interest_rate[rate_percent] )
```

Average, never sum: a rate is intensive, and Tuesday plus Wednesday has no
referent. The series are published in percent already, so set the format string
to `0.00` and put the sign in the label rather than dividing by 100.

```dax
Contract rate (mean) =
CALCULATE (
    [Rate (mean of period)],
    dim_interest_rate_series[rate_kind] = "contracted"
)
```

```dax
Posted rate (mean) =
CALCULATE (
    [Rate (mean of period)],
    dim_interest_rate_series[rate_kind] = "posted"
)
```

The third value of `rate_kind` is `policy`, and no measure filters on it: the
policy rate belongs on the line chart through the legend, not in a KPI that
would invite subtracting it from a mortgage rate.

```dax
Posted minus contract (points) =
[Posted rate (mean)] - [Contract rate (mean)]
```

```dax
Rate grain warning =
VAR Observations = COUNTROWS ( fact_interest_rate )
VAR Series = DISTINCTCOUNT ( fact_interest_rate[series_id] )
RETURN
    IF (
        Series > 1,
        "Averages over " & Observations & " observations across " & Series
            & " series of different frequency: the policy rate publishes every business day, both mortgage rates weekly."
    )
```

### E. First-time buyer — on `fact_affordability` and `Income input`

```dax
Sectors priced =
CALCULATE (
    DISTINCTCOUNT ( fact_affordability[apciq_sector_number] ),
    NOT ISBLANK ( fact_affordability[income_required_lower_bound] )
)
```

```dax
Sectors within reach of this income =
VAR Income = 'Income input'[Income input Value]
RETURN
    COUNTROWS (
        FILTER (
            VALUES ( fact_affordability[apciq_sector_number] ),
            VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
            RETURN NOT ISBLANK ( Required ) && Required <= Income
        )
    )
```

**The `NOT ISBLANK` is not defensive padding — without it the measure is
wrong.** A sector APCIQ did not price has no required income, so `AVERAGE`
returns `BLANK()`; DAX coerces a blank to `0` in a numeric comparison, and
`0 <= Income` is true for every income the slicer can produce. Montréal-Nord,
which publishes no condominium median in 2026 Q2, would have been counted as
*within reach* — the one verdict the data cannot support. The test on the
sector's own price is what keeps `41` consistent with `Sectors priced`.

The `FILTER` runs over the eighteen sector numbers, not over 141 462 fact rows.
Iterating the fact table would give the same answer at a cost no page should
pay, and would count a sector once per tract if the measure ever landed in a
visual without a sector on the axis.

```dax
Tracts priced =
CALCULATE (
    DISTINCTCOUNT ( fact_affordability[ct_uid] ),
    NOT ISBLANK ( fact_affordability[median_price] )
)
```

```dax
Verdict for this income =
VAR Income = 'Income input'[Income input Value]
VAR Required = AVERAGE ( fact_affordability[income_required_lower_bound] )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Required ), "No published price",
        Income >= Required * 1.10, "Within reach",
        Income >= Required, "Borderline",
        "Out of reach"
    )
```

**The 10 % margin is a display convention of this project, not a lending rule.**
It exists because `income_required_lower_bound` is a floor: a household exactly
at the floor has none of the property tax, heating or condo fees the real ratio
would charge them. Calling that band "Borderline" rather than "Within reach" is
an honest reading of a number the model states is incomplete. It is an
assumption, and `methodology.md` must name it as one.

```dax
Down payment assumption =
"Assumes the legal minimum down payment for this price, insured. "
    & "A larger down payment is not modelled."
```

---

## 4. Colour

Formats are in the index at section 3.2, one line per measure, so that a format
never has to be kept in step in two places.

Read `dataviz` before choosing colours. Two rules matter more than the palette
here: **do not use a red-green scale for the affordability verdict** — it reads
as good/bad on a figure that is a floor, not a judgement — and **keep one colour
per `rate_kind`** across every page, so posted and contracted are never the same
colour in two charts.

---

## 5. The what-if parameter

**Modeling > New parameter > Numeric range.**

| Field | Value |
|---|---|
| Name | `Income input` |
| Data type | Whole number |
| Minimum | 30000 |
| Maximum | 300000 |
| Increment | 2500 |
| Default | 95000 |

95 000 $ is the figure section 31 of the brief uses in its worked example, which
makes the page answer the question the project set out to ask.

**The parameter is not called `Household income`, and that is deliberate.**
`fact_affordability` already carries a column named `household_income`: the 2020
census median of the tract, an observation. The parameter is a number the reader
types, a hypothesis. Two fields whose names differ only by capitalisation would
be picked interchangeably out of the Fields pane, and keeping observed apart
from assumed is what this whole model is for. `Income input` cannot be mistaken
for a census figure.

Power BI creates a calculated table `Income input` and, inside it, a measure
called `Income input Value`. `Sectors within reach of this income` and
`Verdict for this income` reference it as
`'Income input'[Income input Value]`; the table qualifier is what shows the
value comes from the slicer rather than from the model.

⚠️ **That table does not exist until this section has been done.** Create the
parameter *before* typing those two measures — DAX refuses both until it can
resolve `'Income input'`. If you name the parameter something else, both
measures must be edited to match.

---

## 6. What this report deliberately does not do

**No map — and the reason written here on 2026-08-27 was wrong, so the question
is reopened rather than settled.** It claimed `Shape Map` needed a TopoJSON
conversion and that the alternatives were a Bing round-trip or a custom visual.
Checked against learn.microsoft.com on 2026-08-28, page dated 2026-06-10:
`Shape Map` is not a preview feature and not a custom visual, it accepts
**GeoJSON** as well as TopoJSON, and it colours a shape file you supply rather
than geocoding anything. Its stated ceiling is 1 500 data points; eighteen
sectors and 541 tracts are far below it.

What a map costs here is not the visual. It is that the eighteen APCIQ sectors
carry `geometry = NULL` — `dim_geography.sql`, the `apciq_sectors` CTE, and
deliberately so since J3.1. J3.4 settled how to build it: **the union of each
sector's census tract polygons**, one source file, a tessellation by
construction, and the `st_union` pattern already appears twice in that same
model. Every geometry is stored in EPSG:4326, so `ST_AsGeoJSON` is the entire
export.

Two different maps are available, and they do not say the same thing. Eighteen
sectors shaded by median price is the one a reader expects. **541 tracts shaded
by the affordability verdict is the one that shows something no other report
has**: the J4.1 finding that in seventeen of the eighteen sectors the verdict
changes from tract to tract at an identical price. Eighteen flat areas cannot
show that.

Not built in this milestone — not because it is expensive, but because it is
not one of the eleven criteria of section 44. Section 30 of the brief does ask
for one. **Whether it earns its own session is a scope decision, not a
technical one.**

**No `housing_burden_ratio`.** It needs sixteen municipal tax rates that are not
identified and condo fees that only exist in listings. Out of scope for J4,
decided in advance.

**No five-variable FTB Score.** Section 25 of the brief describes one; it is
reduced here to the required income, which dominates it anyway. Building a
composite index on top of a figure already stated to be a lower bound would add
precision that is not there.

**No forecast, and no causal wording.** The rate line and the sales columns on
page 4 sit on the same axis because they moved in the same years. Every label
on that page says *association*, never *cause*.

---

## 7. Why this file exists

