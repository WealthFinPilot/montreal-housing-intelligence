# Report design

> **Table names in this file are the MODEL's names, not the database's.** The
> `dim_` prefix is dropped on import, so `marts.dim_date` is `'date'` here,
> `marts.dim_property_type` is `property_type`, and `marts.dim_geography` is
> split into `Sector` and `Census_Tract`. Fact tables are unchanged. Where a
> sentence genuinely means the dbt table it says so — `dim_geography` appears
> twice below, both times about the database and not about the model.
>
> `'date'` is quoted everywhere because `DATE` is a DAX function and a bare
> table name of that spelling does not parse. See `powerbi/README.md`.



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
| Slicer | `property_type[name_en]`, single select, **required** |
| Slicer | `'date'[quarter_label]` |
| KPI row | `Sales (island, as published)`, `Median price`, `Days on market`, `Active listings (island)` — visual filter `Sector[geography_type] is island` |
| Line | `Median price` by `'date'[quarter_label]` — same visual filter |
| **Map** | `Shape map`, `Sector[geography_code]` on **Location**, `Median price` on **Color saturation**, `Legend` **empty**, a drawn gradient shape as legend — visual filter `Sector[geography_type] is apciq_sector` |
| Column chart | `Price relative to the island` by `Sector[name]`, sorted descending, **Y axis fixed 0 to 3.5×**, Y constant line at **1.0×**, columns coloured by `Sector price colour`, tooltip `Sector rank (price)` — same visual filter |
| Table | `Sector[name]`, **`Sector rank (price)`**, `Median price`, `Price status`, `Sales (sectors)` — same filter |

**The bar has changed measure twice, and each change was made for a reason
worth keeping.** It started as `Sales (sectors)` by sector; that chart is
dominated by how large a sector is — sector 1 spans seven municipalities — so it
mostly restates the housing stock, and a tall bar reads as a hot market when it
means a big one. It became `Median price`, which is not confounded that way and
is one figure APCIQ printed per bar. It is now **`Price relative to the
island`**, and the reason is the map beside it.

**Why the bar gives up dollars: because the map keeps them, and the two must not
say the same thing twice.**

The map is coloured by `Median price` on an **automatic** scale, which is a
deliberate trade with a known cost: Power BI recomputes the colour bounds from
whatever the slicers leave standing, so every property type uses the whole
palette — and **two quarters become visually incomparable**, because a general
rise in prices repaints itself away. A fixed common scale was measured and is
worse: on 2026 Q2 a scale spanning all three types leaves condominium occupying
**26 %** of the palette and plex **26.5 %**, against 89 % for single-family. The
condominium map would be near-monochrome, which is the one thing a choropleth
must not be.

**The relative bar is what pays for that.** Its axis is a multiple of the
island's own median, so it does not move when prices do: 2019 and 2026 sit on
the same scale, and the reader compares *structure* on the bar and *level* on the
map.

⚠️ **And the bar loses nothing by dropping dollars, which was verified rather
than assumed.** Dividing every sector by the island's median divides them all by
the same constant, so the ranking cannot change — measured across **1 136
sector-rows over 87 type × quarter slices: zero changed rank**. The bar ranks
exactly as it did, and now carries a second reading for free: above 1.0× is
dearer than the island, below is cheaper, and the constant line makes that
threshold a place on the chart rather than a mental calculation.

**The value axis is fixed from 0 to 3.5×, never autoscaled** — and it is the
**Y** axis, because this chart is vertical columns. (Page 3 is the horizontal
one, for a reason stated there: eighteen sector names do not fit under vertical
columns, and that page has no map competing for width.) An autoscaled axis would
restore exactly the incomparability the columns exist to remove. 3.5 is above the
maximum ever observed — the whole archive runs from **0.51× to 3.29×**, 99th
percentile 2.91× — so nothing is clipped and no column is ever truncated. The
axis starts at 0 because a column chart that starts elsewhere exaggerates every
difference on it.

The reference line is therefore a **Y constant line at 1.0** (Analytics pane),
not an X one: everything above it is dearer than the island, everything below is
cheaper.

**The columns are also coloured on that threshold**, added on
2026-08-31 — dark above the island, lighter below:

```dax
Sector price colour =
VAR X = ROUND ( [Price relative to the island], 2 )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( X ), "#E8EAEC",
        X >= 1, "#17527A",
        "#5B9BC4"
    )
```

**It reads `[Price relative to the island]` rather than comparing the price to
the island a second time**, for the same reason `Sector bar colour` reads
`[Verdict for this income]`: written as its own comparison, the threshold would
exist in three places — the constant line, the column height and the colour —
with nothing keeping them in step. Reading the measure makes the colour
incapable of disagreeing with the line drawn across it.

The `ISBLANK` branch is unreachable on screen, since a sector with no price has
no column at all. It is there because DAX compares a blank as a zero, which
would file every unpriced sector *below the island*, and **that fault has
already appeared three times in this report**.

⚠️ **`ROUND ( .., 2 )` was added after the first build, and it fixes a real
contradiction rather than a hypothetical one.** Without it the colour reads the
full precision while the label reads two decimals, so on 2026 Q2 Saint-Laurent
sat at **0.998530×**, printed *1.00×*, and was coloured pale — a column
apparently on the reference line, coloured as if below it. Measured across the
archive: **11 rows display 1.00×; 3 of them are strictly below 1** and 5 are
exactly equal to the island. The same printed figure would therefore come out
in two different colours depending on a third decimal nobody can see.

Rounding first makes **the colour decide on what the reader is shown**. The
cost is that a column can be dark while its top sits a fraction under the line
— 0.04 % of the axis height at 0.9985×, invisible on an axis that reaches 3.5.
Of the two inconsistencies, the visible one is the one worth removing.

⚠️ **The same hex means something different on page 3, and that is deliberate.**
`#17527A` is *within reach* there and *dearer than the island* here. What the
reader learns is not a meaning per colour but a direction — **darker is more of
the thing being measured** — and the two pages are consistent in that. Which is
also why the map's gradient is pinned to the same two colours, Minimum
`#5B9BC4` to Maximum `#17527A`: on this page the map and the columns must not
disagree about which end is dear. The `#C7CCD1` *Blank area* grey stays outside
both, being neutral.

⚠️ **A sector whose median APCIQ withheld has no bar and no colour, and both
read as a zero.** That is why the table beside them carries `Price status`: the
bar gives the ranking, the map gives the geography, the table says why a place
is empty. Never any of them alone. Switch the property type to Plex and the
effect is immediate — see the acceptance figures below.

**The sort is recalculated every quarter, and the ranking it shows really
moves.** A Power BI bar sorted by a measure re-sorts itself in each filter
context, so the order on screen is always the selected quarter's own. Measured
across the 29 quarters, condominium:

| What the ranking does | Measured |
|---|---|
| sectors moving **5 places or more** over the archive | **9 of 18** |
| largest swing | sector 7 (NDG), from **2nd to 11th** |
| first quarter vs last | **11 of 17** sectors changed rank, largest move 7 places |
| average move from one quarter to the next | 1.15 places, 60 moves of 3+ over 476 pairs |
| sector 9 (Centre) | **1st in all 29 quarters, without exception** |

**But a recalculated sort shows the order and hides the movement**: when one
sector climbs, every other one shifts, and the eye has to re-read the names to
notice. That is why `Sector rank (price)` sits in the bar's tooltip and as a
column in the table — a rank read as a number can be compared across two
quarters without reconstructing an order. The colour of the map and the length
of the bar answer "how much"; the rank column answers "which place, and has it
changed".

The rank is also the honest way to read the top and bottom of this chart, which
barely move: sector 9 has been first in every published quarter, and the churn
measured above is concentrated in the middle of the table.

#### The map, and the one absence it has to show

**Built and accepted on 2026-08-31**, together with the relative column chart
beside it. `Shape map` colours a shape file you hand it: it geocodes nothing and
contacts no external service. The file is generated from the same table the page reads
its numbers from:

```bash
.venv/Scripts/python.exe scripts/export_map_shapes.py --layer sectors
```

`powerbi/shapes/apciq_sector_island.geojson` — 18 features, 720 kB, one property
per feature (`sector_id`). **It is smaller than the 541-tract file of page 2**,
because the union that builds it erases every internal border. Its outlines are
the union of each sector's census tract polygons; `docs/geography.md` section 5
carries the construction, the majority rule it needs and the proof that the
eighteen cover the island exactly once.

**`Color saturation` is used here and was refused on page 2, and the difference
is the number of absences.** Filling `Color saturation` greys out the
per-location colour entirely and offers a single *Blank area* colour. Page 2 has
**two** absences that must not look alike — no APCIQ price, and no 2020 census
income. **This page has one**: a sector APCIQ did not price. One absence, one
grey, and in exchange the tooltip and the colour legend come for free instead of
being rebuilt by hand.

⚠️ **The grey has to be told apart from the bottom of the scale**, which is the
whole risk of a saturation map: "cheapest" and "not published" are adjacent
colours by default. Set *Blank area* to a colour that is not on the ramp — the
neutral grey `#C7CCD1` already used for *Out of reach* on page 3 — and check it
on the acceptance slice below, where more than half the island is grey.

**Both were constated in Desktop on 2026-08-31, and one of them cost a
measure.**

⚠️ **`Color saturation` renders NO legend on this visual.** The gradient paints
correctly and nothing on screen says what a shade is worth — the same kind of
silence as page 2 losing its automatic tooltip, and worse here, because the
scale is automatic: the colours mean something different in every quarter and
the reader is told neither value nor direction.

**A text measure was written to replace it and dropped the same day.** It read
the palest and darkest published price out of `ALLSELECTED` and printed them
as a sentence, so the caption would follow the scale it described. Rejected on
sight: **a line of text under a map is a lot of text for a
legend**, and this page is already dense. The measure is recorded here and not
in the model.

**What replaces it is a drawn gradient shape**, added by hand beside the map.
⚠️ **It must carry no figures.** The scale is automatic, so any amount written
on a static shape is wrong by the next quarter — the shape says *pale → dark =
cheaper → dearer* and names the grey, and the exact value stays in the tooltip.
A legend that states a direction is honest; one that states a bound it cannot
keep is not.

**Legend is a fourth well on this visual, and it stays empty.** `Color
saturation` is what produces the gradient; filling `Legend` colours by category
instead, and the two would contest the same colour.
**Projection: Mercator**, constated, and accepted. The island comes out
stretched east-west as expected at 45° N; nothing on this page compares areas,
so the distortion costs nothing here. It would matter if a shape were ever read
as a quantity — `area_basis` in `dim_geography` exists for that reason.

**The Tooltips well is filled by hand** even though `Color saturation` provides
an automatic one: `Sector[name]`, `Price status`, `Price relative to the
island`, `Sector rank (price)`. Without `Price status`, a grey shape does not
say whether APCIQ withheld the figure or the join failed — and those two look
identical on a map.

#### The figures this page has to reproduce

Measured against the database on 2026-08-31. **The three colour classes must add
up to 18**, the shape count of the file — the cheapest check that no sector is
drawn twice or lost:

| Type / quarter | Coloured | Grey, no price | Total |
|---|---|---|---|
| **Condominium / 2026 Q2** | **17** | **1** (sector 17, Montréal-Nord) | 18 |
| Single-family / 2026 Q2 | 14 | 4 | 18 |
| Plex / 2026 Q2 | 9 | 9 | 18 |
| **Plex / 2022 Q3** | **7** | **11** | 18 |

**Plex 2022 Q3 is the acceptance case, not condominium.** At 11 grey shapes it
puts more than half the island in the "no published price" colour, which is the
only slice that shows whether that colour reads as an absence rather than as a
cheap sector. It is the sector-map equivalent of the 216 grey tracts page 2 is
recetted on.

**Reproduced on screen on 2026-08-31**: 17 coloured and 1 grey on condominium
2026 Q2, Centre first at 1.59×, Pointe Est de l'Île ranked 17, Montréal-Nord
with no column, no colour and `withheld` in the table. **Nothing had to be
corrected in the figures**; the two defects found during the build were both in
the measures, and both are recorded above — the ranking universe and the
rounding of the colour threshold.

For the bar, on any slice: the topmost sector reads above **1.0×** and the
bottom one below it, no bar exceeds the 3.5× axis, and the sector order is
identical to the order `Median price` produced before the change — that identity
is the regression check, and it holds on all 87 slices.

**Every visual on this page carries a geography filter, and none of them is
optional.** The map, the bar and the table exclude the island so it does not sit
beside its own eighteen parts. The KPI row and the line do the opposite for a
different reason: `Median price` and `Days on market` count the rows left
standing and return blank above one, so without `is island` they would read
blank on a page that has nineteen geographies in scope. The two island measures
carry their own island filter and are indifferent to it.

**Single select on property type is not a preference.** `Median price` returns
blank whenever the selection covers more than one published cell, which is what
happens the moment two property types are in play. That is deliberate — see
section 3 — and a required single-select slicer is what turns a confusing blank
into an obvious control.

**Both slicers are load-bearing, and the quarter one is the less obvious of the
two.** `Median price`, `Price context`, `Price status` and `Days on market`
return blank above one surviving row. With the island filter and one property
type but *no* quarter, twenty-nine rows survive — one per published quarter — so
the price and the days-on-market cards read blank. The quarter slicer is not a
convenience; it is what makes half the page non-empty. Set it to **Dropdown**
(Format > Slicer settings > Options > Style), single select, and leave the newest
quarter selected when saving.

**Then set every interaction by hand, because the page has two geographic zones
that exclude each other.** The KPI cards and the price line accept only the
island row; the map, the bar and the table accept only the eighteen sectors.
Left on their defaults, a click in one zone filters the other to
`island AND apciq_sector`, which is the **empty set** — the cards read `--`, the
line vanishes, the table empties. That is not a rendering fault and the values
are not merely small: there is nothing left to show.

It also looks different depending on the target, which is worth knowing before
diagnosing it. A chart that receives a selection **cross-highlights**: it keeps
its full height in a pale tint and paints the selected share solid, so an empty
selection reads as bars that have gone faint rather than as bars that have gone.
A table cannot highlight — it can only be filtered — so it simply empties. **A
`Shape map` does neither**: an empty selection leaves every shape in its *Blank
area* colour, which is the same grey that means "no published price". On this
visual an interaction fault and a data absence look identical, which is the
strongest reason the two zones stay sealed.

**Format > Edit interactions**, then set each source visual in turn:

| Source clicked | KPI cards | Price line | Map | Sector bar | Table |
|---|---|---|---|---|---|
| Property type slicer | Filter | Filter | Filter | Filter | Filter |
| Quarter slicer | Filter | **None** | Filter | Filter | Filter |
| Price line | **None** | — | **None** | **None** | **None** |
| Map | **None** | **None** | — | Filter | Filter |
| Sector bar | **None** | **None** | Filter | — | Filter |
| Table | **None** | **None** | **None** | **None** | — |

Four rules produce that table. **The two slicers drive everything**, because
they are the only controls whose scope is the whole page. **The price line
drives nothing**: its axis is the quarter, which the slicer already governs, and
it is meant to stand still as the history behind the selected quarter. **Nothing
crosses between the zones**, in either direction. And inside the sector zone the
three visuals do cross-filter, in the two directions a reader actually uses:
click a shape on the map to find its bar and its row, click a bar to light up
its shape. The table drives nothing, because a table click is as easily
accidental as deliberate and it would repaint the map.

⚠️ **Map → bar is a filter, not a highlight, and that is worth checking at the
screen.** Filtering the bar down to one sector removes the constant line's
context: a single bar beside a 1.0× line still reads correctly, but the ranking
is gone. If it reads badly in practice, the fix is to set map → bar to
*Highlight* rather than to unpick the zone rule.

**The date dimension is wider than this page, and stays that way.** `date`
starts on 2015-01-01 because the Bank of Canada series are daily and weekly from
then; page 4 uses those years. `fact_market` starts in 2019 Q2. Narrowing the
dimension would amputate page 4, so the quarters with no market data are removed
per visual — the slicer carries a visual filter
`Sales (island, as published) is not blank` — never from `'date'` itself.

### Page 2 — Affordability

*The same market, read against what households earn, at the census tract.*

| Element | Field or measure |
|---|---|
| Slicers | property type (single select), `household_profile[name_en]`, quarter |
| KPI | `Share of tracts affordable`, `Tracts evaluated`, `Income required, lower bound (mean)` |
| Line | `Share of tracts affordable` by `'date'[quarter_label]` — **the finding** |
| Bar | `Share of tracts affordable` by `Sector[name]` |
| Table | `Sector[name]`, `Census_Tract[name]`, `Household income (2020 census)`, `Income required, lower bound (mean)`, `Income shortfall (mean)`, `Price to income (median)`, `Verdict` — sorted by shortfall ascending |
| **Shape map** | `Census_Tract[geography_code]` in **Location**, colour by `Tract map colour` — see below |
| Card | `Income vintage warning` |
| Card | `Grain warning` |
| Card | `Map coverage note` |

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

#### The map, and why it is on this page and not another

**Built and accepted on 2026-08-30.** `Shape map` colours a shape file you hand
it: it geocodes nothing and contacts no external service, which is why it can
draw a geography no mapping provider knows about.

The shape file is generated from the same table the page reads its numbers
from, by `scripts/export_map_shapes.py` — 541 features, 1.3 MB, one property per
feature. Regenerate it after any change to `dim_geography`:

```bash
.venv/Scripts/python.exe scripts/export_map_shapes.py
```

⚠️ **A census tract id looks like a number and is not one.** `4620001.00`
written as a JSON number becomes `4620001`: the file loads without error and
joins to nothing. Every key is written as a string and the script refuses to
write a file where that stops being true. Confirm the match in Power BI with
*Format visual > Map settings > View map type key* before looking anywhere else.

**`Color saturation` is deliberately left empty, and that costs the automatic
tooltip.** Microsoft documents three colour configurations, and they exclude one
another: filling `Color saturation` greys out the per-location colour entirely.
It also offers a single *Blank area* colour — and this page has **two** absences
that must not look alike:

| Absence | Shapes | What it means |
|---|---|---|
| no APCIQ price | **18** | the whole of sector 17, Montréal-Nord — one solid block |
| no 2020 census income | **11** | near-empty tracts, suppressed at source, scattered |

One grey for both would say the same thing about "APCIQ published no price
here" and "almost nobody lives here". So the map uses `Location` alone with
*Colors > Location > Fx > Format style = Field value*, pointing at a measure
that returns a hex string — and the fields that `Color saturation` would have
put in the tooltip are added to the **Tooltips** well by hand.

**The scale is fixed at 0 to 15× annual income, never autoscaled.** An
autoscaled map repaints itself every time a slicer moves, which hides exactly
the trend the page exists to show. Clipping at 15 costs **2.09 %** of rows
overall, **0 %** on condominium and 4.51 % on single-family — measured
2026-08-30, where the single-family maximum is 2.4 times its own 99th
percentile. A scale stretched to that outlier would flatten everything else.

**`Verdict` gained a branch because of this map.** The table on this page
carries `Sector[name]` *and* `Census_Tract[name]`, so every row is unique. **The
map carries only the tract**, so `4620511.02` — the one genuinely shared tract
of the island, J3.4 — arrives with both its rows in context and `SELECTEDVALUE`
returns blank. Measured over its 261 combinations: **174 disagree on the price
and 12 disagree on the verdict**, and in those 12 the original measure would
have printed *No published price* for a tract that has two. The `Sectors > 1`
branch fires first and names the real situation. It cannot regress the table,
where a sector is always filtering and the count is always one.

#### The figures the map has to reproduce

Measured 2026-08-30, quarter **2026 Q2**. The three colour classes must add up
to 541 — the shape count of the file — which is the cheapest check that no
tract is drawn twice or lost:

| Type / profile | Shaded | Grey, no price | Beige, no income | Affordable | Median ratio |
|---|---|---|---|---|---|
| **Condominium / Couple** | **512** | **18** | **11** | 179 | not reproduced |
| Condominium / One person | 512 | 18 | 11 | 1 | not reproduced |
| **Plex / Couple** | 317 | **216** | 8 | 0 | not reproduced |
| Single-family / Couple | 395 | 138 | 8 | 2 | not reproduced |

⚠️ **512 shapes, not the 513 rows the KPI counts.** The shared tract is one
shape and two rows; confusing the two is how a map ends up asserting a count
the page contradicts. With the `Sectors > 1` branch the split reads
511 + 1 + 18 + 11.

**Plex is the acceptance case, not condominium.** At 216 grey shapes it puts
40 % of the island in the "no published price" colour, which is the only slice
that shows whether that colour truly reads as an absence rather than as a low
ratio. Verified on 2026-08-30: 317 / 216 / 8, exact.

**One interaction is switched off: the map must not filter the three KPI
cards.** Same mechanism as the bar chart on page 3 — clicking one tract turns
"179 of 512" into "0 of 1", which reads as *nothing is affordable*. The table
and the bar stay on *Filter*.

⚠️ **Still to set at the close of 2026-08-30**: that interaction, and moving the
visual from the scratch page it was built on onto Affordability itself. The
measures, the shape file, the join and the four acceptance slices are done and
verified; these two are placement, not correctness.

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
| **Map** | `Shape map`, `Sector[geography_code]` on **Location**, colour by `Sector bar colour` through *Colors > Location > `fx` > Field value*, tooltips `Verdict for this income`, `Income required, lower bound (mean)`, `Tracts priced` |
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

#### The map, and why it is the sector map and not the tract map

**Built and accepted on 2026-08-31.** No new measure was written for it: it
reads `Sector bar colour`, which the column chart beside it already reads.

**The map asked for on this page was a census tract map of the required income,
and it was refused on a measurement.** The map feasibility study counted it: on
2026 Q2, condominium, couple profile, the required income takes **17 distinct
values across 541 census tracts**. A tract map would draw 541 polygons to show
17 answers and imply a precision that does not exist, which section 41.2 of the
brief forbids. The alternative of comparing the required income to each tract's
own household income was measured too — it reproduces `meets_income_requirement`,
which *is* page 2, and it would take `Income input` out of the loop on the one
page whose only control is that slider.

So the map here is the **eighteen sectors, coloured by the verdict**: 18 shapes
for 17 values, it moves with the slider, and it reuses the shape file of page 1
at no extra cost. Two of the report's maps sharing one outline is not a
weakness — the reader learns the island once and then compares a price to a
verdict on the same silhouette.

| Well | Field |
|---|---|
| Location | `Sector[geography_code]` |
| Colors > Location > `fx` > Format style | **Field value**, on `Sector bar colour` |
| Tooltips | `Verdict for this income`, `Income required, lower bound (mean)`, `Tracts priced` |

**It reuses `Sector bar colour` unchanged, and that is the point rather than an
economy.** The bar and the map read the same measure, so they cannot disagree
about where the 10 % band falls — the fault this page was specified with, a card
and a table on two thresholds, is structurally impossible between these two.
Adding a second colour measure for the map would have re-created it.

**`Color saturation` cannot be used here**, unlike page 1: it takes a number and
this map paints a verdict, which is a category. Colour by location through `fx`
is the only configuration that does that — at the cost of the automatic tooltip,
which is why three fields are added to the Tooltips well by hand.

⚠️ **A shape map cannot be cross-highlighted**, so an empty selection and a
"no published price" sector are the same grey. `Sector bar colour` returns
`#E8EAEC` for the fourth branch — a lighter grey than *Out of reach* — and those
two shades are the whole legend, since conditional formatting produces none. The
tooltip is where the words are.

**One thing this map is safe from that page 2 was not.** The tract map broke a
branch of `Verdict` because a shape carried only the tract, and the one shared
tract of the island then arrived with two rows. Measured here: across the whole
of `fact_affordability`, **no sector slice holds two different required
incomes** — 18 sectors, 18 geography keys, zero slices with two values. One
shape is one value, and `AVERAGE` over a sector's tracts averages a constant.

#### The figures the map has to reproduce

Same slice as the rest of the page — condominium, couple, 2026 Q2, 95 000 $ —
and **the four colour classes must add up to 18**, which is the same check the
KPI row already carries:

| Colour | Verdict | Shapes |
|---|---|---|
| `#17527A` | Within reach | **6** |
| `#5B9BC4` | Borderline | **1** |
| `#C7CCD1` | Out of reach | **10** |
| `#E8EAEC` | No published price | **1** (sector 17, Montréal-Nord) |
| | **Total** | **18** |

Move the slider and the map has to keep answering: at **30 000 $** and at
**60 000 $** every priced sector is *Out of reach* and exactly one stays in the
"no published price" shade — a map that goes entirely blank at the low end of
the slider has a blank-versus-zero fault, not an empty market.

**One interaction is switched off, for the same reason as the bar: the map must
not filter the three KPI cards.** Clicking one sector turns "6 of 17" into
"0 of 1" or "1 of 1", which reads as a verdict about the island. Map → table
stays on *Filter*, so a click on a shape finds its row.

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
| Slicer | `'date'[calendar_year]`, **Dropdown**, multi-select, nothing selected when saving |
| KPI | `Posted minus contract (points)` |
| Card | `Rate freshness warning` |
| Line | `Rate (mean of period)` by `'date'[date_key]`, **continuous** axis, legend `interest_rate_series[rate_kind]` |
| Combo (line and stacked column) | columns `Sales (island, 12 months)`, line `Contract rate (mean)`, by `'date'[quarter_label]` — **both Y-axis ranges pinned by hand** |
| Card | `Trailing window` |
| Card | `Rate grain warning` |
| Table — series | `series_label`, `rate_kind`, `frequency`, `Rate observations`, `First rate observation`, `Last rate observation`, `what_it_is` |
| Table — quarters | `'date'[quarter_label]`, `Posted rate (mean)`, `Contract rate (mean)`, `Posted minus contract (points)`, `Rate observations` |
| Text box | the association caveat — see below |

`calendar_year` is a whole number, so Power BI renders its slicer as a **numeric
range** by default. Set the style to Dropdown: a range slider always holds a
value, so "nothing selected" does not really exist on it, and isolating one year
means dragging two handles. Both check passes below become tedious to reproduce,
and a check that is tedious does not get repeated. The same will happen with
`calendar_quarter`. If the eleven-year line wants a zoom, the line chart has its
own **zoom slider** (Format > General), which touches no other visual.

The series table is the page. Three series that all look like "the interest
rate" on a chart are three different things, and the posted one — the one most
reports would have used — stood **1.84 points above** the contracted one in
2026 Q2, which moves the required income by about 15 %. `rate_kind` is in the
table although `series_label` almost repeats it: it is the exact token the line
chart legend shows, and it is what maps a colour to a row. `what_it_is` gets the
widest column and word wrap — it is the column that justifies the page.

Sort `series_label` by `sort_order` (*Column tools > Sort by column*), once, in
the model. Alphabetical order puts the posted rate above the contracted one,
which is the reverse of the hierarchy the page argues for.

**`Rate grain warning` names each series and the observations behind its
average**, so no chart on this page can imply the weekly series was observed as
often as the daily one. That is section 22 of the brief in one card.

#### The contracted series stopped publishing on 2026-06-02, and calling that a lag was wrong

**This paragraph replaces one written on 2026-08-27 that explained the gap as a
publication lag.** That explanation fitted one quarter and no others, and it was
never measured — the same fault the trailing-12-month finding of J3.5 avoided by
refusing to explain what the source does not state.

Measured on 2026-08-30, on the loaded table and then against the live Valet API:

| Series | Last observation | Days behind the newest the model holds |
|---|---|---|
| Policy (`V39079`) | 2026-08-25 | 1 |
| Posted (`V80691335`) | 2026-08-26 | 0 |
| Contracted (`FVI_MTG_RATE_5Y_FIX`) | **2026-06-02** | **85** |

There was no lag before that. Over its whole history the contracted series runs
at a cadence of **exactly 7 days, minimum gap 7, maximum gap 7, not one gap
above 7** — 596 observations since 2015-01-06 — and it landed on or near the
quarter end every quarter through 2026 Q1 (13 observations, last 2026-03-31).
Then it stops. 2026 Q2 holds 9 of its 13 weeks; **2026 Q3 holds none at all**,
while the posted series holds 9 and the policy rate 40.

`GET https://www.bankofcanada.ca/valet/observations/FVI_MTG_RATE_5Y_FIX/json?recent=3`
→ 200, newest observation 2026-06-02, on 2026-08-30. So this is the source, not
the ingestion: the API answers, the series exists, and it has published nothing
for twelve weeks. `GET /valet/series/FVI_MTG_RATE_5Y_FIX/json` → 200 returns a
label and a one-line description and **says nothing about a discontinuation**.

Whether the series is suspended, retired, or merely very late is **`[INCONNU]`**
and must not be guessed on the page. What is certain is the consequence, and it
is not confined to page 4: this is the rate `fact_mortgage_scenario` prices
with. Every quarter it prices today is covered, because APCIQ's newest edition
is 2026 Q2. **The next APCIQ edition would arrive with no contract rate at all.**

That is why `Rate freshness warning` exists and why it names any series more than
three weeks behind the rest rather than naming this one. It is a card, not a dbt
test: a source that stops publishing is a publisher defect, and J3.2 settled that
a publisher defect earns a verdict on screen, never a build that refuses to run.
The dbt `freshness` declarations answer a different question — when *we* last
loaded — and would stay green here. Detecting it automatically belongs to the
n8n orchestration of J4.3.

#### The KPI reads whatever the slicer holds, and the quarter table is where the headline can be found

`Posted minus contract (points)` has no quarter of its own. Measured on
2026-08-30, the same card reads three different figures depending on the slicer:

| Slicer | Reads |
|---|---|
| nothing selected (2015 → 2026) | 2.11 points |
| `calendar_year` = 2026 | 1.93 points |
| 2026 Q2 alone | 1.84 points |

None is wrong and none is the headline. The headline is the third, and a year
slicer cannot produce it — hence the quarter table, whose 2026 Q2 row carries
the 1.84 in a place a reader can point at. **A card whose value moves with a
slicer needs somewhere on the page where the number the text quotes is legible.**

#### The line chart needs a continuous axis, and that is not a cosmetic setting

Checked against learn.microsoft.com on 2026-08-30, page dated 2026-02-17
(*High-density line sampling in Power BI*):

* the sampling algorithm **is available for line and area charts with a
  continuous x-axis** and is On by default;
* a **categorical** axis shows a missing value as a break in the line. Both
  mortgage series publish once a week against a date dimension that carries
  every day, so on a categorical axis they would be six gaps in seven — a
  dotted mess that says nothing about frequency and looks like missing data;
* **3 500 points is the maximum displayed on most visuals, across all series
  together.** This chart asks for 4 229, so binning is certain. Binning keeps
  each bin's minimum and maximum, so peaks and troughs survive;
* a consequence to recognise rather than debug: **hovering a date can show a
  tooltip for one series and nothing for another**, because each series is
  binned independently. Read exact values from the tables, shape from the line;
* if a data source is too large the algorithm **drops legend series in
  alphabetical order**. Three series and 4 229 points are far from that, but
  the order here would be contracted, policy, posted — the posted one falls
  first, and it is the one the page exists to contrast.

#### The combo chart is a dual axis, the objection was raised, and it was kept

**The `dataviz` rule this file already tells the reader to consult calls a
dual-axis chart the single most common charting mistake**, for a reason that
lands squarely on this project: *the alignment of the two scales is arbitrary,
so the chart invents a correlation that isn't in the data.* Section 27 of the
brief forbids presenting a correlation as a cause, and section 6 below states
that every label on this page says *association*.

A stacked pair was built first — volume above, rate below, one shared time axis,
nothing scaled against anything — and then **abandoned on 2026-08-30 in favour
of the combo**. The reason is real and is recorded rather than argued away: the
combo is compact, and a reader sees the relationship in one glance instead of
travelling between two frames. On a page that already carries two tables and
four cards, a frame saved is not nothing.

**What the decision costs, stated once.** The vertical distance between the
column tops and the line is a convention, not a measurement. Slide either scale
and the two series appear to agree more or less. The chart cannot be read for
how *closely* they move — only for whether they move in opposite directions,
which they do.

**And what makes that cost bearable — pin both axis ranges by hand.** Left on
auto-scale, Power BI recomputes both scales on every slicer move, so the apparent
gap between the two series **changes when the filter changes while the data does
not**. That is the part a reader cannot see and cannot correct for. Set
*Format > Y axis > Range* and *Format > Secondary Y axis > Range*, Start and End,
once, on the unfiltered view, and leave them. The alignment stays arbitrary —
nothing fixes that — but it becomes **stable and declared** instead of
recalculated behind the reader. The caveat text box carries more weight here,
not less.

One detail: with a single measure in the column well, *stacked* does nothing
that *clustered* would not.

#### And the volume series had to change too — the quarterly one is mostly the calendar

The question on 2026-08-30 was what the pair was for. Measuring the answer
found a second fault, independent of the first.

**Quarterly sales are strongly seasonal.** Island sales by calendar quarter,
indexed to each year's mean, 2020-2025: **Q1 100 · Q2 117 · Q3 91 · Q4 92**.
Within a single year the strongest quarter beats the weakest by a factor of
**1.36 to 1.92**, every year measured. Raw quarterly sales beside a rate line
therefore show the calendar as much as the market — and a reader attributes the
sawtooth to the rate. This fault is **independent of the chart type**: it
survives a combo, a stacked pair, or anything else built on the quarterly
series.

**`fact_market_trailing_12m` fixes it by construction**: a twelve-month window
always contains all four seasons. Measured, same years: the intra-year ratio
falls from 1.36–1.92 to **1.05–1.28**. What is left is the movement, not the
calendar.

So the columns read `Sales (island, 12 months)`, never `Sales (island, as
published)`. This is also the first use the trailing table has found in the
report: it was imported at page 1 and had answered nothing until here.

⚠️ **One residual, accepted rather than solved: consecutive windows overlap by
nine months, and columns read as buckets that partition the period.** They do
not — adding two neighbouring columns counts most of a year twice. Nothing on
the chart invites the addition and no total is shown, so the risk is conceptual
rather than arithmetic, but it is the reason the `Trailing window` card sits
beside the visual and the reason the title has to say *12 months to*. A line
carried the same series without that reading; the column well came with the
combo.

**No coefficient goes on this page, and the reason is arithmetic rather than
caution.** Twenty-nine overlapping windows are not twenty-nine independent
observations — neighbours share three quarters of their data, so the effective
count is nearer seven, and any correlation computed on them is inflated. Two
series that each carry a trend correlate almost by construction. And a pandemic
sits in the middle of the window, having pushed rates down and housing demand up
at the same time — a textbook confounder. The direction is not settled either:
a central bank raises rates *in response* to an economy that includes housing.

**What the report can assert instead is stronger, and it is not statistical.**
The link between the rate and purchasing power is not observed here, it is
*computed*: `fact_mortgage_scenario` takes the contracted rate, applies the CMHC
qualifying rate, the amortization and the debt-service ratio, and returns a
required income. Raise the rate and the required income rises — by arithmetic.
The two curves illustrate that mechanism on the real market; they are not asked
to prove it. The lag analysis section 28 of the brief asks for is real
statistical work and belongs to J5, not to a milestone whose job is to finish.

#### Titles, captions, and the one that must not be a text box

A card is for text that **changes with the selection** — `Rate grain warning`,
`Rate freshness warning`, `Trailing window`. Fixed text belongs to the visual's
own title (Format > General > Title) or to a text box, never to a card.

The combo carries a short title on the visual — *Sales (12 months) and the
contracted rate* — and the caveat in a **text box** beneath: three lines of
prose in a visual title get truncated on the first resize.

⚠️ **No count goes in that text box.** The first draft read "over these 29
quarters". A text box is filtered by nothing and refreshes never, so the day a
thirtieth APCIQ edition lands the page states a false figure and nothing flags
it. Either drop the number or make it a measure in a card. Same rule as
everywhere else here: what depends on the data lives in a measure, what does not
lives in fixed text, and mixing them is how a page goes stale in silence.

#### The axis is shorter than the page, and `quarter_label` needs no sort column

`fact_market` and `fact_market_trailing_12m` cover 29 quarters, 2019 Q2 →
2026 Q2; `'date'` runs from 2015-01-01 because the Bank of Canada series do.
Without a visual filter the combo would carry seventeen quarters of rate line
and no columns at all. Filter the **visual** — `Sales (island, 12 months) is not
blank` — never narrow `'date'`: page 4 is precisely the page that needs it
wide, since the three-series line beside it runs the full eleven years.

`quarter_label` is written `2015 Q1`, so its alphabetical order is its
chronological order and it needs no *Sort by column*. That holds for the page 1
and page 2 axes too.

#### Interactions

Simpler than page 1 — there are no mutually exclusive zones here — but the
default is still wrong in one direction that matters. **Five sources**, and only
one of them is allowed to do anything.

| Source clicked | Effect to set on every other visual |
|---|---|
| Year slicer | **Filter**, everywhere |
| Rate line (daily, three series) | **None**, everywhere |
| Combo (12-month sales and contract rate) | **None**, everywhere |
| Series table | **None**, everywhere |
| Quarter table | **None**, everywhere |

The four cards are never sources — they appear only as targets.

One rule: **the slicer drives, nothing else does**, and three separate reasons
converge on it.

**The page holds two grains.** The three-series rate line is at the *day*; the
combo and the quarter table are at the *quarter*. Clicking one point of
the rate line selects a single day, which propagates through `'date'` to facts
keyed on a quarter *start* date — so it empties the quarterly visuals on 89 days
out of 90.

**The reverse collapses the history.** Clicking a quarter reduces an
eleven-year daily chart to three months, which is the view the page exists to
give.

**And a click inside the combo removes the comparison it exists to show.**
Selecting one column filters the visual to that quarter, leaving a single column
and a single point of line — the pair of shapes the chart is read for is gone.

`Rate freshness warning` removes `'date'` twice by construction, so it is
indifferent to every source and there is nothing to set on it. That is also the
check: **if it goes quiet when a year is selected, the `ALL ( 'date' )` calls
have been lost**, and a source outage became invisible the moment anyone
filtered — the opposite of a control.

#### The figures this page has to reproduce

Measured against the database on 2026-08-30. Every figure here is a Bank of
Canada one, so unlike pages 1 to 3 they can all be written down.

With **nothing selected in the year slicer**:

| Measure | Expected |
|---|---|
| `Rate observations`, series table | 3 025 policy · 596 contracted · 608 posted |
| `First rate observation` | 2015-01-01 · 2015-01-06 · 2015-01-07 |
| `Last rate observation` | 2026-08-25 · **2026-06-02** · 2026-08-26 |
| `Posted minus contract (points)` | 2.11 |
| `Rate freshness warning` | fires, naming the contracted series at 2026-06-02 |
| `Rate grain warning` | fires, naming all three series with the counts above |
| `Trailing window` | `12 months, 2018-07-01 to 2026-06-30` |
| The combo | **29 columns**, 2019 Q2 → 2026 Q2 |
| The three-series rate line | the contracted line stops in June 2026, the other two run on |

With **`calendar_year` = 2026**:

| Measure | Expected |
|---|---|
| `Rate observations` | 168 policy · 22 contracted · 34 posted |
| `Posted minus contract (points)` | 1.93 |
| Quarter table, 2026 Q1 | posted 6.09 · contracted 4.10 · gap 2.00 · 13 contract observations |
| Quarter table, **2026 Q2** | posted 6.09 · contracted 4.25 · **gap 1.84** · 9 contract observations |
| Quarter table, **2026 Q3** | posted 6.09 · contracted **blank** · gap **blank** · 0 contract observations |
| `Rate freshness warning` | fires, unchanged — the year slicer must not silence it |
| `Trailing window` | `12 months, 2025-04-01 to 2026-06-30` |

**Two rows carry the whole check, because they are the only two things on this
page that can be wrong while looking right.**

**2026 Q3, the gap cell.** Blank is correct. **6.09** is the unguarded
subtraction of section D, and it is the only figure here a wrong measure returns
*confidently*. Everything else either matches or goes visibly blank.

**`Rate freshness warning` with a year selected.** If it disappears, the
`ALL ( 'date' )` calls have been dropped and a publisher outage becomes
invisible the moment anyone filters.

The combo must run **2019 Q2 → 2026 Q2, 29 columns**. Thirty or more means the
visual filter was lost and the empty quarters of `date` are showing. **A
repeating annual sawtooth on the columns means they are reading `fact_market`
instead of `fact_market_trailing_12m`** — that is the seasonality fault
returning, and it is the one thing on this visual that looks like a finding and
is not.

`scripts/report_oracle.py` prints the rate figures under *PAGE 4*; two of its
three tables there were added on 2026-08-30 with this page. The one element it
does **not** cover is the sales line, which is an APCIQ figure: its check is the
*PAGE 1 — Sectors minus island* table, the same underlying column.

**Built on 2026-08-30, and both passes reproduced.** Everything that changed,
changed *during* the build rather than after it, because the measures were
checked against the database before anything was drawn: the volume series moved
from quarterly to twelve-month trailing, the year slicer came off Power BI's
numeric-range default, the series table went from a throwaway check to the
centrepiece, and the combo was replaced by a stacked pair and then reinstated as
a combo with its axis ranges pinned. Nothing had to be corrected once the page
existed.

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
| Rates | `Rates` | `fact_interest_rate`, `interest_rate_series` |
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
thirty-eight, and a name that reads the same in the model and on the page.

### 3.2 Index

Every measure, its group, what it reads, its format, and where it is used.
**This table is the formatting reference** — there is no second list to keep in
step with it.

| Group | Measure | Home table | Reads from | Format | Page |
|---|---|---|---|---|---|
| Guards | `Grain warning` | `_Measures` | filter state of `Census_Tract` | Text | 2, 3 |
| Guards | `Income vintage warning` | `_Measures` | `fact_affordability` | Text | 2 |
| Guards | `Income basis note` | `_Measures` | `fact_affordability` | Text | 2 |
| Guards | `Selected area disclosure` | `_Measures` | `Place` | Text | 1, 2, 3 |
| Guards | `Slice warning` | `_Measures` | `property_type`, `fact_affordability` | Text | 2, 3 |
| Market | `Sales (island, as published)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1 |
| Market | `Sales (selected area)` | `_Measures` | `fact_market`, `Place` | Whole number, thousands sep. | 1 |
| Market | `Active listings (selected area)` | `_Measures` | `fact_market`, `Place` | Whole number, thousands sep. | 1 |
| Market | `Area title` | `_Measures` | `Place` | Text | 1 |
| Market | `Sales (sectors)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1, 4 |
| Market | `Sectors minus island (sales)` | `_Measures` | the two `Sales` measures | Whole number | 1 |
| Market | `Median price` | `_Measures` | `fact_market` | Currency, 0 dec., thousands sep. | 1 |
| Market | `Price context` | `_Measures` | `fact_market` | Text | 1 |
| Market | `Price status` | `_Measures` | `fact_market` | Text | 1 |
| Market | `Days on market` | `_Measures` | `fact_market` | Whole number | 1 |
| Market | `Active listings (island)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1 |
| Market | `Price relative to the island` | `_Measures` | `Median price`, `Sector` | Custom `0.00"×"` — **never a currency** | 1 |
| Market | `Sector rank (price)` | `_Measures` | `Median price`, `Sector` | Whole number | 1 |
| Market | `Sector price colour` | `_Measures` | `Price relative to the island` | Text — a `#RRGGBB` string, **never formatted** | 1 |
| Market | `Sales (island, 12 months)` | `_Measures` | `fact_market_trailing_12m` | Whole number, thousands sep. | 4 |
| Market | `Trailing window` | `_Measures` | `fact_market_trailing_12m` | Text | 4 |
| Affordability | `Tracts evaluated` | `_Measures` | `fact_affordability` | Whole number | 2 |
| Affordability | `Tracts affordable` | `_Measures` | `fact_affordability` | Whole number | 2 |
| Affordability | `Household income (theoretical)` | `_Measures` | `fact_affordability` | Currency, 0 dp | 2 |
| Affordability | `Share of tracts affordable (2020 dollars)` | `_Measures` | `fact_affordability` | Percentage | 2 |
| Affordability | `Share of tracts affordable` | `_Measures` | the two `Tracts` measures | Percentage, 1 dec. | 2 |
| Affordability | `Income required, lower bound (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2, 3 |
| Affordability | `Household income (2020 census)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Income shortfall (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Price to income (median)` | `_Measures` | `fact_affordability` | Custom `0.0"×"` — **never a currency** | 2 |
| Affordability | `Verdict` | `_Measures` | `fact_affordability` | Text | 2 |
| Affordability | `Tract map colour` | `_Measures` | `Verdict`, `Price to income (median)` | Text — a `#RRGGBB` string, **never formatted** | 2 |
| Affordability | `Map coverage note` | `_Measures` | `fact_affordability` | Text | 2 |
| Rates | `Rate (mean of period)` | `_Measures` | `fact_interest_rate` | Decimal, 2 dec. | 4 |
| Rates | `Contract rate (mean)` | `_Measures` | `Rate (mean of period)`, `interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted rate (mean)` | `_Measures` | `Rate (mean of period)`, `interest_rate_series` | Decimal, 2 dec. | 4 |
| Rates | `Posted minus contract (points)` | `_Measures` | the two rate means | Decimal, 2 dec. | 4 |
| Rates | `Rate observations` | `_Measures` | `fact_interest_rate` | Whole number, thousands sep. | 4 |
| Rates | `First rate observation` | `_Measures` | `fact_interest_rate` | Custom `yyyy-mm-dd` | 4 |
| Rates | `Last rate observation` | `_Measures` | `fact_interest_rate` | Custom `yyyy-mm-dd` | 4 |
| Rates | `Rate grain warning` | `_Measures` | `fact_interest_rate`, `interest_rate_series` | Text | 4 |
| Rates | `Rate freshness warning` | `_Measures` | `fact_interest_rate`, `interest_rate_series` | Text | 4 |
| First-time buyer | `Sectors priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Sectors within reach of this income` | `_Measures` | `fact_affordability`, `Income input` | Whole number | 3 |
| First-time buyer | `Sectors borderline` | `_Measures` | `fact_affordability`, `Income input` | Whole number | 3 |
| First-time buyer | `Tracts priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Verdict for this income` | `_Measures` | `fact_affordability`, `Income input` | Text | 3 |
| First-time buyer | `Sector bar colour` | `_Measures` | `Verdict for this income` | Text | 3 |
| First-time buyer | `Down payment assumption` | `_Measures` | nothing — a constant string | Text | 3 |
| First-time buyer | `Verdict for the selected place` | `_Measures` | `Verdict for this income`, `Place` | Text | 3 |
| — | `Income input Value` | `Income input` | the slicer selection | Currency, 0 dec. | 3 |

### 3.3 Build order

Eight measures reference another measure, and one group references a table that
section 5 creates. Typing them out of order gets a red squiggle and no
explanation, so build in this order:

| Order | Create | Because |
|---|---|---|
| 1 | `Sales (island, as published)`, `Sales (sectors)` | `Sectors minus island (sales)` subtracts one from the other |
| 2 | `Median price` | `Price relative to the island` and `Sector rank (price)` both read it |
| 2b | `Price relative to the island`, `Sector rank (price)` | need `Median price` above |
| 2b bis | `Sector price colour` | reads `Price relative to the island` rather than repeating its comparison |
| 2c | the rest of the Market group | independent |
| 3 | `Tracts evaluated`, `Tracts affordable` | `Share of tracts affordable` divides one by the other |
| 4 | the rest of the Affordability group | independent |
| 5 | `Rate (mean of period)` | the two rate means wrap it in `CALCULATE` |
| 6 | `Contract rate (mean)`, `Posted rate (mean)` | `Posted minus contract (points)` reads both, and tests both for blank |
| 7 | `Posted minus contract (points)` | needs the two above |
| 7b | `Rate observations`, `First rate observation`, `Last rate observation`, `Rate grain warning`, `Rate freshness warning` | independent |
| 7c | `Sales (island, 12 months)`, `Trailing window` | Market group, but built with page 4 — nothing before it needed the trailing table |
| 8 | **the `Income input` parameter (section 5)** | three First-time buyer measures read `'Income input'[Income input Value]` |
| 9 | the First-time buyer group, `Verdict for this income` before `Sector bar colour` | the colour measure reads the verdict rather than repeating its comparison |
| 10 | the three Grain guards | independent; they only need `fact_affordability`, `property_type` and the `Census_Tract` table |

**Build a group, then build its page, then check the number.** Each group has a
figure already measured against the database, and the report has to reproduce it
or something is wrong upstream of the visual:

| After group | Check | Expected |
|---|---|---|
| Market | `Sectors minus island (sales)` across every quarter | zero everywhere except 2023 Q4, where it is about 0.3 % — reproduced on 2026-08-28 |
| Market | `Sector rank (price)` against the bar's own order, any slice | identical — the rank column and the sort must never disagree, and they cannot, since both read `Median price` |
| Market | `Price relative to the island`, condominium 2026 Q2 | between 0.71× and 1.59×; the archive as a whole never leaves 0.51×–3.29×, so no bar reaches the fixed 3.5× axis |
| Market | the map's colour classes, plex 2022 Q3 | 7 coloured + 11 grey = 18 — the acceptance slice, where more than half the island has no published price |
| Affordability | `Share of tracts affordable`, condominium, couple, by quarter | 93.2 % in 2019 Q2 falling to 35.0 % in 2026 Q2, with the break at 2022 Q2 |
| Rates | `Posted minus contract (points)`, on the quarter table's 2026 Q2 row | 1.84 points — and 1.93 with the year slicer on 2026, 2.11 with nothing selected. All three are the same measure; see page 4 |
| Rates | `Rate freshness warning`, no slicer | names the contracted series, last 2026-06-02, against observations held to 2026-08-26 |
| Rates | `Rate grain warning`, `calendar_year` = 2026 | three series named, the contracted one at 22 observations against 34 posted and 168 policy — measured 2026-08-30 |
| First-time buyer | page 3 at 95 000 $, condominium, couple, 2026 Q2 | 6 within reach, 1 borderline, 10 out of reach, 1 with no published price — and `Sectors priced` reads 17 |

These are the same figures section 1 and section 2 of this file quote. A visual
that disagrees with them is not a new finding — it is a filter in the wrong
place, and catching it at the end of a group is much cheaper than at the end of
the report.

---
### A. Grain guards

The model has two geography dimensions on purpose. `Sector` reaches the market
facts, `Census_Tract` reaches only affordability. Nothing in Power BI stops a
user from putting a tract on an axis beside a market measure — the total would
simply repeat, once per tract, looking like data. These two measures make that
visible.

```dax
Grain warning =
IF (
    ISFILTERED ( 'Census_Tract' ),
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
VAR Types = COUNTROWS ( VALUES ( property_type[name_en] ) )
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
`date`, so it reports what actually reached the fact table after the filter
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
Price relative to the island =
VAR SectorPrice = [Median price]
VAR IslandPrice =
    CALCULATE (
        [Median price],
        REMOVEFILTERS ( Sector ),
        Sector[geography_type] = "island"
    )
RETURN DIVIDE ( SectorPrice, IslandPrice )
```

**It divides by a constant, so it cannot reorder anything** — the island median
is the same figure for every sector of a given quarter and property type.
Verified rather than reasoned: across 1 136 sector-rows over 87 type × quarter
slices, **not one sector changes rank** between this measure and `Median price`.
The bar keeps its ranking and gains an axis that does not move with inflation.

**`REMOVEFILTERS ( Sector )` before the island filter is what makes it work on
page 1**, where the bar carries a visual filter of `is apciq_sector`. Without
it, `Sector[geography_type] = "island"` would intersect with that filter and
return nothing, and `DIVIDE` would hand back a blank for every bar — a chart
that is entirely empty rather than visibly wrong.

**`DIVIDE`, not `/`.** A quarter where APCIQ published sector prices but no
island price would divide by blank; `DIVIDE` returns blank and the bar is
absent, which is the honest outcome. Measured on 2026-08-31: **all 87 slices
that carry sector prices also carry an island price**, so the branch is unused
today. It exists because the archive grows every quarter and the failure would
otherwise be an infinity.

Format: custom `0.00"×"` — a multiple, **never a currency and never a
percentage**. Same rule as `Price to income (median)`.

```dax
Sector rank (price) =
IF (
    NOT ISBLANK ( [Median price] ),
    RANKX (
        FILTER ( ALLSELECTED ( Sector ), Sector[geography_type] = "apciq_sector" ),
        [Median price],
        ,
        DESC,
        DENSE
    )
)
```

**The rank is what a re-sorted bar chart cannot show.** A bar sorted by a
measure re-sorts itself in every filter context, so the order on screen is
always the selected quarter's — and when one sector climbs, all the others
shift, which the eye reads as noise. A rank printed as a number can be carried
from one quarter to the next. It is not decoration: measured over the 29
quarters on condominium, **9 of the 18 sectors move by 5 places or more**,
sector 7 travels from 2nd to 11th, and 11 of 17 sectors sit at a different rank
in the last quarter than in the first.

⚠️ **The `FILTER` is not belt and braces — the first version of this measure
was wrong, and it was wrong on screen within minutes of being typed.** It read
`RANKX ( ALLSELECTED ( Sector[name] ), … )`, which ranks whatever the visual
leaves standing. Checked in a scratch table without the `is apciq_sector`
filter on 2026-08-31: **the island row joined the ranking at 9th place and
pushed every sector below it down one**, so Pointe Est de l'Île read 18 out of
an island that has eighteen sectors. Centre still read 1, which is why nothing
looked broken.

Restricting the ranking universe to `geography_type = "apciq_sector"` makes
the measure give the same rank in any visual, filtered or not. **A measure
whose correctness depends on a filter someone else remembers to set is not a
measure, it is a trap** — and this one was sprung by the very first table built
to test it.

`ALLSELECTED` rather than `ALL` is still what respects the two slicers: the
ranking is of the selected quarter and property type, not of the whole archive.

**A withheld sector is ranked last and shows nothing**, which costs no one a
place: `[Median price]` is blank there, DAX sorts a blank to the bottom in
`DESC`, and `NOT ISBLANK` keeps the number off the screen. Montréal-Nord is
the case to check — and it disappears from a table altogether unless
`Price status` is beside it, because Power BI drops a row whose measures are
all blank. That is the same reason the page's table carries `Price status` at
all: **the map, the bar and the table each go silent on a withheld sector, and
only one of them says why.**

**The `NOT ISBLANK` guard keeps unpriced sectors out of the ranking.** Without
it `RANKX` gives them the last place, which is a statement about the market;
what the data says is that APCIQ printed nothing. A blank rank beside
`Price status = withheld` says that, and the two are read together.

`DENSE` rather than `SKIP`: two sectors at the same median share a rank and the
next one follows immediately, so the column is always read as "of 18" rather
than jumping.

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
VAR Sectors = DISTINCTCOUNT ( fact_affordability[apciq_sector_number] )
VAR Meets = SELECTEDVALUE ( fact_affordability[meets_income_requirement] )
VAR HasPrice = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[median_price] ) )
VAR HasIncome = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[household_income] ) )
RETURN
    SWITCH (
        TRUE (),
        Sectors > 1, "Shared between two sectors",
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
row where the price and the income both exist yet the verdict is null. Leave it
visible: a branch that never fires is a control, and one that starts firing is
news.

⚠️ **The shared tract was anticipated here and the consequence was predicted
wrong, which the map found on 2026-08-30.** This paragraph used to say that
`4620511.02` would fall through to `Not evaluated` when its two sectors
disagree. It does not: `SELECTEDVALUE` returns blank for `median_price`, so
`NOT HasPrice` catches it first and prints **`No published price`** — for a
tract that has two. Measured over its 261 combinations, **174 disagree on the
price and 12 disagree on the verdict**, so the wrong branch was reachable in
twelve of them. The `Sectors > 1` branch added above fires before either and
names what is actually true. **A branch predicted to be unreachable is not a
control until something tries to reach it.**

```dax
Tract map colour =
VAR State = [Verdict]
VAR Ratio = [Price to income (median)]

VAR ScaleMax = 15
VAR Position = MIN ( 1, MAX ( 0, DIVIDE ( Ratio, ScaleMax ) ) )

VAR StartR = 222   VAR StartG = 235   VAR StartB = 247
VAR EndR   = 8     VAR EndG   = 48    VAR EndB   = 107

VAR R = INT ( StartR + ( EndR - StartR ) * Position )
VAR G = INT ( StartG + ( EndG - StartG ) * Position )
VAR B = INT ( StartB + ( EndB - StartB ) * Position )

VAR HexChars = "0123456789ABCDEF"
VAR Hex =
    "#"
        & MID ( HexChars, QUOTIENT ( R, 16 ) + 1, 1 ) & MID ( HexChars, MOD ( R, 16 ) + 1, 1 )
        & MID ( HexChars, QUOTIENT ( G, 16 ) + 1, 1 ) & MID ( HexChars, MOD ( G, 16 ) + 1, 1 )
        & MID ( HexChars, QUOTIENT ( B, 16 ) + 1, 1 ) & MID ( HexChars, MOD ( B, 16 ) + 1, 1 )

RETURN
    SWITCH (
        State,
        "No published price",         "#9E9E9E",
        "No published income",        "#EDE3D0",
        "Shared between two sectors", "#7FBF7F",
        "Not evaluated",              "#FF00FF",
        Hex
    )
```

**Leave the format string on *General*.** This measure returns a colour, not a
number, and any currency or decimal format would corrupt the string before
Power BI reads it. The magenta is deliberate: `Not evaluated` is the branch that
must never light up, and a colour that shouts is a control rather than a
palette choice.

```dax
Map coverage note =
VAR Coloured = CALCULATE ( DISTINCTCOUNT ( fact_affordability[ct_uid] ),
                           NOT ISBLANK ( fact_affordability[price_to_income_ratio] ) )
VAR NoPrice  = CALCULATE ( DISTINCTCOUNT ( fact_affordability[ct_uid] ),
                           ISBLANK ( fact_affordability[median_price] ) )
VAR NoIncome = CALCULATE ( DISTINCTCOUNT ( fact_affordability[ct_uid] ),
                           NOT ISBLANK ( fact_affordability[median_price] ),
                           ISBLANK ( fact_affordability[household_income] ) )
RETURN
    FORMAT ( Coloured, "#,0" ) & " tracts shaded, scale capped at 15x — "
        & FORMAT ( NoPrice, "#,0" )  & " with no published price, "
        & FORMAT ( NoIncome, "#,0" ) & " with no 2020 census income"
```

**It counts tracts, not rows, and that is the whole point.** A map draws one
shape per tract; the KPI row counts rows. The two differ by exactly the shared
tract, and stating the shape count under the map is what stops the two numbers
from being read as a contradiction.

### D. Rates — on `fact_interest_rate` and `interest_rate_series`

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
    interest_rate_series[rate_kind] = "contracted"
)
```

```dax
Posted rate (mean) =
CALCULATE (
    [Rate (mean of period)],
    interest_rate_series[rate_kind] = "posted"
)
```

The third value of `rate_kind` is `policy`, and no measure filters on it: the
policy rate belongs on the line chart through the legend, not in a KPI that
would invite subtracting it from a mortgage rate.

Both are written as `CALCULATE ( …, column = value )`, which **replaces** any
filter already on `rate_kind` rather than intersecting with it. That is
deliberate: click *posted* in the line chart legend and `Contract rate (mean)`
still returns the contracted mean, so the KPI keeps comparing the two things it
exists to compare. The consequence is the rule for the line chart — put
`Rate (mean of period)` on it and let the legend do the splitting. The two
kind-specific measures would draw the same two flat lines whatever is selected.

```dax
Posted minus contract (points) =
VAR Posted = [Posted rate (mean)]
VAR Contract = [Contract rate (mean)]
RETURN
    IF ( NOT ISBLANK ( Posted ) && NOT ISBLANK ( Contract ), Posted - Contract )
```

⚠️ **The guard is not defensive habit — without it this measure is wrong today,
on a period the model already holds.** `[Posted rate (mean)] - [Contract rate
(mean)]` written plainly returns **6.09** for 2026 Q3, where the posted series
has nine observations and the contracted one has none: DAX reads the blank as
zero in the subtraction and the card announces a six-point gap that nobody
measured. That is the **third** appearance of blank-as-zero in this report,
after `Sectors within reach of this income` on page 1 and the same mechanism on
page 3. Take it as settled: **in this model, any measure that subtracts or
compares two measures gets an explicit `ISBLANK` test.**

```dax
Rate observations =
COUNTROWS ( fact_interest_rate )
```

```dax
First rate observation =
MIN ( fact_interest_rate[observation_date] )
```

```dax
Last rate observation =
MAX ( fact_interest_rate[observation_date] )
```

The three carry `rate` in their names although the display folder already says
`Rates`, because unlike every other measure here they would return a plausible
number beside a market or affordability visual — `COUNTROWS` of a fact table has
no way of refusing. Long headers in the series table are the cost, and the file
has already ruled out *Rename for this visual* as a way to pay it.

They answer **within the current selection**, which is what a table under a year
slicer should do. `Rate freshness warning` below is the one that deliberately
does not, and the contrast is the point: one reports what you are looking at,
the other reports the state of the source whatever you are looking at.

```dax
Rate grain warning =
VAR SeriesInScope = DISTINCTCOUNT ( fact_interest_rate[series_id] )
VAR PerSeries =
    CONCATENATEX (
        interest_rate_series,
        interest_rate_series[series_label] & " — "
            & COALESCE ( CALCULATE ( COUNTROWS ( fact_interest_rate ) ), 0 ),
        "; ",
        interest_rate_series[sort_order], ASC
    )
RETURN
    IF (
        SeriesInScope > 1,
        "Averages over observations of unequal frequency. Observations behind each — "
            & PerSeries
            & ". The policy rate publishes every business day, both mortgage rates weekly."
    )
```

**The first version counted rows and series and reported neither per series**,
while section 2 of this file claimed it stated "the number of observations
behind each average". The sentence was right about what the page needs; the
measure did something else. Iterating `interest_rate_series` directly gives
the row context every column of the dimension, so `sort_order` is available to
order the sentence and `CALCULATE ( COUNTROWS ( … ) )` transitions that row into
a filter on the fact.

`COALESCE ( …, 0 )` is what makes it print `— 0` instead of dropping the series
from the sentence, and on 2026 Q3 that zero is the whole news. A count that
disappears when it reaches zero is the same failure as a bar that vanishes when
APCIQ withholds a median.

```dax
Rate freshness warning =
VAR NewestHeld =
    CALCULATE (
        MAX ( fact_interest_rate[observation_date] ),
        ALL ( fact_interest_rate ),
        ALL ( 'date' ),
        ALL ( interest_rate_series )
    )
VAR PerSeries =
    ADDCOLUMNS (
        ALL ( interest_rate_series ),
        "@Last", CALCULATE ( MAX ( fact_interest_rate[observation_date] ), ALL ( 'date' ) )
    )
VAR Stale = FILTER ( PerSeries, NewestHeld - [@Last] > 21 )
RETURN
    IF (
        COUNTROWS ( Stale ) > 0,
        "Published nothing for more than three weeks — "
            & CONCATENATEX (
                Stale,
                interest_rate_series[series_label] & ", last "
                    & IF ( ISBLANK ( [@Last] ), "never", FORMAT ( [@Last], "yyyy-mm-dd" ) ),
                "; ",
                interest_rate_series[sort_order], ASC
            )
            & ". The model holds observations to " & FORMAT ( NewestHeld, "yyyy-mm-dd" )
            & ". Any rate figure for a later period rests on the series that did publish."
    )
```

**Three weeks is a constant, and it is a measured one rather than a chosen one.**
Over their whole history both weekly series run at a gap of exactly seven days —
minimum 7, maximum 7, not one gap above 7, across 596 and 608 observations. The
incident this card was written for sits at **85 days**. Twelve times the largest
gap the source has ever produced separates the two populations, so **every
threshold from 8 to 84 days selects the same series**, and the day that gap
closes the constant deserves the argument it is not getting now. Same shape as
the 1.5 area ratio of J3.4, which sat in a fossé of three orders of magnitude.

It removes `date` on purpose, twice: once for the reference date and once
per series. A freshness card that a year slicer could silence is not a control.

`ISBLANK ( [@Last] )` covers a series present in the dimension with no
observation at all. It cannot happen while the dimension is built from what was
loaded — which is exactly why it stays: if it ever prints `last never`, the
model and the ingestion have come apart.

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

The page-4 rate lines, chosen on 2026-08-30 and **validated by script rather
than by eye** — `dataviz/scripts/validate_palette.js`, light mode, all pairs:

| Series | Colour |
|---|---|
| `contracted` | `#2A78D6` |
| `posted` | `#EB6834` |
| `policy` | `#4A3AA7` |
| sales (single series, its own chart) | `#8A9199` |

Blue and orange go on the two mortgage rates because **that** is the comparison
the page exists for, and they are the best-separated pair in the set. All three
pass the lightness band, the chroma floor, colour-blind separation and contrast
against a light surface.

⚠️ **The page-3 blue `#17527A` was tried here first and the validator refused
it** — too dark for the lightness band and too grey for the chroma floor. That
is not a contradiction between the two pages: on page 3 it belongs to a
single-hue scale running dark to light, which is a *sequential* job, and on page
4 it would have to establish identity against two other hues, which is a
*categorical* one. The same hex is right for one and wrong for the other.

The sales grey fails the chroma floor on purpose. That check says "this reads as
grey", which is exactly the brief: sales are alone in their chart with no
identity to defend, the only test that applies is contrast, and a saturated
colour there would compete with the rates.

**Colour follows the entity, never the visual.** The contracted rate is
`#2A78D6` on the eleven-year line and `#2A78D6` again on the quarterly one. A
reader who learns "blue is the negotiated rate" at the top of the page must find
it unchanged at the bottom.

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

**~~No map~~ — superseded on 2026-08-30. The census tract map is built and
accepted; it lives on page 2.** The reason first written here on 2026-08-27 was
wrong twice over, and the record is kept rather than deleted. It claimed
`Shape Map` needed a TopoJSON conversion and that the alternatives were a Bing
round-trip or a custom visual; it accepts **GeoJSON**, colours a shape file you
supply, and geocodes nothing. It was then labelled a preview feature on the
strength of a second Microsoft page — **confirmed in Power BI Desktop on
2026-08-30 that it carries no preview label**. Two documentation pages
disagreed, and the more recently revised one was the wrong one. **A
disagreement between two docs pages is settled in the product, not by the
revision date.**

**~~No map of the eighteen APCIQ sectors~~ — built on 2026-08-31.** They had
carried `geometry = NULL` since J3.1. They now carry the union of the census
tract polygons each of them draws, proved by an equality — sum of the parts =
area of the union = area of the 541 tracts = 499.627 km² — and held by a dbt
test. `docs/geography.md` section 5 has the construction and the majority rule
it needs; the cost of that rule is one tract whose 476 residents are counted in
one sector and drawn in another, 0.024 % of the island.

**The three maps do not say the same thing, and that is why there are three.**
Eighteen sectors shaded by median price is what a reader expects, and it is now
page 1. **541 tracts shaded by the price-to-income ratio shows what no other
report has**: the J4.1 finding that in seventeen of the eighteen sectors the
verdict changes from tract to tract at an identical price. Eighteen flat areas
cannot show that. And the sector map returns on page 3 carrying a verdict
rather than a price, which is the one thing `Income input` can change.

**The tract map of the required income was refused, and on a measurement.** It
would draw 541 shapes for **17 distinct values** — see page 3. That is the one
map this report deliberately does not do.

No map is one of the eleven criteria of section 44, though section 30 of the
brief asks for one. They were built because the geometry, the measures and the
join keys already existed or cost a single dbt model.

**No `housing_burden_ratio`.** It needs sixteen municipal tax rates that are not
identified and condo fees that only exist in listings. Out of scope for J4,
decided in advance.

**No five-variable FTB Score.** Section 25 of the brief describes one; it is
reduced here to the required income, which dominates it anyway. Building a
composite index on top of a figure already stated to be a lower bound would add
precision that is not there.

**No forecast, no coefficient, and no causal wording.** The rate line and the
sales columns of page 4 share a time axis because they moved in the same years,
and nothing more is claimed: every label there says *association*, never
*cause*. No correlation figure appears on the page either, and that is
arithmetic rather than modesty — 29 overlapping twelve-month windows are worth
about seven independent observations, both series carry a trend, and a pandemic
sits in the middle of the window having moved rates and housing demand at once.
The link the project can actually assert is the computed one:
`fact_mortgage_scenario` turns a rate into a required income by arithmetic. The
chart illustrates that mechanism on the real market; it is not asked to prove
it. The lag analysis of section 28 of the brief is real statistical work and
belongs to J5.

---

## 7. Why this file exists


---

# 8. J4.2¾ · 1 — The theoretical income

**Built on 2026-08-31.** Read this before touching page 2: five existing
measures now read a different column, and the reason is not cosmetic.

## 8.1 What happened, in one paragraph

Until now the report divided a 2026 price by a 2020 income and showed the
result as the state of the market. Three quarters of the fall it displayed was
not the market — it was the income standing still for six years. No source
publishes income below the metropolitan area after 2021 (the full Statistics
Canada catalogue was swept on 2026-08-31: 8 267 cubes, and the 27 carrying
"census tract" all end in 2021), so today's income cannot be **observed**. It
can only be **calculated**: the 2020 census income restated in dollars of the
quarter being displayed, using the Montréal CPI.

That figure is a **theoretical median income**. The word is not caution, it is
the description. It goes in the measure name, in the column header and on a
permanent card — not only in `methodology.md`, which nobody opens while
reading a chart.

## 8.2 The decision of 2026-08-31

**The theoretical income is what the page shows. The 2020 observation stays in
the model, in second position** — by decision. There is no toggle
slicer: the measures below read the indexed columns outright, and the
`(2020 dollars)` measure exists for whoever wants the comparison back on
screen.

⚠️ **A toggle was considered and rejected**, and the reason is worth keeping.
It would have rested on `SELECTEDVALUE ( Basis[Basis], "theoretical" )` — a
default that applies both when nothing is selected *and* when several things
are. That is the blank-versus-zero trap in its DAX form, and this project has
now met it five times. No toggle, no trap.

## 8.3 What the mart now carries

Six columns on `fact_affordability`, all derived, none observed:

| Column | What it is |
|---|---|
| `income_index_factor` | quarter CPI ÷ mean CPI of the twelve months of 2020 |
| `income_index_base_year` | 2020 — fixed by the census, not chosen |
| `income_index_basis` | `cpi_rmr462` or `not_indexed` |
| `income_not_indexed_reason` | in words, when there is no factor |
| `household_income_indexed` | the theoretical income. **Null when there is no factor — never the 2020 figure wearing a newer label** |
| `price_to_income_ratio_indexed`, `income_shortfall_indexed`, `meets_income_requirement_indexed` | the three derived measures against it |

**Why the verdict is computed in SQL and not in DAX.** On 2026-08-30 page 3
carried two definitions of one threshold — a map testing `required <= income`,
a table testing `income >= required * 1.10` — and they disagreed on 44 of 87
slices. Writing the indexed verdict in DAX would have set that up again, in a
language with no tests. One definition, in one place, with a positive control
that fires.

## 8.4 The three new measures

```dax
Household income (theoretical) =
VAR Tracts = DISTINCTCOUNT ( fact_affordability[ct_uid] )
RETURN
    IF ( Tracts = 1, MAX ( fact_affordability[household_income_indexed] ) )
```

**The `IF` is verrou n° 1 of J4, and it is the same guard as
`Household income (2020 census)`.** At one census tract there is one income;
above that, aggregating forty tract medians into a sector income is wrong
whether or not it is weighted. Indexing does not repair that — it multiplies
every tract by the same factor, so a median of medians stays a median of
medians. Blank above a single tract.

**Name the table column *Theoretical median income (2020 census, indexed)*.**
The parenthesis is the whole point: it names both what was observed and what
was done to it, in the one place a reader is looking when they read the number.

```dax
Income basis note =
VAR Basis = SELECTEDVALUE ( fact_affordability[income_index_basis] )
VAR Factor = SELECTEDVALUE ( fact_affordability[income_index_factor] )
VAR Reason = SELECTEDVALUE ( fact_affordability[income_not_indexed_reason] )
RETURN
    SWITCH (
        TRUE (),
        Basis = "not_indexed",
            "Income shown: 2020 census, NOT restated — " & Reason,
        NOT ISBLANK ( Factor ),
            "Theoretical income: the 2020 census median, restated in dollars of this "
                & "quarter by the Montréal CPI (× " & FORMAT ( Factor, "0.000" ) & "). "
                & "A calculated figure, not an observation.",
        "Theoretical income: the 2020 census median restated by the Montréal CPI. "
            & "Select one quarter to see the factor."
    )
```

⚠️ **This card is permanent, like `Down payment assumption`.** Three things
must be on screen at all times: the income is the 2020 census · it has been
restated into dollars of the displayed quarter · the instrument is the Montréal
CPI. A reader who takes the number for an observation has been misled by the
page, not by their own carelessness.

⚠️ **It must also handle the un-indexed case, and that case is not
hypothetical.** On 2026-08-31 the CPI reached 2026-07, so 2026 Q3 exists with
one month of three and has no factor. `fact_market` stops at 2026 Q2 today, but
the next APCIQ edition will land before the September CPI. When it does, this
card says so and `assert_every_priced_quarter_can_be_indexed` fails.

```dax
Share of tracts affordable (2020 dollars) =
VAR Evaluated =
    CALCULATE (
        DISTINCTCOUNT ( fact_affordability[ct_uid] ),
        NOT ISBLANK ( fact_affordability[meets_income_requirement] )
    )
VAR Affordable =
    CALCULATE (
        DISTINCTCOUNT ( fact_affordability[ct_uid] ),
        fact_affordability[meets_income_requirement] = TRUE ()
    )
RETURN
    IF ( NOT ISBLANK ( Evaluated ), DIVIDE ( Affordable + 0, Evaluated ) )
```

**This is the second-position measure, and it is not decoration.** Put it
beside `Share of tracts affordable` and the gap between the two *is* the result
of this session: 93.2 % → 35.0 % as displayed until now, 92.5 % → 78.1 %
restated. The 2022 Q2 break survives the restatement (−9.6 points instead of
−15.6): **the break is the market, the slope was the vintage.**

## 8.5 The five measures that now read indexed columns

Change the column, keep every guard. The blank-versus-zero protections in
`Tracts affordable` and `Tracts evaluated` are unchanged and still necessary.

| Measure | Was | Now |
|---|---|---|
| `Tracts evaluated` | `NOT ISBLANK ( meets_income_requirement )` | `NOT ISBLANK ( meets_income_requirement_indexed )` |
| `Tracts affordable` | `meets_income_requirement = TRUE ()` | `meets_income_requirement_indexed = TRUE ()` |
| `Price to income (median)` | `MEDIAN ( price_to_income_ratio )` | `MEDIAN ( price_to_income_ratio_indexed )` |
| `Income shortfall (mean)` | `AVERAGE ( income_shortfall )` | `AVERAGE ( income_shortfall_indexed )` |
| `Verdict` | reads `meets_income_requirement` | reads `meets_income_requirement_indexed` |

⚠️ **`Tracts evaluated` must move too, and it is the one that could quietly be
left behind.** It is the denominator of `Share of tracts affordable`. If it
kept counting rows evaluable against the 2020 income while the numerator
counted rows affordable against the theoretical one, the two would rest on
different tracts the day a quarter has no CPI factor — and the percentage would
still look perfectly reasonable. They are identical today because every quarter
of the archive is indexed. That is exactly why it would go unnoticed.

## 8.6 `Income vintage warning` — rewritten, not removed

The six-year gap is still true. It is now *corrected* rather than *suffered*,
so the sentence changes and the card stays.

```dax
Income vintage warning =
VAR Gap = SELECTEDVALUE ( fact_affordability[price_year_minus_income_year] )
VAR IncomeYear = SELECTEDVALUE ( fact_affordability[income_year] )
VAR Basis = SELECTEDVALUE ( fact_affordability[income_index_basis] )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Gap ), BLANK (),
        Basis = "not_indexed",
            "Income is the " & IncomeYear & " census and could NOT be restated for this quarter. "
                & "The price is " & Gap & " year(s) later.",
        Gap = 0,
            "Income is the " & IncomeYear & " census, restated to this quarter by the CPI.",
        "Income is the " & IncomeYear & " census, restated into dollars of this quarter "
            & "(" & Gap & " year(s) later) by the CPI. Prices and incomes are in the same "
            & "dollars; the 2020 distribution between tracts is unchanged."
    )
```

**The last clause is the limitation indexing does NOT remove**, and it belongs
on screen rather than only in `limitations.md`. The CPI moves the whole island
by one factor. If a tract has gentrified since 2020, nothing here can see it.
Measured cost: **4.2 % on the median tract**, against the 10.6 % that made J4.1
refuse a sector-grain income — two and a half times less damaging than an error
the project has already rejected.

## 8.7 Acceptance, and it is checkable

`scripts/report_oracle.py` prints these. Condominium, couple:

| Slice | `Share of tracts affordable` | `(2020 dollars)` |
|---|---|---|
| 2019 Q2 | **92.5 %** | 93.2 % |
| 2022 Q2 | **71.1 %** | 54.7 % |
| 2023 Q4 | **56.3 %** | 29.7 % |
| 2026 Q2 | **78.1 %** | 35.0 % |

⚠️ **Count distinct tracts, not rows.** The shared tract `4620511.02` is one
tract and two rows, so a row count returns 513 where a tract count returns 512.
Both are right about different questions — the same trap as *512 shapes ≠ 513
rows* on the page 2 map.

⚠️ **2023 Q4 is exactly 288 / 512 = 56.25 %, a value sitting precisely on the
rounding boundary.** PostgreSQL rounds it half-up to 56.3, Python rounds it
half-to-even to 56.2, and the feasibility study printed 56.2 for that reason.
Neither is wrong and neither is a discrepancy in the data. Take the oracle's
figure at acceptance, so the report and its check do not disagree over a
half-unit — the same class of false disagreement as `rank()` versus
`RANKX ( .., DENSE )` on page 1.

**The factor to check the card against:** 2026 Q2 is **× 1.2616**, and the base
is the mean of the twelve 2020 months. 2019 Q2 is **× 0.9901** — below one,
because the index deflates towards the past. A card showing 1.000 everywhere
means the measure lost its filter context.

---

# 9. J4.2¾ · 2 — The place filter

**Specified on 2026-08-31.** One slicer, and it changes what three pages mean.
Read 9.1 before anything else: it corrects a figure the feasibility study got
the wrong way round, and the correction is the reason the slicer is shaped the
way it is.

## 9.1 The measurement that shaped this: 26 places of 34 show more than was asked

The study measured that **32 of the 34 administrative entities resolve to
exactly one APCIQ sector**, and concluded that only Verdun and
Côte-des-Neiges–NDG were a problem. That figure is right and the conclusion
does not follow, because it measures the wrong direction. What a reader
experiences is **sector → places**, not place → sector.

Measured on 2026-08-31 over `bridge_apciq_sector_geography`:

| What the reader gets beyond the place they picked | Places |
|---|---|
| exactly what was asked | **8 of 34** |
| one extra place | 10 |
| two extra | 1 |
| three extra | 8 |
| **six extra** | **7** |

Choosing Beaconsfield shows the figures of seven municipalities. Choosing
Westmount shows Hampstead, Mont-Royal and Outremont with it. The eight clean
places are the ones whose sector contains nothing else: Saint-Laurent,
Ahuntsic-Cartierville, Ville-Marie, Le Plateau-Mont-Royal, Rosemont,
Villeray, Mercier–Hochelaga-Maisonneuve, Montréal-Nord.

**This is not a defect of the bridge.** APCIQ does not publish below the
sector, and `docs/geography.md` has said since J3.1 that an APCIQ sector name
is not a geography. What changes is the status of the disclosure: it is not a
special case for two places, it is a **permanent statement for twenty-six**.

## 9.2 The `Place` table, and why it is the bridge itself

Import `marts.bridge_apciq_sector_geography` and **name it `Place`**. No new
dbt model: the bridge already carries both levels of the hierarchy and the
`coverage` column that flags a split place.

| | |
|---|---|
| Rows | **36** — 34 places, two of them appearing twice |
| Columns used | `apciq_sector_name`, `admin_name`, `apciq_geography_key`, `apciq_sector_number`, `coverage`, `admin_geography_type` |

**Relationship:** `Place[apciq_geography_key]` → `Sector[geography_key]`,
many-to-one, **cross-filter direction Both**.

⚠️ **Bidirectional, deliberately, and it is safe here — but check before
copying the pattern.** The slicer sits on `Place` and has to filter the facts,
which hang off `Sector`; a single-direction many-to-one relationship filters
the other way and the slicer would do nothing. Bidirectional is normally worth
avoiding because it creates ambiguous paths, and here there are none: `Place`
touches only `Sector`, and `Sector` touches only the four fact tables. No loop
exists, so no ambiguity can.

**Verdun appears twice in the hierarchy, under `Le Sud-Ouest` and under
`L'Île-des-Sœurs`, and that is correct rather than a duplicate to clean up.**
It is the one honest way a slicer can say that a borough sits in two published
sectors. The same holds for Côte-des-Neiges–NDG under `NDG/Montréal-Ouest` and
`CDN/CSL`.

## 9.3 The slicer

A **hierarchy slicer**, two levels: `Place[apciq_sector_name]` then
`Place[admin_name]`. Chosen on 2026-08-31, against a flat list
of 34 names.

**The reason is 9.1.** A flat list hides the grouping until after the click; a
hierarchy shows it before. Someone opening *Ouest-de-l'Île-Sud* sees its seven
municipalities and understands, without reading anything, that picking one of
them means picking the group. The disclosure card then confirms it rather than
being the first news.

- **Synchronise it across pages 1, 2 and 3. Never page 4.**
  `marts.fact_interest_rate` has seven columns and not one of them is
  geographic — the Bank of Canada publishes for Canada, and there is no
  Montréal rate. A synchronised slicer there would be an inert control, which
  is worse than no control.
- **Multi-select stays allowed**, as on the property-type slicer of page 1.
  `Median price` already blanks with its sentence when more than one published
  cell survives, so nothing new is needed to make multi-selection honest.
- Set *Select all* off. It reads as a state, and "all places" is not the same
  question as "the island" — see 9.5.

## 9.4 `Selected area disclosure` — the card that names what is on screen

```dax
Selected area disclosure =
VAR Chosen = VALUES ( Place[admin_name] )
VAR ChosenCount = COUNTROWS ( Chosen )
VAR SectorsReached = CALCULATETABLE ( VALUES ( Place[apciq_sector_name] ) )
VAR AllPlacesShown =
    CALCULATETABLE (
        VALUES ( Place[admin_name] ),
        REMOVEFILTERS ( Place ),
        TREATAS ( SectorsReached, Place[apciq_sector_name] )
    )
VAR Extra = EXCEPT ( AllPlacesShown, Chosen )
VAR ExtraCount = COUNTROWS ( Extra )
RETURN
    SWITCH (
        TRUE (),
        NOT ISFILTERED ( Place[admin_name] ) && NOT ISFILTERED ( Place[apciq_sector_name] ),
            "Island of Montréal — all 18 APCIQ sectors.",
        ISBLANK ( ExtraCount ),
            "Showing " & CONCATENATEX ( Chosen, Place[admin_name], ", " )
                & ". APCIQ publishes this area on its own.",
        "Showing " & CONCATENATEX ( Chosen, Place[admin_name], ", " )
            & " — but APCIQ publishes it inside "
            & CONCATENATEX ( SectorsReached, Place[apciq_sector_name], " and " )
            & ", so the figures also cover " & ExtraCount & " other place(s): "
            & CONCATENATEX ( Extra, Place[admin_name], ", " ) & "."
    )
```

⚠️ **This card is permanent and it is not a warning, it is a caption.** It
fires on 26 of the 34 places, which is most of the time — a message that
appears that often has to read as an ordinary description of the view, not as
an error. Word it as *what you are seeing*, never as *careful*.

**Put it under the slicer, on all three pages.** It is the only thing standing
between "I clicked Verdun" and "this is the price of Verdun", and that reading
is the one the licence-free part of this project can least afford to leave
uncorrected.

## 9.5 Page 1 — the KPI row becomes contextual

Today `Sales (island, as published)` and `Active listings (island)` filter on
`fact_market[is_island_aggregate] = TRUE ()`. With a place selected, the
intersection of "this sector" and "the island aggregate" is empty by
construction, and **the two cards go blank while `Median price` and
`Days on market` keep working** — a row that answers half.

The filter becomes a switch:

```dax
Sales (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE (
            SUM ( fact_market[sales_count] ),
            fact_market[is_island_aggregate] = FALSE ()
        ),
        CALCULATE (
            SUM ( fact_market[sales_count] ),
            fact_market[is_island_aggregate] = TRUE ()
        )
    )
```

`Active listings (selected area)` is the same shape on
`fact_market[active_listings]`.

⚠️ **Both branches of `ISFILTERED` are needed, and testing only `admin_name`
is the mistake waiting to happen.** The slicer is a hierarchy: selecting at the
top level filters `apciq_sector_name` and leaves `admin_name` untouched. A
measure testing one column would fall back to the island aggregate while the
visual clearly shows one sector selected — the figures would be the island's,
under a title naming a sector.

⚠️ **Never drop the filter instead of switching it.** Without any geographic
filter the 19 rows add up: measured, sales come to **exactly ×2.0000** the
island row, listings between ×1.4747 and ×2.0431. The exact doubling on sales
is the J3.2 reconciliation seen from the other end — the 18 sectors tile the
island — and it is the reason the switch is exclusive by construction: either
the aggregate row, or the sector rows, never their union.

**`Active listings` does not reconcile exactly, and the measure should say
so.** APCIQ defines an active listing as *the mean of the monthly figures*, and
eighteen rounded means do not sum to the nineteenth rounded mean: **±0.18 % at
worst** on the clean slices, 25 of them exact. That is rounding, not a defect,
and not nothing.

```dax
Area title =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
VAR Places = COUNTROWS ( VALUES ( Place[admin_name] ) )
RETURN
    SWITCH (
        TRUE (),
        NOT PlaceChosen, "Island of Montréal",
        Places = 1, VALUES ( Place[admin_name] ),
        Places & " places selected"
    )
```

**A card that changes its perimeter without saying so is the trap this repo has
refused since J3.1.** The title must read the *same* filter state as the value
measures, never its own — the fault `Sector price colour` already avoided by
reading `Price relative to the island` instead of recomputing the comparison.

⚠️ **Promote `Price status` into the KPI row.** 430 of the 1 566 sector cells
have no published price — 27.5 % overall, **48.1 % on plex**, 30.1 % on
single-family, 4.2 % on condo — and those cells still carry sales and listings,
430 of 430. A half-filled row is therefore the normal state, not a symptom, and
only `Price status` distinguishes *APCIQ published nothing here* from *the
filter is broken*.

**The price line stays on the island, and that is measured rather than
preferred.** If it followed the selection: on plex only 6 of 18 sectors have
all 29 quarters and **5 have no series at all**, so the line would vanish
entirely. Keeping it on the island also preserves its job — the depth behind
the selected quarter. Both titles must say which geography they are on.

**The interaction matrix of page 1 has to be redone.** The page had two mutually
exclusive halves — `is island` for the cards and the line, `is apciq_sector` for
the histogram and the table — and the slicer crosses that boundary where an
interaction did not. Rebuild it against the acceptance cases in 9.7 rather than
from the old matrix.

## 9.6 Page 3 — three cards must stop following the place

⚠️ **This is the one thing a slicer breaks that an interaction did not, and no
interaction setting repairs it.** `report-design.md` documents that clicking a
bar is unhooked from the three KPI cards, because selecting one sector turns
"6 of 17" into "0 of 1", which reads as *no sector is within reach*. **A slicer
is not an interaction: it cannot be unhooked.**

So the three existing cards keep the island denominator:

```dax
Sectors within reach of this income =
VAR Income = 'Income input'[Income input Value]
VAR Reached =
    CALCULATE (
        COUNTROWS (
            FILTER (
                VALUES ( fact_affordability[apciq_sector_number] ),
                VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
                RETURN NOT ISBLANK ( Required ) && Required * 1.10 <= Income
            )
        ),
        REMOVEFILTERS ( Place ),
        REMOVEFILTERS ( Sector )
    )
RETURN IF ( ISBLANK ( Reached ), 0, Reached )
```

`Sectors borderline` and `Sectors priced` take the same two `REMOVEFILTERS`.

⚠️ **`REMOVEFILTERS ( Sector )` alone is not enough, and this is the subtle
part.** The slicer's filter lands on `Place`, and the bidirectional
relationship propagates it to `Sector`. Removing it from `Sector` only lets it
arrive again from `Place`. **Both tables, always.**

Then a fourth card answers the question the slicer was added for:

```dax
Verdict for the selected place =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        NOT PlaceChosen,
        "Select a place to see whether it is within reach",
        [Verdict for this income]
    )
```

It deliberately reuses `[Verdict for this income]` rather than repeating the
comparison — the same discipline that keeps `Sector bar colour` from applying a
different threshold than the table beside it. The 10 % band stays written in
exactly two measures.

**The page then answers both questions at once**: *where can I buy on the
island*, from the three island-wide cards, and *and the one I love, is it in
reach*, from the fourth. That second question is the "choix de cœur" the slicer
was requested for.

## 9.7 Acceptance

**The control that proves nothing moved:** with no place selected, all three
pages must read exactly what they read today. That is a before-and-after
comparison against `report_oracle.py`, not a visual inspection.

| Case | What must happen |
|---|---|
| **No selection** | page 1 KPI row identical to today; `Area title` reads *Island of Montréal*; page 3 cards read 6 / 1 / 10 / 18 at 95 000 $ |
| **Rosemont** (clean place) | disclosure says *APCIQ publishes this area on its own*; no extra places named |
| **Westmount** | disclosure names **Centre** and the three other places; page 1 figures are the sector's |
| **Beaconsfield** | disclosure names **six** other municipalities — the worst case |
| **Verdun** | disclosure names sectors **Le Sud-Ouest and L'Île-des-Sœurs**, and Le Sud-Ouest as an extra place |
| **plex, any quarter** | **16 of the 34 places have no published price on the entire archive.** The row must read `--` with `Price status`, never `0` |
| **page 4** | the slicer is absent, and the page is unchanged |

⚠️ **The plex figure is 16, not the 17 the study printed.** The study counted
over the 36 bridge rows; the slicer selects a **place**, and a place reaches all
of its sectors. Verdun's `L'Île-des-Sœurs` row has no plex price in any quarter,
but its `Le Sud-Ouest` row has all 29 — so choosing Verdun does not produce an
empty screen. Both figures are right about different questions, and **16 is the
one this page is accepted against**. Same class of distinction as *512 shapes ≠
513 rows* on the page 2 map.
