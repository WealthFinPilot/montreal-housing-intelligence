# Report design

Four pages, and every measure they need. The connection, the tables and the
relationships are in [README.md](README.md); build the model there first.

---

## 1. What this report has to say

One finding carries the report, and it was measured on 2026-08-27 against the
finished tables:

> For a two-person couple looking at a condominium, the share of island census
> tracts whose median household income reaches the required income falls from
> **93.2 % in 2019 Q2 to 35.0 % in 2026 Q2**.

⚠️ **That closing figure read 34.9 % until 2026-08-29, and the correction is
worth keeping rather than silently applying.** The two ends of the sentence had
been measured two different ways: 93.2 % counts distinct census tracts
(494 / 530), 34.9 % counted fact rows (179 / 513). They differ because
`4620511.02` is genuinely shared between sectors 2 and 5 and therefore holds two
rows — the one shared tract of J3.4. `Tracts evaluated` and `Tracts affordable`
both use `DISTINCTCOUNT`, so the report says **179 / 512 = 35.0 %**, and a page
showing 34.9 % would mean a measure counting rows instead of tracts.

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
| Table | `Sector[name]`, `Census Tract[name]`, `Household income (2020 census)`, `Income required, lower bound (mean)`, `Income shortfall (mean)`, `Price to income (median)`, `Verdict` — sorted by shortfall ascending |
| Card | `Income vintage warning` |
| Card | `Grain warning` |

`Grain warning` prints only when a census tract is filtering, which is exactly
when a market measure on the same page would be repeating a sector total once
per tract. Put it in the title of any visual that mixes the two grains.

**This page carries no geography filter, and page 1 carried one on every
visual.** The difference is not an oversight. `fact_affordability` has no island
row — measured on 2026-08-29, its 141 462 rows key to eighteen sectors and
nothing else — so the two zones that made page 1 exclude itself do not exist
here. Every visual reads the same 542 tract rows, and the sector bar simply
groups them.

**The one thing that follows from it: interactions can stay on their defaults.**
Clicking a sector in the bar filters the tract table to that sector's tracts,
which is the gesture a reader expects. The only interaction to set by hand is
the line chart, which should drive nothing — its axis is the quarter the slicer
already governs, exactly as on page 1.

**A sector can be absent from the bar, and an absent bar is not a zero.** On
2026 Q2, condominium, sector 17 (Montréal-Nord) has no published median, so all
eighteen of its tracts are unevaluable and the sector has no bar at all. Put
`Tracts evaluated` in the bar's tooltip; a share of nothing and a share of zero
are different statements and the chart cannot tell them apart on its own.

**`Income required, lower bound (mean)` does not move when the profile slicer
moves, and that is correct.** The required income depends on the price, not on
who is buying: measured on 2026 Q2 condominium, it holds the same value across
all three profiles to the dollar. (The amount is not written here -- it derives
from an APCIQ median. `scripts/report_oracle.py` prints it.) Only the comparison to what households earn is profile-dependent.
Say so in the card's subtitle, otherwise the flat number reads as a broken
slicer.

**Its base is not the KPI beside it either.** The mean is taken over the 524
rows that carry a required income, while `Tracts evaluated` counts the 512
tracts that also carry an income to compare it with. Two honest denominators on
one row of cards; the subtitle is where that gets stated, not hidden.

#### The figures this page has to reproduce

Measured against the database on 2026-08-29. Property type **Condominium**,
profile **Couple, two persons**, quarter **2026 Q2**:

| Measure | Expected |
|---|---|
| `Tracts evaluated` | 512 |
| `Tracts affordable` | 179 |
| `Share of tracts affordable` | 35.0 % |
| `Income required, lower bound (mean)` | the figure `report_oracle.py` prints -- not reproduced here |
| `Price to income (median)` | the figure `report_oracle.py` prints -- not reproduced here |
| Sectors with at least one evaluable tract | 17 of 18 |

And on the line, across every quarter at the same property type and profile:
93.2 % at 2019 Q2, **70.3 % at 2022 Q1 falling to 54.7 % at 2022 Q2** — the
break the page exists to show — a floor of 29.7 % at 2023 Q4, then sideways to
35.0 % at 2026 Q2.

**Switch the profile to One person and the page reads 1 tract out of 512.** That
is the data, not a filter fault: a single-person household at the 2020 median
income clears the required income in exactly one census tract of the island.
Plex and single-family return 0 and 2 for the couple. A page that only ever
gets checked on its most favourable combination has not been checked.

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

**This is structural, not an observation about one quarter.** Measured on
2026-08-30 across the whole table: of the 4 698 combinations of sector ×
quarter × property type × household profile, **not one holds two different
required incomes**. The verdict is therefore constant inside a sector by
construction, whatever the slicers are set to. A table of 541 rows here would
show 541 copies of eighteen answers and imply a precision that does not exist.
So the page is built on the sector, and the tract count appears only as
coverage.

| Element | Field or measure |
|---|---|
| What-if slicer | `Income input` (see section 5) |
| Slicers | property type (single select), quarter (single select) |
| KPI | `Sectors within reach of this income`, `Sectors borderline`, out of `Sectors priced` |
| Bar | `Income required, lower bound (mean)` by `Sector[name]`, sorted ascending, bars coloured by `Sector bar colour`, tooltips `Tracts priced` and `Verdict for this income`, with an X-axis constant line at `Income input Value` |
| Table | `Sector[name]`, `Income required, lower bound (mean)`, `Verdict for this income`, `Tracts priced` — sorted the same way as the bar |
| Card | `Down payment assumption` |
| Card | `Slice warning` |
| Card | `Grain warning` |

**No household-profile slicer, unlike page 2 — and that is a measured omission,
not a forgotten one.** The required income depends on the price, not on who is
buying: across the 1 566 sector × quarter × property-type combinations, it never
takes two values across the three profiles. Adding the slicer would put a
control on the page that changes nothing, which reads as a broken filter. It
also gives the build a second, independent check: the report shows the same
counts with no profile filter at all that `report_oracle.py` computes on the
couple profile alone.

**The bar chart is horizontal, and the bars are sorted by required income
ascending.** Eighteen sector names do not fit under vertical columns, and the
question the page asks — where can I buy — is answered by reading from the top.
The constant line then cuts the list in two: everything left of it is within
reach. The table repeats that order, so the two visuals never have to be
mentally re-matched.

Page filter: `Sector[geography_type] is apciq_sector`.

**Both slicers are single select, and that is a correctness setting rather than
a convenience.** Every figure on this page is an average of the required income,
and an average answers even when it is averaging three property types or
twenty-nine quarters together — silently, and with a plausible number. See
`Slice warning` in section A for what was measured. `Sector[geography_type]`
only affects the axis: `fact_affordability` keys to the eighteen APCIQ sectors
and to nothing else — 141 462 rows, 18 geography keys, zero island rows,
measured 2026-08-30 — so the page filter cannot change a figure, only keep the
island row of `Sector` off the chart.

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

**One interaction is switched off: the bar chart must not filter the three KPI
cards.** *Format > Edit interactions*, bar selected, **None** on each card; the
table stays on *Filter*. Everything else keeps its default, because unlike page
1 every visual here reads one table at one grain and no click can produce an
empty intersection. The exception matters because clicking a single sector turns
"6 of 17" into "0 of 1", which reads as *no sector is within reach* when the
reader has merely selected one that is not. The KPI row is also where the four
counts are checked against eighteen — it has to stay the summary of the page
rather than follow the click.

**The KPI row has to add up to eighteen, and that is the check to run first.**
`Sectors within reach of this income` + `Sectors borderline` + the rows the
table reads *Out of reach* + the rows it reads *No published price* = 18. Four
counts, one page, one definition of each. It is the cheapest way to catch the
fault this page was specified with: a card and a table applying two different
thresholds to the same comparison.

#### The figures this page has to reproduce

Measured against the database on 2026-08-30. Property type **Condominium**,
profile **Couple, two persons**, quarter **2026 Q2**, income **95 000 $**:

| Measure | Expected |
|---|---|
| `Sectors priced` | 17 of 18 |
| `Sectors within reach of this income` | 6 |
| `Sectors borderline` | 1 |
| Sectors reading *Out of reach* in the table | 10 |
| Sectors reading *No published price* | 1 (sector 17, Montréal-Nord) |
| `Tracts priced`, summed over the table | 524 rows for 523 distinct tracts |
| `Income required, lower bound (mean)` | the figure `report_oracle.py` prints — not reproduced here |

Move the slicer and the page has to keep answering. At **30 000 $** and at
**60 000 $** every card reads a firm **0**, never a blank; at **150 000 $**,
16 of the 17 priced sectors are within reach, and at the slicer's ceiling of
**300 000 $**, all 17. A page that only ever gets checked at its default income
has not been checked.

**Built on 2026-08-30, and every figure above was reproduced** — the KPI row,
the four verdict counts adding to eighteen, Montréal-Nord with no bar and
`Tracts priced` at zero, and the cards holding at zero at the low end of the
slicer. Unlike page 2, nothing had to be corrected during the build: the three
faults this page was specified with — a card and a table on two thresholds, two
measures returning blank instead of zero, and no guard on the property type or
the quarter — were found by checking the measures against the database first,
which is the practice page 2 paid for.

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
| Guards | `Slice warning` | `_Measures` | `dim_property_type`, `fact_affordability` | Text | 2, 3 |
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
| Affordability | `Household income (2020 census)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Income shortfall (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Price to income (median)` | `_Measures` | `fact_affordability` | Custom `0.0"×"` — **never a currency** | 2 |
| Affordability | `Verdict` | `_Measures` | `fact_affordability` | Text | 2 |
| Rates | `Rate (mean of period)` | `_Measures` | `fact_interest_rate` | Decimal, 2 dec. | 4 |
| Rates | `Contract rate (mean)` | `_Measures` | `Rate (mean of period)`, `dim_interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted rate (mean)` | `_Measures` | `Rate (mean of period)`, `dim_interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted minus contract (points)` | `_Measures` | the two rate means | Decimal, 2 dec. | 4 |
| Rates | `Rate grain warning` | `_Measures` | `fact_interest_rate` | Text | 4 |
| First-time buyer | `Sectors priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Sectors within reach of this income` | `_Measures` | `fact_affordability`, `Income input` | Whole number | 3 |
| First-time buyer | `Sectors borderline` | `_Measures` | `fact_affordability`, `Income input` | Whole number | 3 |
| First-time buyer | `Tracts priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Verdict for this income` | `_Measures` | `fact_affordability`, `Income input` | Text | 3 |
| First-time buyer | `Sector bar colour` | `_Measures` | `Verdict for this income` | Text | 3 |
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
| 8 | **the `Income input` parameter (section 5)** | three First-time buyer measures read `'Income input'[Income input Value]` |
| 9 | the First-time buyer group, `Verdict for this income` before `Sector bar colour` | the colour measure reads the verdict rather than repeating its comparison |
| 10 | the three Grain guards | independent; they only need `fact_affordability`, `dim_property_type` and the `Census Tract` table |

**Build a group, then build its page, then check the number.** Each group has a
figure already measured against the database, and the report has to reproduce it
or something is wrong upstream of the visual:

| After group | Check | Expected |
|---|---|---|
| Market | `Sectors minus island (sales)` across every quarter | zero everywhere except 2023 Q4, where it is about 0.3 % — reproduced on 2026-08-28 |
| Affordability | `Share of tracts affordable`, condominium, couple, by quarter | 93.2 % in 2019 Q2 falling to 35.0 % in 2026 Q2, with the break at 2022 Q2 |
| Rates | `Posted minus contract (points)`, 2026 Q2 | about 1.84 points |
| First-time buyer | page 3 at 95 000 $, condominium, couple, 2026 Q2 | 6 within reach, 1 borderline, 10 out of reach, 1 with no published price — and `Sectors priced` reads 17 |

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
VAR IncomeYear = SELECTEDVALUE ( fact_affordability[income_year] )
VAR Preamble = "Income is the " & IncomeYear & " census, unindexed. This price is "
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Gap ), BLANK (),
        Gap = 0, Preamble & "from the same year.",
        Gap < 0, Preamble & -Gap & " year(s) earlier.",
        Preamble & Gap & " year(s) later."
    )
```

**The first version said "later" for every quarter, and for 2019 that was
wrong.** `price_year_minus_income_year` runs from **-1 to 6** — measured on
2026-08-29 across the whole table, on a single `income_year`, 2020. The census
income is *newer* than the price for the four quarters of 2019, and the card
would have printed "this price is -1 year(s) later". Reading the year off the
column rather than typing `2020` into the string also means the sentence cannot
outlive the next census.

⚠️ **The card is blank without a quarter selected.** `SELECTEDVALUE` returns the
value only when one distinct value survives; twenty-nine quarters carry eight
different gaps. Same mechanism as the page 1 cards — the quarter slicer is what
makes the card speak.

```dax
Slice warning =
VAR Types = COUNTROWS ( VALUES ( dim_property_type[name_en] ) )
VAR Quarters = COUNTROWS ( VALUES ( fact_affordability[edition_label] ) )
RETURN
    IF (
        Types > 1 || Quarters > 1,
        "Averaged over " & Types & " property type(s) and " & Quarters & " quarter(s). "
            & "Every figure here assumes one price: select a single property type and a single quarter."
    )
```

**The third guard, added on 2026-08-30, and the one that guards a page that
looks right.** A required income averaged over several property types or several
quarters raises nothing at all — no blank, no error, no empty visual. It just
answers a different question. Measured on 2026 Q2, condominium, couple:
releasing the property-type filter raises the mean required income by **49 %**
and drops the sectors within reach from **7 to 2**; releasing the quarter filter
instead takes them from **7 to 14**. Both are plausible-looking pages.

It is worse than the page 1 mechanism, not milder. There, a median over more
than one row returns blank and the card says `--`, which is a visible refusal to
answer. Here the average answers, and the answer is a mixture. `Sectors priced`
even climbs from 17 to 18, because Montréal-Nord has a price in *some* type or
*some* quarter — so the KPI's own denominator moves to cover the mixture up.

It reads the quarter off `fact_affordability[edition_label]` rather than off
`dim_date`, so it reports what actually reached the fact table after the filter
propagated, not what the slicer looks like it is doing.

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
VAR Affordable =
    CALCULATE (
        DISTINCTCOUNT ( fact_affordability[ct_uid] ),
        fact_affordability[meets_income_requirement] = TRUE ()
    )
RETURN
    IF ( NOT ISBLANK ( [Tracts evaluated] ), Affordable + 0 )
```

```dax
Share of tracts affordable =
VAR Evaluated = [Tracts evaluated]
RETURN
    IF ( NOT ISBLANK ( Evaluated ), DIVIDE ( [Tracts affordable], Evaluated ) )
```

**Both were one line until 2026-08-29, and both made a measured zero
disappear.** `DISTINCTCOUNT` returns `BLANK()` over an empty set, and DAX
divides a blank into a blank rather than into zero — so a sector where every
tract was evaluated and none reached the threshold dropped out of the bar chart
entirely, indistinguishable from Montréal-Nord, which has no published price at
all. The guard turns on `Tracts evaluated`, which is the only measure that knows
whether the question could be asked: **evaluable and none affordable is a zero,
not evaluable is nothing.** Same distinction the raw layer keeps between APCIQ's
`-`, `**` and an empty cell.

Two selections show the cost, both measured on 2026-08-29. Condominium, one
person, 2025 Q4: **one bar instead of seventeen**, sixteen of which belong at
zero. Plex, couple, 2026 Q2: **an empty chart instead of nine bars at zero**,
which reads as "nothing was measured" when nine sectors were.

**It only shows on an unfavourable selection.** On the default page — condominium,
couple — every priced sector has at least one affordable tract, so the fault is
invisible. It was found by running the check on One person, which is the whole
reason that step is in the recipe.

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

⚠️ **Format it `0.0"×"`, so it always carries the multiplier sign and never appears bare.** The column is
`round(median_price / household_income, 3)` — a multiple of **annual** income,
carrying no unit at all. A bare number beside a currency card was read as a
dollar amount on 2026-08-29, and the reading is a reasonable one: every other
number on the page is money. The multiplier sign is what makes the misreading
impossible, and it costs one custom format string.

Name the table column *Price to income (× annual income)* while you are there.
The ratio is the one figure on this page a reader can compare to something
outside the report — three to four times income was the conventional threshold —
and it says more than the verdict does, because it does not depend on any
lending rule.

```dax
Household income (2020 census) =
VAR Tracts = DISTINCTCOUNT ( fact_affordability[ct_uid] )
RETURN
    IF ( Tracts = 1, MAX ( fact_affordability[household_income] ) )
```

```dax
Income shortfall (mean) =
AVERAGE ( fact_affordability[income_shortfall] )
```

**The table showed a verdict and one side of the comparison, and that was the
gap.** `Verdict` printed "Out of reach", `Income required` said against what,
and the income that lost the comparison appeared nowhere — so nothing on the
page could be checked, and the distance was invisible. These two put the
observation back beside the derivation: `household_income` is a Statistics
Canada figure, while the required income rests on three stacked assumptions
(minimum down payment, qualifying rate at contract + 2 points, 39 % GDS).

**The `IF` is verrou n° 1 of J4, enforced in DAX.** At one census tract there is
one income and the measure returns it; above that, aggregating forty tract
medians into a sector income is wrong whether or not it is weighted — the reason
the whole model sits at the tract. So it goes blank above a single tract, like
`Median price` on page 1, and the table's total row is correctly empty.

**The year is in the name deliberately.** With `Income input` (a what-if
hypothesis) and `income_required_lower_bound` (a derivation) already in the
model, a measure called plain "Household income" would be the third revenue-ish
field in a model whose entire purpose is to keep observed, derived and assumed
apart.

⚠️ **These two columns do not share a licence, and that matters at J4.5.**
`Household income (2020 census)` is Statistics Canada, redistributable
explicitly. Everything else in this table derives from an APCIQ median. If the
public route ends up being the zero-APCIQ fallback, the observed column stays
and the derived ones go — a page carrying both degrades into something that
still says something.

```dax
Verdict =
VAR Meets = SELECTEDVALUE ( fact_affordability[meets_income_requirement] )
VAR HasPrice = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[median_price] ) )
VAR HasIncome = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[household_income] ) )
RETURN
    SWITCH (
        TRUE (),
        NOT ISBLANK ( Meets ) && Meets, "Within reach",
        NOT ISBLANK ( Meets ), "Out of reach",
        NOT HasPrice, "No published price",
        NOT HasIncome, "No published income",
        "Not evaluated"
    )
```

**Two different absences, and the first version called both of them a missing
price.** Measured on 2026-08-29, 2026 Q2, condominium, couple: of 542 rows,
513 are evaluated, **18 have no APCIQ price** — every tract of sector 17,
Montréal-Nord — and **11 have a price but no 2020 census income**. Those eleven
are the near-empty tracts of J3.3, suppressed at source. Printing "No published
price" against a tract APCIQ *did* price is the kind of confusion this model
exists to prevent, and the reader has no way to catch it.

`Not evaluated` is the branch that should never appear. It can only fire on a
row where the price and the income both exist yet the verdict is null, or on the
shared tract `4620511.02` if its two sectors ever disagree on the price — in
which case `SELECTEDVALUE` returns blank for both. Leave it visible: a branch
that never fires is a control, and one that starts firing is news.

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
VAR Priced =
    CALCULATE (
        DISTINCTCOUNT ( fact_affordability[apciq_sector_number] ),
        NOT ISBLANK ( fact_affordability[median_price] )
    )
RETURN IF ( ISBLANK ( Priced ), 0, Priced )
```

```dax
Tracts priced =
VAR Priced =
    CALCULATE (
        DISTINCTCOUNT ( fact_affordability[ct_uid] ),
        NOT ISBLANK ( fact_affordability[median_price] )
    )
RETURN IF ( ISBLANK ( Priced ), 0, Priced )
```

**Both count a published price, not a derived one**, and that is deliberate:
`median_price` is what APCIQ printed, `income_required_lower_bound` is what this
project computed from it. A denominator built on the project's own arithmetic
would move if the mortgage seeds moved.

The shortcut it allows was measured on 2026-08-30 rather than assumed: across
all 141 462 rows and all three property types, **there is not one row where a
median price is present and a required income is missing, nor the reverse**. So
the two absences coincide today, and the KPI reads "6 of 17" without a caveat.
`report_oracle.py` recomputes that agreement on every run — the day a price sits
outside the insurable range and carries no required income, the sector belongs
in the denominator and not in the numerator, and the oracle is what will say so.

```dax
Sectors within reach of this income =
VAR Income = 'Income input'[Income input Value]
VAR Reached =
    COUNTROWS (
        FILTER (
            VALUES ( fact_affordability[apciq_sector_number] ),
            VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
            RETURN NOT ISBLANK ( Required ) && Required * 1.10 <= Income
        )
    )
RETURN IF ( ISBLANK ( Reached ), 0, Reached )
```

```dax
Sectors borderline =
VAR Income = 'Income input'[Income input Value]
VAR Band =
    COUNTROWS (
        FILTER (
            VALUES ( fact_affordability[apciq_sector_number] ),
            VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
            RETURN NOT ISBLANK ( Required ) && Required <= Income && Required * 1.10 > Income
        )
    )
RETURN IF ( ISBLANK ( Band ), 0, Band )
```

**The `NOT ISBLANK` is not defensive padding — without it the measure is
wrong.** A sector APCIQ did not price has no required income, so `AVERAGE`
returns `BLANK()`; DAX coerces a blank to `0` in a numeric comparison, and
`0 <= Income` is true for every income the slicer can produce. Montréal-Nord,
which publishes no condominium median in 2026 Q2, would have been counted as
*within reach* — the one verdict the data cannot support. The test on the
sector's own price is what keeps the KPI consistent with `Sectors priced`.

**The `× 1.10` was added on 2026-08-30, because the first version made the card
disagree with the table underneath it.** The card tested `Required <= Income`
and the verdict column tested `Income >= Required * 1.10`: on 2026 Q2,
condominium, at 95 000 $, the card said seven and the table showed six rows
reading *Within reach*. That is not a rounding difference and not particular to
one quarter — measured across the 87 quarter × property-type slices, **the two
definitions disagree in 44 of them, by as much as five sectors**. One page
cannot carry two meanings of "within reach", so the band that the verdict
already applied is now the only definition, and `Sectors borderline` puts the
sectors between the two thresholds on the KPI row rather than leaving them to be
inferred from a subtraction. The four counts add up to the eighteen sectors.

**The `IF ( ISBLANK ( … ), 0, … )` is the page-2 fault, caught before drawing.**
`COUNTROWS` over an empty table and `DISTINCTCOUNT` over an empty set both
return `BLANK()`, so a measured zero and a missing figure arrive at the visual
as the same thing. It is reachable by the first gesture a reader makes: measured
on 2026 Q2 condominium, **no sector is within reach at 30 000 $ or at 60 000 $**,
which is most of the left half of the slicer. Without the guard the card goes
empty there and reads as broken, when the answer is a firm zero.

The `FILTER` runs over the eighteen sector numbers, not over 141 462 fact rows.
Iterating the fact table would give the same answer at a cost no page should
pay, and would count a sector once per tract if the measure ever landed in a
visual without a sector on the axis.

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

It is also the one arbitrary constant on this page, so it is written in exactly
two measures — this one and `Sectors within reach of this income` — and nowhere
else. Changing the band means editing both, and the KPI row is what makes a
half-done change visible immediately: the four counts stop adding up to
eighteen.

```dax
Sector bar colour =
SWITCH (
    [Verdict for this income],
    "Within reach", "#17527A",
    "Borderline",   "#5B9BC4",
    "Out of reach", "#C7CCD1",
    "#E8EAEC"
)
```

**It reads the verdict rather than repeating its comparison, and that is the
whole point of the measure.** Conditional formatting on this bar was first asked
for as *blue at or below the income, grey above* — a threshold of 100 %, which
would have coloured seven bars blue beside a card reading six. The band of 10 %
would then have been written in three measures instead of two, with nothing
keeping them in step. Reading `[Verdict for this income]` makes the colour
incapable of disagreeing with the word printed in the table beside it.

Bound through *Format visual > Bars > Color > `fx` > Format style = Field
value*. Conditional formatting produces **no legend**, so `Verdict for this
income` also goes in the visual's tooltips: the table and the tooltip are the
only two places the three shades are named.

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

The page-3 verdict scale, chosen on 2026-08-30 and carried by `Sector bar
colour`: `#17527A` within reach, `#5B9BC4` borderline, `#C7CCD1` out of reach,
`#E8EAEC` no published price. One hue plus a neutral, and **decreasing
luminosity in verdict order**, so the ranking survives greyscale printing and
colour-blind vision without relying on hue at all. Blue-to-grey rather than
green-to-red because the comparison is a floor against a typed income, not a
pass and a fail.

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
parameter *before* typing those three measures — DAX refuses all of them until
it can resolve `'Income input'`. If you name the parameter something else, all
three must be edited to match.

**The `Default` field of the dialog becomes the second argument of the generated
measure.** Verified in Desktop on 2026-08-30: with `Default` set to 95000,
Power BI writes

```dax
Income input Value = SELECTEDVALUE ( 'Income input'[Income input], 95000 )
```

That second argument is what the whole page falls back to whenever the slicer is
not on a single value — which happens the moment it is switched from *Single
value* to *Between*, a two-click gesture in the visual's header. Left at `0`,
every sector would read *Out of reach* and nothing on the page would say why:
the model would have answered exactly the question it was asked, about a
household earning nothing. Filled in, a mis-set slicer degrades to the
documented scenario instead of to a false one.

⚠️ **Read the generated formula rather than trusting the dialog.**
learn.microsoft.com's page on what-if parameters, updated 2026-05-21, lists
Name, Data type, Minimum, Maximum and Increment and shows no **Default** field
at all — the field exists in Desktop, and the page is behind. Which is the
reason to check the formula: the article that would tell you what was generated
is the one that did not know the field was there.

**A constant line's `Value` can be bound to a measure through its `fx` button,
and page 3 does exactly that.** Verified in Desktop on 2026-08-30: Analytics
pane > X-axis constant line > `fx` beside **Value** > *Field value* >
`Income input Value`. The line then follows the slicer.

learn.microsoft.com's Analytics-pane page, updated 2026-07-23, does not say so
either way — it documents which visuals accept a constant line, and states that
Min / Max / Average / Median lines take their value from *a measure already in
the visual*, which would have been the fallback here: drop `Income input Value`
into the field well and put an **Average** line on it, at the cost of a second
bar per sector. That fallback was not needed.

⚠️ **Never leave a typed constant in that field.** A line frozen at 95 000 $
while the slicer says 140 000 $ is the worst outcome available on this page:
every bar is right, the line is neat, and the verdict a reader takes from it is
false. Dragging the slicer and watching the line move is the check, and it is in
the acceptance list for page 3.

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

