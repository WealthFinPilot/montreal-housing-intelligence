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

⚠️ **The same hex used to mean something different on page 3, and that was
deliberate** — `#17527A` was *within reach* there and is *dearer than the
island* here. **Page 3 stopped using it on 2026-09-12**, so the overlap is gone
and this page keeps the hex alone. What the reader learns is not a meaning per
colour but a direction — **darker is more of the thing being measured** — and
that is still what both pages say, now through different blues. Which is
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
neutral grey `#C7CCD1` — and check it on the acceptance slice below, where more
than half the island is grey. ⚠️ **It was chosen because page 3 used it for
*Out of reach*; page 3 stopped on 2026-09-12, and the choice stands on its own
here.** It is the only grey on this page, which is precisely the condition under
which the validator accepts it — beside a second grey it fails, at 7.0.

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
| Line | `Share of tracts affordable` by `'date'[quarter_label]` — **the finding**. `Share of tracts affordable (2020 dollars)` sits beside it as a **thin dotted grey second plane**: same axis, no markers, no labels — see 8.6 bis |
| Bar | `Share of tracts affordable` by `Sector[name]`, **one series**. `(2020 dollars)` and `Tracts evaluated` go in **Tooltips** |
| ~~Table~~ | **Removed 2026-09-02** — see below |
| **Shape map** | `Census_Tract[geography_code]` in **Location**, colour by `Tract map colour` — see below. Tooltips carry the detail the table used to |
| Card | `Income vintage warning` |
| Card | `Grain warning` |
| Card | `Map coverage note` |
| Card | `Down payment note` |

`Grain warning` prints only when a census tract is filtering, which is exactly
when a market measure on the same page would be repeating a sector total once
per tract. Put it in the title of any visual that mixes the two grains.

#### The tract table was removed, and its detail moved into the map tooltip

**Decided on 2026-09-02.** A 541-row table nobody scrolls, on a
page whose three charts already say the same thing; and a reader looking for
their own neighbourhood hovers the map rather than reading a list.

What the tooltip carries, in this order — it reads as a sentence: *where I am ·
what the neighbourhood earns · what it takes · the ratio · the verdict.*

```
Census_Tract[admin_place_name]         a COLUMN, not a measure -- see below
Household income (theoretical)
Income required, lower bound (mean)
Price to income (median)
Verdict
```

⚠️ **Two things the removal costs, named rather than discovered later.**
`Income shortfall (mean)` leaves the page — it is the subtraction of the two
lines above it, and the measure stays in the model for page 3. And **the 2020
income is no longer readable at tract grain anywhere**: it survives at island
grain on the line chart's second plane and in the vintage bookmark view. That
is consistent with the decision — theoretical is what the page displays,
2020 is a reference and not a competing reading — but it is a door closing.

#### ⚠️ `Min(Sector[name])` in that tooltip was wrong on all 541 shapes

Found on 2026-09-02: it printed **Ahuntsic-Cartierville** everywhere — the
alphabetical minimum of the eighteen sectors.

The map groups by `Census_Tract[geography_code]`. That filter reaches
`fact_affordability` and **stops**: a many-to-one relationship propagates from
the "one" side to the "many" side, so `Sector` is never filtered and `Min` sees
all eighteen rows. It raised nothing — J4.2's central finding in its purest
form, *a missing relationship does not fail, it answers*. The page 1 map does
not have it, because `Place_map` → `Sector` is bidirectional; that is exactly
what the bidirectional relationship buys there.

**The fix is a column, not a measure.** `dim_geography` carries
`admin_place_name` at census-tract level since 2026-09-02
(`docs/geography.md` 7.4), so it sits in `Census_Tract` — the very table the
map groups by. Same row context as the shape: no relationship to propagate, no
DAX, and nothing that can regress when someone edits the model. Set its
aggregation to **First**.

A measure reading `fact_affordability[apciq_sector_number]` and looking the
name up was written and **discarded**: it would have named an APCIQ sector,
and an APCIQ sector is not a place people know.

**Acceptance — hover three shapes, and they must differ:**

| Tract | Must read |
|---|---|
| `CT 0001.00` | Mercier–Hochelaga-Maisonneuve |
| `CT 0250.00` | Villeray–Saint-Michel–Parc-Extension |
| `CT 0511.02` | **Pierrefonds-Roxboro**, and `Verdict` says *Shared between two sectors* |

Three identical names means the old tooltip is still in place.

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
| `Share of tracts affordable` | 35.0 % — 179 / 512, in 2020 dollars. Since 2026-08-31 the measure reads the restated income: **400 / 512 = 78.1 %** |
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
2026-08-30, where the single-family maximum is **2.4 times its own 99th
percentile**. (The ratios themselves are not written here: a price-to-income
ratio in level is invertible into an APCIQ price. A ratio of two ratios is not.) A scale stretched to that outlier would flatten everything else.

**`Verdict` gained a branch because of this map.** The table on this page
carries `Sector[name]` *and* `Census_Tract[name]`, so every row is unique. **The
map carries only the tract**, so `4620511.02` — the one genuinely shared tract
of the island, J3.4 — arrives with both its rows in context and `SELECTEDVALUE`
returns blank. Measured over its 261 combinations: **174 disagree on the price
and 12 disagree on the verdict**, and in those 12 the original measure would
have printed *No published price* for a tract that has two. The `Sectors > 1`
branch fires first and names the real situation. It cannot regress the table,
where a sector is always filtering and the count is always one.

#### 2026-09-02 — the map now colours the SHORTFALL, not the ratio

> ⚠️ **Everything above about the 0–15× scale and the two greys is superseded.**
> It is kept because the reasoning still explains why `Color saturation` is
> unusable here and why the colour has to come from a measure.

**The condominium map read as uniformly pale, which raised the question of
whether the ratio was the right basis. Two faults, and the second is the interesting one.**

**Fault 1 — the scale was calibrated on a measure that changed definition.**
The 15× ceiling was fixed on 2026-08-30 against `price_to_income_ratio`. On
2026-08-31 `Price to income (median)` was repointed at
`price_to_income_ratio_indexed` (8.5). Every ratio was divided by ~1.26 and the
ceiling did not follow. Nothing failed.

**Fault 2 — one fixed scale cannot serve nine distributions.** The median ratio
spans **a factor of 4.4** across type × profile. On the 0–15
scale, condominium · couple lives at **29 %** of the palette — everything pale —
while plex · one person sits at **126 %**, everything saturated. At both ends the
map stops distinguishing anything. This is the same finding the sector map
reached on 2026-08-31 — a fixed scale shared by three types is illegible —
arrived at one day after this page had decided otherwise.

**THE MEASUREMENT THAT DECIDED THE BASIS, AND IT IS THE RESULT OF THE SESSION.**
A price-to-income ratio contains **no interest rate**. It is a division. So it
could not see what dominated the period:

| Condo · couple | Qualifying rate | Median ratio | Share within reach |
|---|---|---|---|
| 2021 Q4 | 5.25 % | *(baseline)* | **82.8 %** |
| 2022 Q4 | 7.04 % | −4.8 % | 66.4 % |
| **2023 Q4** | **7.59 %** | **−4.5 %** | **56.3 %** |

*(The ratio is shown as a change, never as a level: a level multiplied by the
published StatCan income gives back the APCIQ median price.)*

*(Remeasured 2026-09-14. The share column read 66.5 % and 56.1 % until then:
fact rows, not distinct tracts, which is not what `Share of tracts affordable`
counts. 2023 Q4 is 288 / 512 = 56.25 % exactly, on the rounding boundary —
take the oracle's figure at acceptance.)*

**From 2021 Q4 to 2023 Q4 the median ratio FELL 4.5 % while the share within
reach lost 26.5 points.** A reader watching only the ratio would conclude
housing had become slightly more affordable. The median couple cushion went from
lost **78 % of its margin** in eight quarters. The shortfall passes through
`income_required_lower_bound`, which depends on the qualifying rate, the
amortisation, the down-payment bracket and the insurance premium. It sees the
2.34 points. The ratio structurally cannot.

Two lesser reasons, both real: the ratio is a **hyperbola in income**, so it
compresses differences wherever income is high, while the shortfall is
**linear** — every dollar counts the same, which is the household reality. And
the shortfall **carries its own threshold in its sign**, where the ratio
threshold is not even constant: it moves by about a fifth across the archive,
and the rate is what moves it.

**⚠️ WHAT THE CHANGE COSTS, AND IT MUST BE WRITTEN.** The ratio is a derived
figure built on two observations, comparable across cities and decades. The
shortfall is **a quantified assumption**: a rate, a 25-year amortisation, the
minimum down payment, a 39 % GDS. And `income_required_lower_bound` is a
FLOOR — no property tax, no heating, no condo fees. **The map is therefore both
more telling and more optimistic than reality.** Section 41.2 of the brief, in
one visual.

#### The palette, and why it has six colours and three states

Designed against `scripts/validate_palette.js`, not by eye. **Diverging at
zero**, blue = surplus, red = shortfall, bounds fixed at −60 000 $ / +150 000 $
— clipping 1.31 % low and 3.05 % high over 103 854 rows, the same order as the
2.09 % accepted on 2026-08-30.

| State | Colour |
|---|---|
| within reach, from the threshold outwards | `#3987e5` → `#1c5cab` → `#0d366b` |
| out of reach, from the threshold outwards | `#e85f57` → `#c0392b` → `#6b0f0e` |
| out of the current selection | `#EDEDED` |
| no published price **or** no 2020 income | `#9E9E9E` |
| shared between two sectors | `#6B3FA0` |
| never | `#FF00FF` |

> ### ⚠️ THE FIXED BOUNDS ARE MISCALIBRATED FOR THE QUARTER ON SCREEN — measured
> ### 2026-09-12, and DELIBERATELY NOT FIXED
>
> **Left as it is, deliberately:** further tuning of the scale was judged not
> worth its cost. The finding is recorded so nobody has
> to measure it again; **it is not a to-do.**
>
> The clipping figure above — 1.31 % low, 3.05 % high — is true over the
> **103 854 rows of the whole archive**. The map shows **one slice at a time**,
> and on 2026 Q2:
>
> | | share of shapes |
> |---|---|
> | outer third of the blue arm | 3.9 % |
> | outer third of the red arm | **55.5 %** |
> | **clipped at the red end** — all one colour | **27.2 %** |
>
> On plex for one person that is **313 shapes out of 317**: the map is a single
> tone. Expressed as multiples of the current high bound, the slices run from a
> maximum of **0.35** (condominium, couple — it never uses two thirds of the red
> arm) to **1.78** (single-family, one person). A factor of five, on one fixed
> scale. On the blue side the spread is worse: condominium · couple reaches
> **7.17 times** its own bound, and two slices have **no blue shape at all**.
>
> ⚠️ **This is the same fact the map of page 1 measured on 2026-08-31** — "a
> fixed colour scale common to the three types is unreadable, the condominium
> occupies 26 % of the palette against 89 % for the single-family" — which is
> why card 1 went to an automatic scale. **Page 2 reproduced the trap twelve days
> later on a different quantity.** A scale calibrated on the whole population
> says nothing about the slice a reader opens; that is the lesson of probe 3 in
> J4.1, in a third form.
>
> **If it is ever reopened, the measurement already rules one option out.** A
> symmetric automatic scale — the obvious fix, since it keeps zero at the centre
> — starves the weaker arm to **12–16 % of the palette on four slices out of
> nine**. The two live options are an automatic scale **per arm** (what card 1
> does, at the price of comparing quarters) or an **asymptotic compression** of
> the position, which clips nothing and keeps one scale.

**No white at the centre, and that was measured.** A light grey midpoint sits at
**ΔE 4.1** from the beige that used to mean "no census income" —
indistinguishable even with full colour vision, where the floor is 15. So the
ramp breaks straight from blue to red at the threshold. It reads better anyway:
crossing the affordability threshold is an event, not a shade, and a hue break
is easier to see on shapes as small as a tract than a pass through white.

**⚠️ Both arms start at the same luminance — 0.49 and 0.48 — and the first
version did not.** It ran blue from `#9ec5f4` (luminance 0.73, very pale) while
red started at `#e34948` (0.41, saturated): at equal distance from the
threshold, red shouted and blue whispered. A tract clearing narrowly was nearly
invisible while one missing just as narrowly was vivid. **The map read
as "all red", and rightly** — the palette was exaggerating one side.

**⚠️ THE TWO SOURCE ABSENCES ARE NOW ONE GREY, reversing 2026-08-30.** Four hues
were tried for "no 2020 income" and every one collided: the original beige
against the pale grey of "out of selection" (ΔE **3.0**), a darker beige against
the mid grey (7.2), brown or olive against the red arm under protanopia
(3.8–5.0), a very dark grey against the dark blue (10.3). **A divergent ramp
with two arms, plus a selection state, consumes the space a one-armed sequential
ramp left free.** The earlier decision was right for the map it was made for.

What replaces the lost distinction: `Verdict` names it in the tooltip, and
`Map coverage note` prints **both counts** under the map. The information moved;
it was not dropped. That sentence in the note is load-bearing.

#### The cross-check the ratio never allowed

**The share of blue shapes must equal the KPI card above the map.**

```
Share of tracts affordable  =  78.1 %          (condo · couple · 2026 Q2)
blue shapes                 =  401 / 513  =  78.2 %
```

Colour and KPI now answer the *same* question, so they must agree, and a
disagreement is visible without opening a measure. Verified in the marts:
`meets_income_requirement_indexed` and `income_shortfall_indexed < 0` disagree on
**0 of 103 854 rows** — one threshold, one definition.

It also replaces the missing legend: a reader does not need to know what a shade
is worth to read *blue = within reach*, and the KPI above gives the exact
proportion.

⚠️ **If `Income shortfall (mean)` were left on the un-indexed column, 222 of 513
shapes would change side** on condo · couple · 2026 Q2, and the median tract
would flip sign — from a surplus to a shortfall. The cross-check catches that too.

#### Acceptance cases for the shortfall map

| View | What must appear |
|---|---|
| condo · couple · 2026 Q2 | ~**401 blue** of 513 shaded; the KPI above reads 78.1 % |
| plex · couple · 2026 Q2 | **3 blue only**, of 317 shaded |
| **plex · one person** | **no blue at all**, every quarter — 0.0 % within reach |
| a sector selected | every unselected tract `#EDEDED`, never violet, never mid grey |

The plex · one person case is the acceptance case, as the 216 grey shapes were
for the old map: an entirely red map is the **message** — a single person buying
a plex reaches no tract of the island — not a scale fault. Check that the reds
still vary inside it; if they are uniformly dark, the 150 000 $ ceiling is too
low.

#### The figures the map has to reproduce

Measured 2026-08-30, quarter **2026 Q2**. The three colour classes must add up
to 541 — the shape count of the file — which is the cheapest check that no
tract is drawn twice or lost:

| Type / profile | Shaded | Grey, no price | Beige, no income | Affordable |
|---|---|---|---|---|
| **Condominium / Couple** | **512** | **18** | **11** | 179 |
| Condominium / One person | 512 | 18 | 11 | 1 |
| **Plex / Couple** | 317 | **216** | 8 | 0 |
| Single-family / Couple | 395 | 138 | 8 | 2 |

**The median ratio of each slice is deliberately not tabulated here** -- it is
a price-to-income ratio in level, and multiplying it by a published census
income gives the APCIQ price back. Run `report_oracle.py` for the four values.

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
| ~~Card~~ | ~~`Slice warning`~~ — **removed 2026-09-12, see below** |
| ~~Card~~ | ~~`Grain warning`~~ — **removed 2026-09-12, see below** |

> ### ⚠️ BOTH GUARD CARDS WERE REMOVED FROM THIS PAGE ON 2026-09-12
>
> **Removed because they read as two blocks that never say anything**, and
> that reading was right about what was on screen: these were **the only two cards in the
> whole report with no visual-level formatting at all**, so they took the
> theme's card background and drew an empty tile even while blank.
>
> **`Grain warning` was genuinely dead here, and that is measured.** It prints
> only when `Census_Tract` is filtering, and **no visual on page 3 touches
> `Census_Tract`** — checked field by field. Nothing short of adding a
> tract-grained visual could have woken it. It stays on page 2, where clicking a
> shape of the map does filter `Census_Tract` and the warning is the point.
>
> ⚠️ **`Slice warning` was not dead, and removing it has a cost that is written
> here because nothing on screen carries it any more.** It was silent only
> because both slicers are `strictSingleSelect` — *a slicer setting is one click
> from being changed*, which is a sentence this project has had to learn twice.
> What happens then is measured, and it is in the paragraphs below: releasing
> the property-type filter raises the mean required income by **49 %** and takes
> the sectors within reach from **7 to 2**; releasing the quarter filter takes
> them from **7 to 14**. `Sectors priced` climbs from 17 to 18. **Every one of
> those pages looks right.** No blank, no error, no empty visual — an average
> answers, and the answer is a mixture.
>
> **Where the cost is paid:** `docs/limitations.md`, J4.4 — one entry saying
> that every figure on this page assumes a single property type and a single
> quarter, and that nothing in the report enforces it beyond a slicer setting.
> **That entry is load bearing**, like the freshness one the Rates page left
> behind on the same day.
>
> **The measure `Slice warning` is now used by no visual.** Keep it or delete
> it — but if it is deleted, the reasoning below is the only place the 49 %
> lives, so it must reach `limitations.md` first. `Grain warning` stays in use
> on page 2 and is not affected.
>
> **A third route was offered and declined**, and it is recorded because it
> costs nothing to take later: turning the card's background off makes a
> conditional text card **invisible while empty** and visible the day it has
> something to say — which is exactly how the three notes of page 2 already
> behave.

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

⚠️ **SUPERSEDED ON 2026-09-09 — this map now draws the 36 places. See section
13.12.** What follows is kept because its refusal of a *census tract* map still
holds. What expired is the second argument: the sector file was free because
page 1 used it, and page 1 moved to the 36 land-clipped places on 2026-09-01,
leaving this map alone with an outline nothing else in the report shares.

So the map here was the **eighteen sectors, coloured by the verdict**: 18 shapes
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
| `#9BD0F2` | Cash purchase | — |
| `#4E9FD8` | Within reach | **6** |
| `#2A6CA3` | Borderline | **1** |
| `#FF8A7E` | Out of reach | **10** |
| `#A8722E` | Below the legal minimum | — |
| `#E8EAEC` | No published price | **1** (sector 17, Montréal-Nord) |
| | **Total** | **18** |

⚠️ **The counts are the 2026-08-30 ones, at the income of brief section 31 and
before the slider existed**; the colours are the 2026-09-12 ones. Two classes
carry a dash because they cannot occur at that setting. **What the case checks
is the total of 18, not the split** — and since 2026-09-09 there are six classes
to add up, not four. `report_oracle.py` prints the split for whatever slider
position is set.

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
| ~~Card~~ | ~~`Rate freshness warning`~~ — **removed 2026-09-12, see banner below** |
| Line | `Rate (mean of period)` by `'date'[date_key]`, **continuous** axis, legend `interest_rate_series[rate_kind]` |
| Combo (line and stacked column) | columns `Sales (island, 12 months)`, line `Contract rate (mean)`, by `'date'[quarter_label]` — **both Y-axis ranges pinned by hand** |
| Card | `Trailing window` |
| ~~Card~~ | ~~`Rate grain warning`~~ — **removed 2026-09-12, see banner below** |
| Table — series | `series_label`, `rate_kind`, `frequency`, `Rate observations`, `First rate observation`, `Last rate observation`, `what_it_is` |
| Table — quarters | `'date'[quarter_label]`, `Posted rate (mean)`, `Contract rate (mean)`, `Posted minus contract (points)`, `Rate observations` |
| Text box | the association caveat — see below |

> ## ⚠️ THE TWO WARNING CARDS WERE REMOVED FROM THIS PAGE — 2026-09-12
>
> `Rate freshness warning` and `Rate grain warning` were in
> `mhi-Dashboard_v10.pbix` and are in neither page of `v11`. Found by diffing
> the two files field by field, **not** reported: they fell out with the layout
> rebuild. **Decided the same day: the removal stands — the
> page reads better without them.** The measures remain in the model and in
> this document; only the cards are gone.
>
> **What that costs, written here because nothing on screen says it any more:**
>
> ⚠️ **Nothing in the report now tells a reader that the contracted rate has
> not published since 2026-06-02.** That series, `FVI_MTG_RATE_5Y_FIX`, is the
> one `fact_mortgage_scenario` computes with, so the whole of page 3 rests on
> it. **dbt source freshness does not answer this question and stays green** —
> that asymmetry is the entire reason the card existed (see the paragraph near
> "That is why `Rate freshness warning` exists").
>
> **Where it is paid instead:** `docs/limitations.md`, J4.4 — one entry naming
> the series, the date it last published, and the fact that the qualifying rate
> of every affordability figure derives from it. That entry is now **load
> bearing**, not decorative.
>
> The association caveat text box **stays**: it carries brief §27, and it is
> the only thing on the page that does.

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
| ~~`Rate freshness warning`~~ | **card removed 2026-09-12** — nothing to check on screen. The measure still evaluates correctly if ever re-placed |
| ~~`Rate grain warning`~~ | **card removed 2026-09-12** — same |
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
| ~~`Rate freshness warning`~~ | **card removed 2026-09-12** — this case is void |
| `Trailing window` | `12 months, 2025-04-01 to 2026-06-30` |

**Two rows carry the whole check, because they are the only two things on this
page that can be wrong while looking right.**

**2026 Q3, the gap cell.** Blank is correct. **6.09** is the unguarded
subtraction of section D, and it is the only figure here a wrong measure returns
*confidently*. Everything else either matches or goes visibly blank.

~~**`Rate freshness warning` with a year selected.**~~ ⚠️ **Void since
2026-09-12: the card was removed, so a publisher outage is now invisible
whether or not anyone filters.** That was the trade accepted; the
cost is carried in `docs/limitations.md`, not here. The `ALL ( 'date' )`
calls stay in the measure — if the card ever comes back, this case comes
back with it.

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
| Guards | `Grain warning` | `_Measures` | filter state of `Census_Tract` | Text | **2** — removed from page 3 on 2026-09-12, it could never fire there |
| Guards | `Income vintage warning` | `_Measures` | `fact_affordability` | Text | 2 |
| Guards | `Income basis note` | `_Measures` | `fact_affordability` | Text | 2 |
| Guards | `Area is narrowed` | `_Measures` | `Sector` | Whole number (0/1) | 1, 3 |
| Guards | `Slice warning` | `_Measures` | `property_type`, `fact_affordability` | Text | ⚠️ **on no page since 2026-09-12** — the measure exists, no visual reads it |
| Market | `Sales (island, as published)` | `_Measures` | `fact_market` | Whole number, thousands sep. | 1 |
| Market | `Sales (selected area)` | `_Measures` | `fact_market`, `Area is narrowed` | Whole number, thousands sep. | 1 |
| Market | `Active listings (selected area)` | `_Measures` | `fact_market`, `Area is narrowed` | Whole number, thousands sep. | 1 |
| Market | `Median price (selected area)` | `_Measures` | `Median price`, `Area is narrowed` | Currency, 0 dec. | 1 |
| Market | `Days on market (selected area)` | `_Measures` | `Days on market`, `Area is narrowed` | Whole number | 1 |
| Market | `Price status (selected area)` | `_Measures` | `Price status`, `Area is narrowed` | Text | 1 |
| Market | `Price context (selected area)` | `_Measures` | `Price context`, `Area is narrowed` | Text | 1 |
| Market | `Area title` | `_Measures` | `Sector`, `Area is narrowed` | Text | 1 |
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
| Affordability | `Vintage effect (points)` | `_Measures` | `Share of tracts affordable`, `… (2020 dollars)` | Percentage, 1 dec. | 2 |
| Affordability | `Share of tracts affordable` | `_Measures` | the two `Tracts` measures | Percentage, 1 dec. | 2 |
| Affordability | `Income required, lower bound (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2, 3 |
| Affordability | `Household income (2020 census)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Income shortfall (mean)` | `_Measures` | `fact_affordability` | Currency, 0 dec., thousands sep. | 2 |
| Affordability | `Price to income (median)` | `_Measures` | `fact_affordability` | Custom `0.0"×"` — **never a currency** | 2 |
| Affordability | `Verdict` | `_Measures` | `fact_affordability` | Text | 2 |
| Affordability | `Tract map colour` | `_Measures` | `Verdict`, **`Income shortfall`** — corrected 2026-09-12, it stopped reading the ratio on 2026-09-02 | Text — a `#RRGGBB` string, **never formatted** | 2 |
| Affordability | `Down payment note` | `_Measures` | nothing — a constant string | Text | 2 |
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
| First-time buyer | `Tracts priced` | `_Measures` | `fact_affordability` | Whole number | 3 |
| First-time buyer | `Down payment regime code` | `_Measures` | `fact_mortgage_scenario`, `Down payment input` | Whole number | 3 |
| First-time buyer | `Income required at this down payment` | **`Down payment input`** | `fact_mortgage_scenario`, the two seed tables, `Down payment input` | Currency, 0 dec., thousands sep. | 3 |
| First-time buyer | `Verdict at this down payment` | **`Down payment input`** | `Down payment regime code`, `Income required at this down payment`, `Income input` | Text | 3 |
| First-time buyer | `Sectors within reach of this income` | `_Measures` | `Verdict at this down payment` | Whole number | 3 |
| First-time buyer | `Sectors borderline` | `_Measures` | `Verdict at this down payment` | Whole number | 3 |
| First-time buyer | `Sectors below the legal minimum` | `_Measures` | `Verdict at this down payment` | Whole number | 3 |
| First-time buyer | `Sector bar colour` | `_Measures` | `Verdict at this down payment` | Text | 3 |
| First-time buyer | `Down payment assumption` | `_Measures` | `fact_mortgage_scenario`, `Down payment regime code`, `Down payment input` | Text | 3 |
| First-time buyer | `Verdict for the selected sector` | `_Measures` | `Verdict at this down payment`, `Area is narrowed` | Text | 3 |
| Change | `Sales change` | `_Measures` | `Sales (selected area)`, `YoYBadge` | Text | 1 |
| Change | `Sales change colour` | `_Measures` | `Sales (selected area)`, `YoYBadgeColour` | Text | 1 |
| Change | `Price change` | `_Measures` | `Median price (selected area)`, `YoYBadge` | Text | 1 |
| Change | `Price change colour` | `_Measures` | `Median price (selected area)`, `YoYBadgeColour` | Text | 1 |
| Change | `Time on market change` | `_Measures` | `Days on market (selected area)`, `YoYBadge` | Text | 1 |
| Change | `Time on market colour` | `_Measures` | `Days on market (selected area)`, `YoYBadgeColour` | Text | 1 |
| Change | `Months of inventory change` | `_Measures` | `Months of inventory (selected area)`, `YoYBadge` | Text | 1 |
| Change | `Months of inventory change colour` | `_Measures` | same, plus `YoYBadgeColour` | Text | 1 |
| Change | ~~`Listings change`~~ | `_Measures` | **SUPERSEDED by 16.4** — kept as the worked example of a corroboration guard | Text | — |
| Change | ~~`Listings change colour`~~ | `_Measures` | **SUPERSEDED by 16.4** | Text | — |
| Change | `Share change` | `_Measures` | `Share of tracts affordable`, `YoYBadge` | Text | 2 |
| Change | `Share change colour` | `_Measures` | `Share of tracts affordable`, `YoYBadgeColour` | Text | 2 |
| Change | ~~`Tracts evaluated change`~~ | `_Measures` | **SUPERSEDED by 16.6** — the count moved into `Tracts detail` | Text | — |
| Change | ~~`Tracts evaluated colour`~~ | `_Measures` | **SUPERSEDED by 16.6** | Text | — |
| Change | `Required income change` | `_Measures` | `Income required, lower bound (mean)`, `YoYBadge` | Text | 2 |
| Change | `Required income change colour` | `_Measures` | same, plus `YoYBadgeColour` | Text | 2 |
| Market | `Months of inventory (selected area)` | `_Measures` | **`fact_market_trailing_12m`** — `active_listings`, `sales_count` — plus `Area is narrowed` and `Inventory corroboration (selected area)`. ⚠️ twelve-month denominator, see 16.4 | `0.0" months"` — **never a currency** | 1 |
| Market | `Inventory corroboration (selected area)` | `_Measures` | `Area is narrowed`, `fact_market_trailing_12m[active_listings_corroboration]` | Text | 1 |
| Market | `Inventory detail` | `_Measures` | `Months of inventory (selected area)`, `Inventory corroboration (selected area)`. **Holds APCIQ 8/10 bands** | Text | 1 |
| Affordability | `Household income (median tract)` | `_Measures` | `Household income (theoretical)`, `Census_Tract[geography_code]` | Currency, 0 dp. **Takes no reference label — see 16.6** | 2 |
| Affordability | `Tracts detail` | `_Measures` | `Tracts evaluated` | Text | 2 |
| Change | `Quarter comparison note` | `_Measures` | **nothing — a constant** | Text | 1, 2 |
| Change | `Colour convention note` | `_Measures` | **nothing — a constant** | Text | 1 |
| Icons | `Sales icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 1 |
| Icons | `Median price icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 1 |
| Icons | `Days on market icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 1 |
| Icons | `Months of inventory icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 1 |
| Icons | `Household income icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 2 |
| Icons | ~~`Active listings icon`~~ | `_Measures` | **SUPERSEDED by 16.4** — kept in 14.8, deleted from the model | Text | — |
| Icons | `Share affordable icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 2 |
| Icons | ~~`Tracts evaluated icon`~~ | `_Measures` | **SUPERSEDED by 16.6** — kept in 14.8, deleted from the model | Text | — |
| Icons | `Income required icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 2 |
| Icons | `Change since peak icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 2 |
| Icons | `Within reach icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 3 |
| Icons | `Borderline icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 3 |
| Icons | `Sectors priced icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 3 |
| Icons | `Below minimum icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 3 |
| Icons | `Selected sector icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 3 |
| Icons | `Posted minus contract icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | 4 |
| Icons | `Quote icon` | `_Measures` | **nothing — a constant** | Text, **data category Image URL** | **none yet** |
| — | `Income input Value` | `Income input` | the slicer selection | Currency, 0 dec. | 3 |
| — | `Down payment input Value` | `Down payment input` | the slicer selection | Currency, 0 dec. | 3 |

⚠️ **Two measures live in `Down payment input`, not `_Measures`, and that is a
decision rather than an oversight (2026-09-10).** Moving
`Income required at this down payment` and `Verdict at this down payment` into
`_Measures` broke other measures in Desktop, so they were left where they
are. DAX does not care — a measure is referenced as `[Name]` whatever table
holds it — and the index above says where they really are so nobody hunts for
them under `_Measures`.

**What it costs, written here so a future session does not have to rediscover
it**: ⚠️ **changing this what-if parameter's minimum, maximum or increment can
mean Desktop recreates the `Down payment input` table, and measures lodged
inside it go with it.** If the slider's range is ever changed and two measures
vanish, they are section 13.7 and 13.8 of this file — retype them, and put them
back wherever they will live.

`Down payment regime code`, `Sector bar colour` and whether
`Verdict for this income` still exists at all are **not readable from
`Report/Layout`** — one is on no visual, one is bound through `fx`, and absence
from every visual does not prove absence from the model. They have to be looked
at in Desktop, and they have not been.

⚠️ **Three DAX user-defined functions are NOT in this table, because they are
not measures.** `ValueOneQuarterEarlier`, `QuarterBadge` and
`QuarterBadgeColour` live under *Functions* in Model explorer, not under
`_Measures`, and section 14.2 is where they are written. They are what makes
every Change row above a one-liner — except `Listings change`, which carries the
corroboration refusal of 14.7 and is written out in full there.

⚠️ **`Verdict for this income` is absent from this table because section 13.10
deletes it**, once everything that reads it has been rebranched onto
`Verdict at this down payment`. `Income required, lower bound (mean)` stays —
it is page 2's, listed under Affordability, and the two must never share a page.

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
| 8b | **the `Down payment input` parameter (section 13.4)**, and the import of the two seed tables (13.3) | the whole First-time buyer chain refuses to resolve without them |
| 9 | the First-time buyer group, in the order of section 13: `Down payment regime code` → `Income required at this down payment` → `Verdict at this down payment` → the three counts and `Sector bar colour` | each reads the one before it. The colour and the counts read the verdict rather than repeating its comparison, which is what keeps the 10 % band in a single measure |
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
| First-time buyer | page 3 at 95 000 $, condominium, 2026 Q2, down payment **50 000 $** | 7 within reach, 2 borderline, 7 out of reach, 1 below the legal minimum, 1 with no published price — six classes, **totalling 18** — and `Sectors priced` reads 17 |
| First-time buyer | the same slice with the down payment slider at **0 $** | every priced sector below the legal minimum, no bars, and the KPI cards on a firm zero rather than blank |

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
/*  ⚠️ NO VISUAL READS THIS MEASURE SINCE 2026-09-12.
    Its card was removed from page 3 by decision; the measure itself is left
    in place. It was silent only because both slicers are strictSingleSelect,
    and the figures in the paragraphs below say what it was guarding against.
    KEEP THE PARAGRAPHS even if the measure is deleted: the 49 % and the
    7 -> 2 are the only record of a page that is wrong while looking right,
    and they are owed to docs/limitations.md in J4.4.  */
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

⚠️ **Format it `0.0"×"`, so the value always carries the multiplier sign and
never appears bare.** The column is
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
/*  ⚠️ SUPERSEDED 2026-09-02 AND STILL PRINTED HERE UNTIL 2026-09-12.
    This version colours by the PRICE-TO-INCOME RATIO on a 0-15 scale. The map
    stopped doing that on 2026-09-02: it now colours the INCOME SHORTFALL, on a
    ramp that diverges at zero, and the live colours are the table in section 6
    ("within reach / out of reach, from the threshold outwards").
    Two things make this block wrong rather than merely old: the 15x ceiling was
    set against the NON-indexed ratio and never followed the measure to the
    indexed column on 2026-08-31, and a ratio in levels is a figure this
    repository does not keep in a tracked file — multiply it by the published
    StatCan median income and the APCIQ median price comes back.
    KEPT, COMMENTED OUT, as the record of what the map used to do. Do not paste
    it into the model. The live definition is the section 6 palette.  */
/*
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
*/
```

⚠️ **The block above is commented out on purpose.** It is the 2026-08-30 version,
kept as a record. The colours the map actually uses are the ones in the palette
table of section 6, and the index entry in section 3.2 was corrected on
2026-09-12 to say so — it still claimed this measure read
`Price to income (median)`.

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

#### 2026-09-02 — the three measures the page was missing

**⚠️ THE CORRECTION THAT MATTERS MOST ON THIS PAGE, AND IT WAS ALMOST PUT ON
SCREEN.** Reading the one-person figures, the natural sentence is *"fewer than 1 % of
Montrealers without capital can buy"*. That is not what the measure says, and
the difference is not pedantry.

`Share of tracts affordable` counts **census tracts, not households**. A tract
is within reach when **its median household** clears the bar for **the median
property of its sector** — two medians, never a population. So in a tract that
is out of reach, up to half the households sit above the median and some of them
can buy; in a tract within reach, about half sit below and cannot.

**The model cannot answer "what share of Montrealers can buy."** It would need
the full income distribution per tract, and table 98100058 publishes medians
only. Section 41.1 forbids filling that gap.

The exact sentence, and it loses none of its force:

> On condominiums, in 2026 Q2, **in 99.2 % of the island's census tracts a
> single person earning the median income of their own neighbourhood cannot buy
> the median condominium of their sector** — with the minimum down payment and
> no other capital.

That version is checkable and can go in a public README. `Method note` below
carries the same caveat permanently on screen.

```dax
Method note =
VAR Amort = SELECTEDVALUE ( fact_affordability[amortization_years] )
VAR Rate  = SELECTEDVALUE ( fact_affordability[qualifying_rate_percent] )
RETURN
    "Income: 2020 census median, restated to this quarter by the Montréal CPI. "
        & "Buyer: the legal minimum down payment and not a dollar more — no other capital. "
        & "Mortgage: " & FORMAT ( Amort, "0" ) & "-year insured"
        & IF ( NOT ISBLANK ( Rate ), " at " & FORMAT ( Rate, "0.00" ) & " % qualifying" )
        & ", mortgage payment only at 39 % GDS — no property tax, heating or condo fees. "
        & "A tract is within reach when its MEDIAN household clears that bar: "
        & "this counts tracts, not households."
```

**Every assumption in that sentence was read back from the marts, not written
from memory** — `down_payment_scenario = minimum_down_payment`,
`rate_basis = contracted_high_ratio_5y_fixed`,
`income_required_basis = mortgage_payment_only_at_gds_39`,
`amortization_years = 25`,
`price_basis = apciq_sector_price_applied_to_tract`. The amortisation and the
rate are read live so the card cannot drift from the model.

Requested as "the axioms of the page, stated outright". The request named
three; the measure states five, because the price basis and the GDS floor weigh
as much as the down payment rule.

```dax
Affordability change since peak (points) =
VAR Quarters  = CALCULATETABLE ( VALUES ( 'date'[quarter_label] ), ALL ( 'date' ) )
VAR Peak      = MAXX ( Quarters, CALCULATE ( [Share of tracts affordable] ) )
VAR Displayed = [Share of tracts affordable]
RETURN
    IF (
        NOT ISBLANK ( Displayed ) && NOT ISBLANK ( Peak ),
        ( Displayed - Peak ) * 100
    )
```

Format `+0.0" pts";-0.0" pts";"at the peak"`. **The peak is searched, not
assumed**: it differs by type and profile.

⚠️ **`Current` is a reserved word in DAX** — the first version used it as a
variable name and the expression was rejected. Renamed `Displayed`. Same class
as `trailing` in PostgreSQL, found in J3.5.

⚠️ The two `ISBLANK` guards: without them an unindexed quarter yields
`BLANK − 92.5 = −92.5 pts`, a collapse invented out of nothing. Eighth
appearance of the mechanism.

```dax
Peak quarter =
VAR Quarters = CALCULATETABLE ( VALUES ( 'date'[quarter_label] ), ALL ( 'date' ) )
VAR Scored   = ADDCOLUMNS ( Quarters, "@share", CALCULATE ( [Share of tracts affordable] ) )
VAR Best     = MAXX ( Scored, [@share] )
RETURN
    "peak: " & CONCATENATEX ( FILTER ( Scored, [@share] = Best ), 'date'[quarter_label], ", " )
```

Without it, "−14.4 pts" does not say since when. The `@` in the added column
name stops the parser looking for a measure called `Share`.

**Expected on condo · couple:** peak **2019 Q2 at 92.5 %**, trough 2023 Q4 at
**−36.2 pts**, 2026 Q2 at **−14.4 pts**. On condo · one person the story is not
the slope but the level.


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
        NOT ISBLANK ( fact_affordability[median_price] ),
        REMOVEFILTERS ( Sector )
    )
RETURN IF ( ISBLANK ( Priced ), 0, Priced )
```

⚠️ **`REMOVEFILTERS ( Sector )` was added on 2026-09-09, with the sector slicer,
and it is what keeps this card a denominator.** Section 12.4. Without it,
selecting one sector turns "6 of 17" into "0 of 1", which a reader takes as a
statement about the island. Section 9.6 asked for `REMOVEFILTERS ( Place )`
alongside it; `Place` is deleted, so `Sector` alone is now both sufficient and
the only form that resolves.

⚠️ **It also removes the page filter `Sector[geography_type] is apciq_sector`,
and that is safe here for a measured reason.** `fact_affordability` holds
**18 sector keys and zero island rows** — verified 2026-09-09, 141 462 rows,
none of them keyed to anything but an APCIQ sector. The same gesture on
`fact_mortgage_scenario` would not be safe: it carries **19** area codes and
87 island rows, which is why the three counting measures of section 13.8 state
the exclusion themselves instead of relying on a page filter.

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
    CALCULATE (
        COUNTROWS (
            FILTER (
                VALUES ( fact_affordability[apciq_sector_number] ),
                VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
                RETURN NOT ISBLANK ( Required ) && Required * 1.10 <= Income
            )
        ),
        REMOVEFILTERS ( Sector )
    )
RETURN IF ( ISBLANK ( Reached ), 0, Reached )
```

```dax
Sectors borderline =
VAR Income = 'Income input'[Income input Value]
VAR Band =
    CALCULATE (
        COUNTROWS (
            FILTER (
                VALUES ( fact_affordability[apciq_sector_number] ),
                VAR Required = CALCULATE ( AVERAGE ( fact_affordability[income_required_lower_bound] ) )
                RETURN NOT ISBLANK ( Required ) && Required <= Income && Required * 1.10 > Income
            )
        ),
        REMOVEFILTERS ( Sector )
    )
RETURN IF ( ISBLANK ( Band ), 0, Band )
```

⚠️ **These two bodies are transitional.** The down-payment block of section 13
replaces both — they move onto `fact_mortgage_scenario` and read
`[Verdict at this down payment]` instead of repeating the comparison. Section
13.8 holds their final form, and it carries the island exclusion inside the
measure rather than leaning on the page filter. `Sectors priced` above is not
transitional: it stays on `fact_affordability`, and its body is final.

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
/*  ⚠️ SUPERSEDED TWICE, AND PRINTED HERE ONLY AS THE RECORD.
    This is the 2026-08-30 version: four classes, reading
    [Verdict for this income]. Block D replaced the income by the typed down
    payment on 2026-09-09, which took it to six classes and
    [Verdict at this down payment]; the colours were then replaced wholesale
    on 2026-09-12.
    THE DEFINITION IN FORCE IS THE ONE IN SECTION 13. Do not paste this one.
    Two of its three colours also fail the validator as they stand here:
    #C7CCD1 sits 7.0 from #E8EAEC in deuteranopia.  */
/*
Sector bar colour =
SWITCH (
    [Verdict for this income],
    "Within reach", "#17527A",
    "Borderline",   "#5B9BC4",
    "Out of reach", "#C7CCD1",
    "#E8EAEC"
)
*/
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

~~The page-3 verdict scale, chosen on 2026-08-30~~ — **replaced on 2026-09-12,
and the PRINCIPLE changed with it.** It read: `#17527A` within reach, `#5B9BC4`
borderline, `#C7CCD1` out of reach, `#E8EAEC` no published price — one hue plus
a neutral, *blue-to-grey rather than green-to-red, because the comparison is a
floor against a typed income, not a pass and a fail.*

> ⚠️ **That reasoning no longer holds, and it was abandoned by choice rather
> than by drift.** The scale in force (section 13) puts **coral on *out of
> reach*** and amber on the refusal. The red was introduced on
> 2026-09-12 and kept when choosing between measured options. So the page
> now does read as a pass and a fail — which is defensible, since the
> down-payment slider turned the page from "how far is this floor" into "can I
> buy here, yes or no", but it is a reversal and it is recorded as one.
>
> **What survives intact is the other half of the original reasoning**:
> decreasing luminosity in verdict order. The three favourable classes run
> 0.585 → 0.314 → 0.139, so the ranking still survives greyscale and colour
> blindness without leaning on hue. That is checked by the validator, not
> assumed.

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

⚠️ **The blue `#17527A`, page 3's *within reach* until 2026-09-12, was tried
here first and the validator refused it** — too dark for the lightness band and
too grey for the chroma floor. That was not a contradiction between the two
pages: there it belonged to a single-hue scale running dark to light, a
*sequential* job, and here it would have to establish identity against two other
hues, a *categorical* one. The same hex was right for one and wrong for the
other. **The point outlives the hex**: page 3 now runs `#9BD0F2` → `#4E9FD8` →
`#2A6CA3` and the reasoning is unchanged.

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
| `Verdict` | reads `meets_income_requirement` | reads `meets_income_requirement_indexed`, **and gains a sixth case** — see below |

⚠️ **`Verdict` needs a case the specification did not foresee, found while
applying it on 2026-08-31.** Switching to the indexed column makes `Meets` blank
on a quarter with no CPI factor **while the price and the 2020 income both
exist**. The old `SWITCH` then fell through to `"Not evaluated"`, a catch-all
that names nothing.

```dax
Verdict =
VAR Sectors = DISTINCTCOUNT ( fact_affordability[apciq_sector_number] )
VAR Meets = SELECTEDVALUE ( fact_affordability[meets_income_requirement_indexed] )
VAR HasPrice = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[median_price] ) )
VAR HasIncome = NOT ISBLANK ( SELECTEDVALUE ( fact_affordability[household_income] ) )
VAR Restated = SELECTEDVALUE ( fact_affordability[income_index_basis] ) = "cpi_rmr462"
RETURN
    SWITCH (
        TRUE (),
        Sectors > 1, "Shared between two sectors",
        NOT ISBLANK ( Meets ) && Meets, "Within reach",
        NOT ISBLANK ( Meets ), "Out of reach",
        NOT HasPrice, "No published price",
        NOT HasIncome, "No published income",
        NOT Restated, "Income not restated for this quarter",
        "Not evaluated"
    )
```

**Its position in the `SWITCH` is load-bearing**: after the two source
absences, because a sector with no published price stays *No published price*
even when the CPI is also missing.

⚠️ **It is unreachable today** — all 29 archived quarters are indexed — and
J4.2½ applies: *a branch predicted unreachable is not a control until something
has tried to reach it*. It is written, not verified.

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

## 8.6 bis How the reader reaches the 2020 figure

**The decision said "theoretical on screen, observed in second position",
and this file did not say by what gesture.** Asked on 2026-08-31 while building;
the answer has two layers.

> ⚠️ **REVISED 2026-09-02.** Two decisions below were changed
> after the page was built. They are corrected in place, with the reasoning,
> rather than left to be applied and undone.

**Layer one, free and always on: a second plane, not a tooltip.** The original
text put `Share of tracts affordable (2020 dollars)` in the line chart's
**Tooltips** well only. **Superseded**: it sits on the line chart as a second
series, **thin dotted grey, no markers, no data labels**, while the theoretical
share is solid, accented and labelled.

**The asymmetry is what justifies it, and it is not a matter of taste.** The
two figures do not bound an interval. 35.0 % divides a 2026 price by a 2020
dollar — two units of account, so it estimates six years of inflation as much
as it estimates affordability. 78.1 % is a named assumption whose direction is
known: it supposes household income tracked the CPI exactly, i.e. that real
income held. The CIS control measured in J4.2¾ says it fell slightly — RMR 462,
82 100 $ in 2020 against 81 100 $ in 2024, constant 2024 dollars — so the CPI
restatement runs a little rich. **The truth is a point or two below 78.1 %, not
halfway to 35.0 %.** Two series of equal visual weight would assert an
equivalence that does not hold; a second plane states the reference without
disputing the reading.

On the **sector bar** the same pair gets the opposite treatment: `(2020
dollars)` goes to **Tooltips**, with `Tracts evaluated`. Two clustered series
over eighteen sectors is thirty-six columns, and the ranking — the only thing
that chart has to say — disappears under the pattern. On the line the axis is
time and the gap *is* the trajectory; twenty-nine dotted points cost nothing.

**~~And name the gap~~ — `Vintage effect (points)` was NOT built.** Decided on
2026-09-02: with both series on the chart the gap is already
visible, and a fourth KPI card for a difference the eye reads is noise.

**The reservation, so this is a decision and not an oversight:** the gap is now
nowhere readable as a figure. It is **43.1 points on 2026 Q2** — the result of
J4.2¾ — and a chart shows it without naming it. Recovering it costs one measure
and one tooltip field, no object on the page. The measure, if it is ever wanted:

```dax
Vintage effect (points) =
VAR Restated = [Share of tracts affordable]
VAR AsPublished = [Share of tracts affordable (2020 dollars)]
RETURN
    IF (
        NOT ISBLANK ( Restated ) && NOT ISBLANK ( AsPublished ),
        Restated - AsPublished
    )
```

Affordability group. ⚠️ **Number, not percentage, and that correction stands
even though the measure was dropped**: `+43.1 %` printed beside a card reading
`78.1 %` reads as a 43 % relative rise. It is a gap between two shares, so it is
points — hence the `* 100` and a custom format of `+0.0" pts";-0.0" pts"`.

**+43.1 points on 2026 Q2** — the share of the displayed collapse that was not
the market. **−0.7 point on 2019 Q2**, negative because the index deflates
towards the past, which is the control showing it does not always point one
way.

⚠️ **The two `ISBLANK` are not padding.** Without them an unindexed quarter
yields `BLANK − 35.0 = −35.0`, a gap invented out of nothing. Sixth appearance
of the same mechanism.

**Layer two — two focus views driven by bookmarks. ABANDONED 2026-09-02.**

Specified on 2026-08-31, deferred the same day, and dropped before
being built. **The reason is analytical, not a matter of effort, and it is the
better argument:**

> A focus view would have legitimised the grey line as a COMPETING READING. It
> is not one. 35.0 % divides a 2026 price by a 2020 dollar — two units of
> account — so its collapse measures six years of inflation as much as it
> measures affordability. Analysing that vintage across time does not mean
> anything, and the collapse of the grey line is precisely what shows it.

In permanent second plane the grey line does the one job it can do: it shows
where the figure came from and why it had to be restated. Given a view of its
own, it would have claimed to answer the same question as the blue line.

**What this decision retires**: the two bookmarks, the two buttons, the
duplicated line chart, share card and view label — and with them the two traps
recorded on 2026-08-31 (unchecking *Data*, and objects that name a view having
to exist twice). None of it is needed.

**What survives from that specification, and is worth keeping in mind if a
toggle is ever proposed again:** a bookmark does not touch DAX, so it carries no
implicit default to get wrong — unlike a `SELECTEDVALUE ( …, "theoretical" )`
slicer, whose default fires both when nothing is selected and when everything
is. If a switch ever becomes necessary, bookmarks remain the right mechanism.

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

# 9. J4.2¾ · 2 — The place filter (SUPERSEDED 2026-09-01)

> ⚠️ **Kept as the record of a decision that was reversed, not as the
> design.** On 2026-09-01 page 1 was narrowed to the APCIQ sector:
> 18 published prices, so a control offering 34 names promises a figure
> that does not exist. **Section 11 says what survives of this and what
> goes.** The measurement in 9.1 stays true and still explains why a
> sector name is not a place a reader recognises.

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

```dax
Active listings (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE (
            SUM ( fact_market[active_listings] ),
            fact_market[is_island_aggregate] = FALSE ()
        ),
        CALCULATE (
            SUM ( fact_market[active_listings] ),
            fact_market[is_island_aggregate] = TRUE ()
        )
    )
```

It is written out in full rather than left as *the same shape as the measure
above*. Two measures that must stay identical are worth two blocks: a reader
translating "the same shape" is a reader who can translate it wrong, and this
one differs from `Sales (selected area)` by exactly one column name.

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

### The visual-level `is island` filter has to go, and four measures go with it

**Found on 2026-09-01, applying B5.** The two measures above are necessary and
they are not sufficient, and the reason is not in them.

The KPI row carries a visual-level filter `Sector[geography_type] is island` —
`Median price`, `Days on market`, `Price status` and `Price context` need it,
because one property type and one quarter still leave nineteen rows and
`Median price` blanks on anything but a single published cell. With a place
selected, `Sector` is filtered to that place's sector, and
`{sector} INTERSECT {island}` is **empty**. Every card in the row blanks,
including `Sales (selected area)`: a measure that switches on
`is_island_aggregate` still reads whatever rows the visual filter leaves, and
that is none.

So the filter comes off the row — and the four measures that relied on it have
to carry the switch themselves, exactly as the two above do:

```dax
Median price (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE ( [Median price], fact_market[is_island_aggregate] = FALSE () ),
        CALCULATE ( [Median price], fact_market[is_island_aggregate] = TRUE () )
    )
```

```dax
Days on market (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE ( [Days on market], fact_market[is_island_aggregate] = FALSE () ),
        CALCULATE ( [Days on market], fact_market[is_island_aggregate] = TRUE () )
    )
```

```dax
Price status (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE ( [Price status], fact_market[is_island_aggregate] = FALSE () ),
        CALCULATE ( [Price status], fact_market[is_island_aggregate] = TRUE () )
    )
```

```dax
Price context (selected area) =
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
RETURN
    IF (
        PlaceChosen,
        CALCULATE ( [Price context], fact_market[is_island_aggregate] = FALSE () ),
        CALCULATE ( [Price context], fact_market[is_island_aggregate] = TRUE () )
    )
```

**All four are written out, and that is not padding.** The first draft of this
section left three of them as *the same four lines around* the other measures —
the identical shortcut this file had just removed from
`Active listings (selected area)` a few pages up. Four measures that must stay
identical are worth four blocks; the difference between them is one measure
name, which is precisely the kind of difference a reader retypes wrong.

**Each wraps the original measure instead of restating it.** "A median cannot be
averaged" stays written in exactly one place, in `Median price`; the wrapper
only decides which rows that rule is applied to. This is the discipline
`Sector price colour` and `Verdict for the selected place` already follow, and
here it also keeps the sector bar and the sector table working: they filter
`is apciq_sector` themselves and go on reading the **unwrapped** measures. That
is why the switch is a new measure and not a rewrite of the old one — rewriting
`Median price` would empty the table beside it.

**What each state then shows, and both are correct:**

| Selection | `Median price (selected area)` |
|---|---|
| none | the island's published median — the row reads as it does today |
| one place, one sector | that sector's median |
| Verdun, or any multi-selection | blank, and `Price context (selected area)` prints its sentence |

The third row is the decision of 2026-08-31 — *multi-select stays allowed,
`Median price` blanks with its sentence* — working as intended rather than
failing. Two sectors are two published cells, and there is no median of two
medians.

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
| **No selection** | page 1 KPI row identical to today; `Area title` reads *Island of Montréal*; the three page-3 cards read 6 / 1 / 17 at 95 000 $ (the map's four colour classes are what total 18: 6 + 1 + 10 + 1) |
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


# 10. J4.2¾ · 2 bis — The place map

**Built 2026-09-01.** Page 1 draws **36 shapes** — 32 administrative entities
plus the four halves of the two boroughs APCIQ splits — instead of the 18
sector outlines, so a reader can find the place they
live in. `marts.map_place` and `powerbi/shapes/admin_place_island.geojson` hold
it; read the model header before changing anything.

## 10.1 What the map is allowed to claim

**Nothing new.** APCIQ publishes 18 prices and this map draws 36 shapes, so
several shapes carry the same figure — the seven municipalities of sector 1 are
one published number, not seven. That is a readability trade, never a grain.
Nothing joins a fact to `place_key`, and nothing ever should.

**Why 36 and not 34.** The first version drew the 34 administrative entities
and lost a whole published sector: L'Île-des-Sœurs is APCIQ sector 10 and is
not an administrative entity, so nothing drew it. Verdun and CDN–NDG are
therefore cut along the neighbourhood lines the seed `apciq_sector_neighbourhood`
already declares — the same declaration J3.4 uses to place census tracts.

⚠️ **One of those two lines is an assumption.** APCIQ publishes no boundary
between sectors 7 and 8; the city's 2014 sociological line stands in for it,
over 40 tracts and 170 583 people. `boundary_is_assumed` carries it on those
two shapes and the tooltip says so. Verdun is cut on water, which is not an
assumption — and conflating the two would hide the only assumed line on the map.

⚠️ **The relationship `Place_map[apciq_geography_key]` → `Sector[geography_key]`
must be BIDIRECTIONAL.** Many-to-one propagates from the one side to the many:
`Sector` filters `Place_map`, not the reverse. In single direction the map
groups by place, that grouping never reaches `fact_market`, `Median price` sees
nineteen geographies instead of one and returns blank — **and the whole map
comes out grey, which looks exactly like a shape file that failed to join.**
Diagnosed on the first build, 2026-09-01.

## 10.2 The acceptance cases

Coloured + grey must always total **36**. Measured on 2026 Q2:

| Property type | Coloured | Grey |
|---|---|---|
| Condominium | 35 | 1 |
| **Plex** | **12** | **24** |
| Single-family | 32 | 4 |

**Accept on plex**, not condominium: 24 grey shapes out of 36 is the only case
that shows whether absence reads as absence. Same reasoning as the 216 grey
tracts on page 2.

**The four cut shapes are all coloured on condominium 2026 Q2** — *Verdun
(L'Île-des-Sœurs)*, *Verdun (Le Sud-Ouest)*, *CDN–NDG (CDN/CSL)*, *CDN–NDG
(NDG/Montréal-Ouest)*. If any of them is grey, the cut lost its sector key.

⚠️ **Compare against the old sector map once, on purpose.** Every sector that
had a colour there must have one here. That is how the missing Île-des-Sœurs
was found, and it is now also a dbt test — but the eye found it first.

## 10.3 The tooltip, and the note that replaced a measure

**The tooltip carries two fields: the place name and
its APCIQ sector.** That answers the question the map raises — *where does this
figure come from* — and no measure was needed for it.

A `Place map tooltip` measure was written, then dropped on 2026-09-01. It
restated in words what those two fields already show, and it listed the other
places sharing a sector — which the map shows better than any sentence: four
shapes of the same colour, side by side. **A tooltip is read while moving a
mouse; anything past a line is not read at all.**

### What a tooltip could not carry, and where it went instead

Two of the 36 shapes — the halves of Côte-des-Neiges–Notre-Dame-de-Grâce — are
separated by a line **APCIQ does not publish**. The city's 2014 sociological
boundary stands in for it. On screen those two shapes look exactly like the 34
others, which are official administrative limits: **an assumption drawn as a
measurement**, which is the one thing this project does not leave standing.

Decided: a **static text box** under the map, not a measure.

```text
Each shape is coloured by the median of its APCIQ sector, so neighbouring
shapes can share one published figure. The line dividing Côte-des-Neiges from
Notre-Dame-de-Grâce is not published by APCIQ: the city's 2014 sociological
boundary stands in for it.
```

⚠️ **No figure, no count, and no quarter in that box, ever.** A text box is
filtered by nothing and refreshes never — the same rule that removed "over
these 29 quarters" from the page 4 caveat on 2026-08-29. Everything above is
structural: it stays true whatever the slicers do and whatever the next APCIQ
edition brings.

⚠️ **The full version of this limitation still belongs in `limitations.md` in
J4.4** — 40 census tracts and 170 583 people are placed by that line. The box
is the warning at the point of reading, not the record.

⚠️ **`Place_map` is a provisional name.** The model also holds `Place`, the
36-row bridge imported for the place slicer of section 9, which is on hold. One
of the two has to go.


# 11. The clean-up after the grain was rewritten

**2026-09-01.** Section 9 specified a slicer over 34 places. The grain changed
the same day: page 1 speaks **APCIQ sectors**, because there are 18
published prices and a control offering 34 names promises a figure that does
not exist. Section 9 is kept as the record of a decision that was reversed, and
is **not** the design any more.

This section says what survives, what goes, and in which order — because the
order matters: deleting the `Place` table first would break seven measures at
once.

## 11.1 What goes

| Object | Why |
|---|---|
| table **`Place`** (the 36-row bridge) | It existed to feed a slicer of places. There is no slicer of places. `Place_map` carries the same relationships with one row per drawn shape, which the bridge could not |
| **`Selected area disclosure`** | It names *the extra places shown beyond the one you picked*. With a sector-level control there is no "one you picked" below the sector, and `Place map tooltip` already names what a shape covers — better, because it fires where the reader is looking |

## 11.2 What survives, and the one line each of them changes

Seven measures branch on `ISFILTERED ( Place[admin_name] ) || ISFILTERED (
Place[apciq_sector_name] )`. That test dies with the table. It is replaced by a
single measure both more robust and written once:

```dax
Area is narrowed =
VAR SectorsShown =
    CALCULATE ( COUNTROWS ( Sector ), Sector[geography_type] = "apciq_sector" )
VAR SectorsAll =
    CALCULATE (
        COUNTROWS ( Sector ),
        REMOVEFILTERS ( Sector ),
        Sector[geography_type] = "apciq_sector"
    )
RETURN INT ( NOT ISBLANK ( SectorsShown ) && SectorsShown < SectorsAll )
```

**Why a count rather than `ISFILTERED`, and it is not a matter of taste.**
`ISFILTERED` only sees a filter placed *directly* on the column it names. A
reader clicking a shape on the map filters `Place_map`, which reaches `Sector`
by propagation — `ISFILTERED ( Sector[name] )` stays FALSE, and the KPI row
would go on showing the island under a map that clearly shows one sector.
Counting what survives asks the only question that matters — *is the view
narrower than the whole island?* — and answers it the same way whatever did the
narrowing: the slicer, the map, a bar, or a page filter.

It returns `1` / `0` rather than TRUE/FALSE so it can be read as a number in
any context without a conversion surprise. ⚠️ **The `NOT ISBLANK` guard is
not decoration** — section 12.2 says which row of `Sector` it protects against
and why the measure would have looked correct without it.

Each of the seven then swaps one line:

```dax
-- before
VAR PlaceChosen =
    ISFILTERED ( Place[admin_name] ) || ISFILTERED ( Place[apciq_sector_name] )
-- after
VAR PlaceChosen = [Area is narrowed] = 1
```

That covers `Sales (selected area)`, `Active listings (selected area)`,
`Median price (selected area)`, `Days on market (selected area)`,
`Price status (selected area)` and `Price context (selected area)`.

**`Area title` changes more than one line**, because it also *names* the area:

```dax
Area title =
VAR Areas = CALCULATETABLE (
                VALUES ( Sector[name] ),
                Sector[geography_type] = "apciq_sector"
            )
VAR HowMany = COUNTROWS ( Areas )
RETURN
    SWITCH (
        TRUE (),
        [Area is narrowed] = 0, "Island of Montréal",
        HowMany = 1, CONCATENATEX ( Areas, Sector[name] ),
        HowMany & " sectors selected"
    )
```

⚠️ **It reads the same filter state as the value measures, through the same
measure.** A title that computed its own idea of the perimeter is exactly the
fault this repository has refused since J3.1 — and the one `Sector price colour`
avoided by reading `Price relative to the island` instead of recomparing.

## 11.3 The order of operations

1. Create `Area is narrowed`.
2. Swap the one line in the six `(selected area)` measures, and rewrite
   `Area title`.
3. **Check the KPI row against `scripts/report_oracle.py`** on condominium +
   2026 Q2 with nothing selected. The four figures are sales, listings and a
   median from APCIQ, so they are not written in this repository -- the
   oracle reads them from the marts at run time. Nothing should have moved: with
   no narrowing, both the old test and the new one take the island branch.
4. Delete `Selected area disclosure` from the three pages, then from the model.
5. Delete the `Place` table.
6. Re-check the same four figures.

⚠️ **Do not delete first.** Power BI reports a broken measure where it is used,
not where the table was removed, so a table deleted before its readers are
rebranched turns one action into six error messages on three pages.

⚠️ **If the four `(selected area)` wrappers are ever deleted too**, the
visual-level filter `Sector[geography_type] is island` must go back on the KPI
row. Without either, the row sees nineteen rows and `Median price` blanks.


# 12. The sector slicer

**2026-09-01.** The control page 1 gets is a slicer over the **18 APCIQ
sectors** — the grain APCIQ actually publishes. It replaces the 34-place slicer
of section 9, and it needs no new table: `Sector` is already in the model and
already reaches all four fact tables.

## 12.1 The slicer

| | |
|---|---|
| Field | `Sector[name]` |
| **Visual-level filter** | **`Sector[geography_type] is apciq_sector`** |
| Selection | multiple allowed |
| *Select all* | off |
| Synchronised on | pages **1 and 3**. **Never page 4** — `fact_interest_rate` has no geographic column, and a synchronised control there would be inert, which is worse than no control |

⚠️ **The visual-level filter is not tidiness, it is the seventh appearance of
the blank-as-zero trap.** `Sector` holds 19 rows: the 18 sectors and the island
aggregate. Without the filter, *Île de Montréal (agglomeration)* appears in the
list, and selecting it leaves **no** row with
`geography_type = "apciq_sector"` — so the count in `Area is narrowed` returns
BLANK, DAX compares BLANK as 0, `0 < 18` is true, every measure switches to its
sector branch, and there is no sector. **Every KPI goes blank while the slicer
shows a perfectly reasonable selection.**

The filter removes the row from the list. The guard in 12.2 removes the fault
even if the row comes back by another route.

## 12.2 `Area is narrowed` — corrected before it was ever built

```dax
Area is narrowed =
VAR SectorsShown =
    CALCULATE ( COUNTROWS ( Sector ), Sector[geography_type] = "apciq_sector" )
VAR SectorsAll =
    CALCULATE (
        COUNTROWS ( Sector ),
        REMOVEFILTERS ( Sector ),
        Sector[geography_type] = "apciq_sector"
    )
RETURN INT ( NOT ISBLANK ( SectorsShown ) && SectorsShown < SectorsAll )
```

**`NOT ISBLANK` is the whole correction.** "No sector survives" and "one sector
survives" are different states and must not switch the same way: the first means
*nothing to show*, and the honest answer there is the island, not an empty
sector branch. Written without the guard, the measure would have been correct
on every case anyone would have thought to test, and wrong on the one row of
`Sector` nobody thinks about.

## 12.3 Page 2 is deliberately NOT synchronised

`Sector` reaches `fact_affordability`, so the slicer *would* work there. It is
left off, and the reason is measured rather than preferred.

Page 2 draws **541 census tracts**. Selecting one sector colours the 30 to 40
tracts it contains and leaves roughly 500 grey — and on that page grey already
means *no published price* or *no 2020 income*. **A Power BI map cannot
highlight**: a filtered-out shape and a shape with no data are the same grey,
so the map would state an absence that is not there.

The page keeps its own controls. A reader who wants one sector's tracts has
page 1 for the sector view and the page 2 table for the detail.

## 12.4 Page 3 — the three island cards get simpler

Section 9.6 required `REMOVEFILTERS ( Place )` **and** `REMOVEFILTERS ( Sector )`
on the three KPI cards, because the filter landed on `Place` and came back
through a bidirectional relationship. **With `Place` deleted and the slicer
sitting directly on `Sector`, `REMOVEFILTERS ( Sector )` alone is now enough** —
and it is the only form that stays right, because there is no longer a `Place`
table to name.

`Verdict for the selected place` keeps its job and its shape; only its name is
now inaccurate. Rename it **`Verdict for the selected sector`**, and swap its
test to `[Area is narrowed] = 1`.

## 12.5 Acceptance

| Case | What must happen |
|---|---|
| **No selection** | all pages read exactly what they read today; `Area title` says *Island of Montréal*; page 3 cards read 6 / 1 / 17 at 95 000 $ |
| **One sector** | the KPI row shows that sector; `Area title` names it; the map keeps all 36 shapes |
| **Two sectors** | `Area title` reads *2 sectors selected*; `Median price` blanks and `Price context (selected area)` prints its sentence — a median of two medians does not exist |
| **The island row, if it ever reaches the list** | the KPI row shows the island, never blank. That is the guard of 12.2 |
| **Page 4** | slicer absent, page unchanged |

⚠️ **The map must keep all 36 shapes when a sector is selected.** The slicer
filters `Sector`, and `Place_map` hangs off `Sector` by a bidirectional
relationship — so the filter propagates back and the map would draw one shape.
Set **Format > Edit interactions > None** between the slicer and the map, or
the page loses the context that makes a selection readable.


# 13. J4.2¾ · 3 — The typed down payment

**2026-09-09.** Page 3 assumed the legal *minimum* down payment, because that
is the only scenario `fact_mortgage_scenario` carries. A reader with savings
was not modelled, and `Down payment assumption` existed to say so. This section
replaces that card with a control.

The whole of it lives in DAX. **No dbt model moves**, and the two figures that
prove the model is untouched are the ones to check first: `dbt build` stays at
PASS=353 and the pytest suite at 140.

## 13.1 What changes, and what deliberately does not

| | |
|---|---|
| **Page 3** | gains a `Down payment input` slider; every figure on the page becomes a figure *at that down payment* |
| **Page 2** | **unchanged**. Its map still colours the shortfall computed in SQL at the legal minimum |
| **Pages 1 and 4** | unchanged; neither carries a mortgage figure |
| `marts.fact_mortgage_scenario` | unchanged. It remains the legal-minimum scenario, and it remains what the oracle checks against |
| `income_required_lower_bound` | **keeps its name.** A bigger down payment moves the floor up towards the true figure; it does not reach it. The GDS ratio still charges property tax, heating and half of any condo fees, and this project still holds none of the three |

**Page 2 is left out on purpose, and the reason is a measurement rather than a
scope decision.** On 2026-08-31 the indexed verdict and the indexed ratio were
computed in SQL rather than left to DAX, because two definitions of one
threshold had been found cohabiting on page 3 and disagreeing on **44 of 87
slices**. Re-deriving `income_shortfall_indexed` in DAX for 541 census tracts
would recreate exactly that: one figure with a SQL definition and a DAX
definition, differing wherever a guard was written in one and forgotten in the
other. Decided on 2026-09-09.

## 13.2 The probe that licenses every formula below

Before a measure was written, the entire mortgage chain was re-implemented in
SQL **with the down payment as a free parameter**, and then fed the legal
minimum — the one input for which the answer is already known, because
`fact_mortgage_scenario` holds it.

| Compared on the 1 223 rows that carry a price | Rows differing by more than one cent |
|---|---|
| loan amount | **0** |
| insurance premium | **0** |
| monthly payment at the qualifying rate | **0** |
| income required | **0** |

So the DAX below is not a re-reading of `fact_mortgage_scenario.sql` — it is a
transcription of a chain that was checked against the table it has to agree
with. ⚠️ **That is also why every formula here mirrors the SQL line for line,
including the parts that look clumsy.** The `- 0.0001` on the band lookup and
the rounding of the payment *before* it is divided by the GDS ratio are not
style; changing either makes the page disagree with the oracle by a few dollars
per sector, which is exactly the size of error nobody notices.

## 13.3 Two seed tables to import, and one deliberately not

Both **disconnected** — no relationship to anything. They are parameter
lookups, read with explicit filters, never sliced by the page.

| Import | Rows | What it carries |
|---|---|---|
| `marts.mortgage_insurance_premium_band` | 11 | the CMHC premium rate by amortization × LTV band × down-payment kind |
| `marts.mortgage_underwriting_parameter` | 12 | GDS, the qualifying rate buffer and floor, the amortization, the compounding convention |

⚠️ **`mortgage_down_payment_bracket` is NOT imported, and importing it would be
a mistake.** The mart already publishes `minimum_down_payment` on every row,
computed from that seed in SQL. Importing the bracket to re-derive the same
figure in DAX would put a second definition of the legal minimum in the model —
the one thing this section is organised to avoid. The measure reads the column.

**Both tables keep their database names**, unlike the dimensions. The `dim_`
convention does not apply: these are neither dimensions nor facts, and a name
that matches the seed is what lets a reader find where the number came from.

## 13.4 The what-if parameter

**Modeling > New parameter > Numeric range.**

| Field | Value |
|---|---|
| Name | `Down payment input` |
| Data type | Whole number |
| Minimum | 0 |
| Maximum | 300000 |
| Increment | 5000 |
| Default | **50000** |

**The name clears two collisions, and the reasoning is the one that named
`Income input`.** `fact_mortgage_scenario[minimum_down_payment]` is a figure
*derived from a published rule*; `Down payment input` is a number the reader
types. And the measure `Down payment assumption` keeps its name because it
still does what it says — it states the assumption, which is now the typed
figure rather than the legal minimum.

⚠️ **0 is a real input and must not be overloaded to mean "use the legal
minimum".** A reader with nothing saved is the reader this project was built
for, and the honest answer at 0 $ is *below the minimum down payment* on every
sector. Making 0 mean something else would take the page's most common starting
question and answer a different one.

⚠️ **There is no "follow the mart" toggle either**, and the reason is on the
record. Such a switch would rest on `SELECTEDVALUE ( …, <default> )`, whose
default fires both when **nothing** is selected and when **several** things
are — the DAX form of the blank-as-zero mechanism, written down on 2026-08-31
when a vintage toggle was rejected for the same reason.

**Why the default is 50 000 $, and what it moves.** Measured on 2026-09-09
across the 54 sector × property-type slices of the most recent quarter, at the
95 000 $ income the page opens on:

| Legal minimum → 50 000 $ | Slices |
|---|---|
| `Out of reach` → **`Below the legal minimum`** | **19** |
| `Out of reach` → `Borderline` | 2 |
| `Borderline` → `Within reach` | 1 |
| unchanged | 32 |

**Nineteen of the twenty-two are not verdicts flipping, they are verdicts
ceasing to exist** — the scenario becomes one the law does not allow, and the
page stops answering rather than answering wrongly. Nothing here is an
approximation: at 50 000 $ the chain computes exactly, against each sector's own
published price.

⚠️ **At 50 000 $ the plex carries no verdict at all** — nine sectors below the
legal minimum, nine with no published price. That is true, and it is
recognisable at a glance: nobody expects to buy a plex with 50 000 $ down. It
is left as it falls, on the same grounds the page already shows nine plex
sectors *Out of reach* today.

## 13.5 The measures read `fact_mortgage_scenario`, not `fact_affordability`

**This is the J4.1 split line, used for the purpose it was drawn for.** A down
payment is a property of the purchase, not of the household: it belongs on the
1 653-row table keyed to quarter × area × property type, not on the 141 462-row
table that repeats each purchase once per household profile. Reading the
household table for a household-independent quantity would work — and would
re-create the confusion two tables were built to prevent.

It carries every input the chain needs, on one row: `median_price`,
`minimum_down_payment`, `contract_rate_percent`.

**Nothing has to be created in the model.** `Sector`, `'date'` and
`property_type` already reach `fact_mortgage_scenario` — three of the thirteen
relationships listed in `powerbi/README.md` section 5.

**`Sectors priced` and `Tracts priced` stay on `fact_affordability`**, and that
is a deliberate exception. `Tracts priced` counts census tracts, which the
scenario table does not carry. `Sectors priced` stays beside it so the KPI row's
denominator comes from one table. The two tables could in principle disagree
about which sector has a price — and the check that they do not is **already in
the oracle**, written on 2026-08-30 for a different reason: across all 141 462
rows there is no row where a median price is present and a required income is
missing, nor the reverse.

## 13.6 The regime, decided in exactly one place

```dax
Down payment regime code =
VAR Price   = CALCULATE ( AVERAGE ( fact_mortgage_scenario[median_price] ) )
VAR MinDown = CALCULATE ( AVERAGE ( fact_mortgage_scenario[minimum_down_payment] ) )
VAR Down    = 'Down payment input'[Down payment input Value]
VAR Ltv     = DIVIDE ( Price - Down, Price )
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Price ), 0,   -- no published price
        Down >= Price,     1,   -- cash purchase, no mortgage
        Down < MinDown,    2,   -- below the legal minimum
        Ltv <= 0.80,       3,   -- uninsured
        4                       -- insured
    )
```

**⚠️ THE ORDER OF THESE FIVE TESTS IS THE WHOLE MEASURE.** Written the other way
round — band first, legality afterwards — a down payment below the legal minimum
pushes the LTV above 95 %, where **no band exists in the seed**, the lookup
returns blank, and a `coalesce` reads that blank as a premium of *zero*. The
naive probe of 2026-08-31 did exactly that and produced a loan **1.23 times
larger than the legal one**, with no premium. Fifth appearance of the
blank-as-zero mechanism in this project.

**With the guard first, the two dangerous branches stop existing rather than
being caught.** Measured on 2026-09-09 over the whole table at seven slider
positions from 0 to 300 000 $:

- **`no band` occurs 0 times**, at every position. Once the down payment is at
  or above the legal minimum, the LTV cannot exceed 95 %: that *is* what the
  minimum is.
- **`not insurable` becomes unreachable.** Above 1.5 M$ the legal minimum is
  20 %, so an LTV above 80 % there already means *below the minimum*. The mart
  carries the status for its own scenario; the slider chain never needs it.

⚠️ **`0.80` is a constant in this formula, and it is the third place it lives**
— `fact_mortgage_scenario.sql` writes it twice. Decided on
2026-09-09: **accepted and documented**, rather than promoted to a seed row.
What it costs is stated plainly here so nobody has to rediscover it: the
threshold above which mortgage insurance is compulsory is a published rule, and
none of the three places it appears says where it comes from. The control is
`scripts/report_oracle.py`, which computes the same regimes in SQL — a page that
disagrees with it has one of the three copies wrong.

⚠️ **The regime is a *code*, not a label, and the chain reads the code.** A
chain that re-derived the regime from its own arithmetic could refuse where the
regime said *insured*, or compute where it said *below the minimum*. One
decision, read twice.

## 13.7 The chain

```dax
Income required at this down payment =
VAR Regime = [Down payment regime code]
VAR Price  = CALCULATE ( AVERAGE ( fact_mortgage_scenario[median_price] ) )
VAR Rate   = CALCULATE ( AVERAGE ( fact_mortgage_scenario[contract_rate_percent] ) )
VAR Down   = 'Down payment input'[Down payment input Value]
VAR Loan0  = Price - Down
VAR Ltv    = DIVIDE ( Loan0, Price )

VAR Years =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "max_amortization_years_standard"
    )
VAR Compounding =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "interest_compounding_periods_per_year"
    )
VAR Gds =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "gds_max_ratio"
    ) / 100
VAR BufferInsured =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "qualifying_rate_buffer"
    )
VAR BufferUninsured =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "qualifying_rate_buffer_uninsured"
    )
VAR FloorInsured =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "qualifying_rate_floor"
    )
VAR FloorUninsured =
    CALCULATE (
        MAX ( mortgage_underwriting_parameter[parameter_value] ),
        mortgage_underwriting_parameter[parameter_name] = "qualifying_rate_floor_uninsured"
    )

VAR Band =
    MAXX (
        FILTER (
            ALL ( mortgage_insurance_premium_band ),
            mortgage_insurance_premium_band[amortization_years] = Years
                && mortgage_insurance_premium_band[down_payment_kind] = "traditional"
                && Ltv > mortgage_insurance_premium_band[ltv_from] - 0.0001
                && Ltv <= mortgage_insurance_premium_band[ltv_to]
        ),
        mortgage_insurance_premium_band[premium_rate]
    )

VAR Premium = IF ( Regime = 4, ROUND ( Loan0 * Band, 2 ), 0 )
VAR Loan    = Loan0 + Premium

VAR QualifyingRate =
    MAX (
        Rate + IF ( Regime = 3, BufferUninsured, BufferInsured ),
        IF ( Regime = 3, FloorUninsured, FloorInsured )
    )
VAR MonthlyRate =
    POWER ( 1 + QualifyingRate / 100 / Compounding, Compounding / 12 ) - 1
VAR Payment =
    ROUND (
        DIVIDE ( Loan * MonthlyRate, 1 - POWER ( 1 + MonthlyRate, - Years * 12 ) ),
        2
    )
RETURN
    IF (
        Regime < 3 || ( Regime = 4 && ISBLANK ( Band ) ),
        BLANK (),
        ROUND ( Payment * 12 / Gds, 2 )
    )
```

**Read once, in order, this is the same chain the SQL runs.** A price, minus
what the buyer puts down, is the loan before insurance. Insurance is added to
the loan when the loan is above 80 % of the price, at the rate the seed
publishes for that band. The payment is computed not at the rate the buyer
gets but at the **qualifying** rate the regulator imposes — the contract rate
plus two points, or 5.25 %, whichever is higher. And the income required is
that payment, over a year, divided by the 39 % of gross income a lender allows
to go to housing.

**The five things worth knowing before editing it:**

⚠️ **`POWER ( …, Compounding / 12 )` is not `/ 12`.** Canadian fixed-rate
mortgages are quoted **half-yearly**, so the monthly rate is
`(1 + annual/2)^(1/6) − 1`. The simpler form overstates every payment. The seed
row that carries the convention says in its own text that it is *market
practice, not law*.

⚠️ **`Payment` is rounded to the cent BEFORE being divided by the GDS ratio.**
`fact_mortgage_scenario.sql` rounds in exactly that order. Round once at the end
instead and the page disagrees with the oracle by a few dollars a sector —
enough to move a verdict that sits on the threshold, not enough for anyone to
suspect the formula.

⚠️ **The uninsured pair of underwriting parameters is read even though it is
identical to the insured pair today.** Both stand at a 2-point buffer and a
5.25 % floor, so the 20 % threshold currently changes the premium and the loan
but not the qualifying rate. Reading the right pair costs four lines and means
the model follows if OSFI and CMHC ever diverge — which is the only reason both
pairs are seeded separately.

⚠️ **`ISBLANK ( Band )` on the insured branch is written and cannot fire
today.** Section 13.6 measured it: with the legality guard first, the band gap
above 95 % LTV is unreachable. It is written anyway, and this note is what
stops a later reader from deleting it as dead code — the same treatment the
sixth branch of `Verdict` received on 2026-08-31.

⚠️ **`MAX ( a, b )` here is the two-scalar form**, not the column aggregation.
It is DAX's `greatest()`, and it is what makes the floor a floor.

## 13.8 The verdict now has six classes, and the control changes with it

```dax
Verdict at this down payment =
VAR Areas    = COUNTROWS ( VALUES ( fact_mortgage_scenario[area_code] ) )
VAR Income   = 'Income input'[Income input Value]
VAR Regime   = [Down payment regime code]
VAR Required = [Income required at this down payment]
RETURN
    SWITCH (
        TRUE (),
        Areas > 1,  "Several areas selected",
        Regime = 0, "No published price",
        Regime = 1, "Cash purchase",
        Regime = 2, "Below the legal minimum",
        ISBLANK ( Required ), "Not evaluated",
        Income >= Required * 1.10, "Within reach",
        Income >= Required, "Borderline",
        "Out of reach"
    )
```

⚠️ **`Areas > 1` comes first, and it is the guard section 12.5 asked for on a
different card.** A median of two medians does not exist: with two sectors
selected, `AVERAGE ( median_price )` returns a number that belongs to no
property. The counting measures below are safe from it by construction —
they evaluate this measure once per sector inside a `FILTER` — but a card
reading it directly is not.

| Verdict | Colour | What it says |
|---|---|---|
| Cash purchase | `#9BD0F2` | the down payment covers the price; there is no loan, and the income does not matter |
| Within reach | `#4E9FD8` | the income clears the required figure by at least 10 % |
| Borderline | `#2A6CA3` | the income clears the required figure, but by less than 10 % |
| Out of reach | `#FF8A7E` | evaluated, and the income does not clear it |
| Below the legal minimum | `#A8722E` | **a refusal, not an absence.** The law does not allow this purchase at this down payment |
| No published price | `#E8EAEC` | APCIQ printed no median for this slice |

> ### ⚠️ These six colours replaced the previous five on 2026-09-12
>
> **Six classes now carry six colours.** The row above used to give
> `Cash purchase` and `Within reach` the same tone deliberately — a cash
> purchase being a special case of affordable. That was reversed on
> 2026-09-12, once the option had been seen drawn with a tone of its own. **To go
> back, give both `#4E9FD8`** and re-run the validator.
>
> **The palette was searched, not picked.** 33 candidates, every pair of every
> combination measured in the four views, 270 combinations cleared 10.0, and
> this is the one whose worst pair is highest: **14.3**, against 14.8 for the
> five-colour set it replaces — the same order, with one more class to place.
>
> **It was prompted by a defect, and the defect had three parts.** The measure
> that was in the model on 2026-09-12 read:
>
> | Pair | CIEDE2000 |
> |---|---|
> | `Cash purchase` / `Borderline` | **0.0** — the same hex |
> | `Within reach` `#E0F0FF` / `No published price` | **5.6** |
> | `Out of reach` / `Below the legal minimum` | **8.3** — two reds |
>
> ⚠️ **The second is the one that mattered**, and it is why the pale blue was
> asked about in the first place: **an affordable sector looked like a sector
> with no published price.** That is the worst sentence this map can utter.
>
> **The three favourable verdicts are now ordered by luminance** — 0.585,
> 0.314, 0.139 — so the ramp reads as a ramp on the dark theme. The refusal
> leaves the red family for an amber, which is what buys it **14.3** against
> *Out of reach* instead of 8.3.
>
> ⚠️ **One thing to watch on screen rather than here:** `Out of reach`
> `#FF8A7E` is *lighter* than `Within reach`. On a dark ground a red has to be
> light to exist at all, and the hue carries the meaning — but at the bottom of
> the down-payment slider almost every sector is out of reach, so the map will
> be largely coral. Judged on a contact sheet before it was chosen; judge it
> again in Desktop.

**The 10 % band is still a display convention of this project and still lives in
one measure only.** The counting measures below read *this* verdict rather than
repeating the comparison — the `Sector bar colour` principle, applied to the
KPI row as well. What they duplicate is the *label*, not the threshold, and a
renamed label fails loudly: the counts stop adding up to eighteen.

### The palette was measured, and the measurement found an inherited fault

`scripts/validate_palette.py` computes CIEDE2000 between every pair, in normal
vision and through all three dichromacies, and reports the **worst** of the
four. Its first run, on the four colours the page already had:

> `Out of reach` / `No published price` — **7.0 in deuteranopia**

Two greys separated by lightness alone, accepted by eye on 2026-08-30. Lightness
is the axis colour blindness leaves intact, which is why it looked safe — and
also the axis two light greys on a light background have almost none of. **Out
of reach therefore moves from `#C7CCD1` to `#A6ADB4`** in the same pass that
adds the fifth class.

| The five, measured — **superseded 2026-09-12, kept as the record** | |
|---|---|
| pairs tested | **10** |
| worst pair | **14.8** — Borderline / Out of reach, in protanopia |
| pairs below the threshold of 10 | **0** |

**The set in force is the six above**, measured the same way: 15 pairs, worst
**14.3**, none below the threshold. `python scripts/validate_palette.py
--palette page3-verdict` prints it.

Negative control run the same day: putting `#C7CCD1` back alongside the new set
still fails, at 7.0. ⚠️ **`#C7CCD1` remains correct on page 1**, where it is the
*Blank area* grey of a map with no second grey beside it. This is a page 3
change, not a project-wide one.

```dax
Sector bar colour =
SWITCH (
    [Verdict at this down payment],
    "Cash purchase",           "#9BD0F2",
    "Within reach",            "#4E9FD8",
    "Borderline",              "#2A6CA3",
    "Out of reach",            "#FF8A7E",
    "Below the legal minimum", "#A8722E",
    "#E8EAEC"
)
```

### The three counting measures

All three count over the same universe, and **they define it themselves rather
than inheriting it**:

```dax
The eighteen sectors, whatever the page is filtered on
=  CALCULATETABLE (
       VALUES ( fact_mortgage_scenario[area_code] ),
       REMOVEFILTERS ( Sector ),
       fact_mortgage_scenario[is_island_aggregate] = FALSE
   )
```

⚠️ **`REMOVEFILTERS ( Sector )` and the island exclusion are one gesture, and
splitting them is the fault.** These three cards must keep the island
denominator when a sector is selected — that is what section 12.4 asks for, and
"6 of 17" turning into "0 of 1" is why. But `REMOVEFILTERS ( Sector )` also
removes the **page filter** `Sector[geography_type] is apciq_sector`, and
`fact_mortgage_scenario` carries **19 area codes, one of them `island`**. Remove
the one filter without stating the other and every count silently gains the
island row: eighteen becomes nineteen, the arithmetic check stops adding up, and
nothing raises an error.

**This is the `RANKX` fault of 2026-08-31 in another costume.** There, ranking
over `ALLSELECTED ( Sector[name] )` let the island row slip in at rank 9 and
pushed every sector below it down a place, while the first rank stayed correct
and nothing looked broken. A measure whose correctness depends on a filter
somebody else has to remember to leave in place is not a measure, it is a trap.

```dax
Sectors within reach of this income =
VAR Sectors =
    CALCULATETABLE (
        VALUES ( fact_mortgage_scenario[area_code] ),
        REMOVEFILTERS ( Sector ),
        fact_mortgage_scenario[is_island_aggregate] = FALSE
    )
VAR Reached =
    COUNTROWS (
        FILTER (
            Sectors,
            CALCULATE ( [Verdict at this down payment], REMOVEFILTERS ( Sector ) )
                IN { "Within reach", "Cash purchase" }
        )
    )
RETURN IF ( ISBLANK ( Reached ), 0, Reached )
```

```dax
Sectors borderline =
VAR Sectors =
    CALCULATETABLE (
        VALUES ( fact_mortgage_scenario[area_code] ),
        REMOVEFILTERS ( Sector ),
        fact_mortgage_scenario[is_island_aggregate] = FALSE
    )
VAR Band =
    COUNTROWS (
        FILTER (
            Sectors,
            CALCULATE ( [Verdict at this down payment], REMOVEFILTERS ( Sector ) ) = "Borderline"
        )
    )
RETURN IF ( ISBLANK ( Band ), 0, Band )
```

```dax
Sectors below the legal minimum =
VAR Sectors =
    CALCULATETABLE (
        VALUES ( fact_mortgage_scenario[area_code] ),
        REMOVEFILTERS ( Sector ),
        fact_mortgage_scenario[is_island_aggregate] = FALSE
    )
VAR Refused =
    COUNTROWS (
        FILTER (
            Sectors,
            CALCULATE ( [Verdict at this down payment], REMOVEFILTERS ( Sector ) ) = "Below the legal minimum"
        )
    )
RETURN IF ( ISBLANK ( Refused ), 0, Refused )
```

⚠️ **`CALCULATE` around `[Verdict at this down payment]` inside the `FILTER` is
what makes it evaluate per sector.** Without it the measure would be computed
once, in the filter context of the whole card, where `Areas > 1` fires and the
verdict reads *Several areas selected* — so every count would come back zero,
on every slice, at every slider position. A firm and uniform zero is exactly
the kind of wrong answer that looks like a market rather than like a bug.

⚠️ **`REMOVEFILTERS ( Sector )` has to be repeated inside that `CALCULATE`,
and the first version of this section omitted it.** Found in Desktop on
2026-09-09, applying D7: with the slicer on one sector, the three cards moved
instead of holding. The `REMOVEFILTERS` in the `CALCULATETABLE` above protects
only the **construction of the universe** — the list of eighteen `area_code`
stays eighteen. The verdict inside the `FILTER` is then evaluated in the
**outer** filter context, where the slicer has left `Sector[name]` set: for the
seventeen other area codes the intersection *this area code* ∩ *that sector* is
empty, `Price` comes back blank, the regime reads 0 and the row is counted as
*No published price*. Eighteen rows are walked and seventeen are evaluated
against nothing. **Nothing raises an error, and the smaller figure is exactly
what a reader expects to see after narrowing a page** — which is why only the
acceptance gesture *select a sector and check the cards do NOT move* catches
it. The trimester and property-type filters are deliberately left in place;
only `Sector` is removed, in both spots.

**A cash purchase counts as within reach, and the tooltip is where the
difference is read.** It is the extreme case of affordable — no loan at all —
so counting it anywhere else would put a sector nobody needs an income for into
a column of sectors that are out of reach. It is unreachable on the most recent
quarter at every slider position, and reachable on the early quarters of the
archive: a page checked only on 2026 Q2 has not seen it.

**The `IF ( ISBLANK ( … ), 0, … )` is kept on all three.** `COUNTROWS` over an
empty table returns `BLANK()`, and a card that goes empty reads as broken where
a firm `0` reads as an answer. At 0 $ on the slider, two of these three
measures are legitimately zero on every slice.

⚠️ **The page's arithmetic check changes shape.** It was *four counts totalling
eighteen*. It is now **six**, and the two new ones are refusals. Measured on
2026-09-09 at seven slider positions and on all three property types: the six
classes total 18 in every one of the 21 combinations, with no exception.

## 13.9 `Down payment assumption`, rewritten

```dax
Down payment assumption =
VAR Down   = 'Down payment input'[Down payment input Value]
VAR Areas  = COUNTROWS ( VALUES ( fact_mortgage_scenario[area_code] ) )
VAR Price  = CALCULATE ( AVERAGE ( fact_mortgage_scenario[median_price] ) )
VAR Regime = [Down payment regime code]
VAR Amount = FORMAT ( Down, "#,##0 $" )
RETURN
    SWITCH (
        TRUE (),
        Areas > 1 || ISBLANK ( Price ),
            Amount & " down. The share of the price it represents differs by "
                & "sector — select one to read it.",
        Regime = 1,
            Amount & " down covers the whole published median price here: "
                & "a cash purchase, with no mortgage and no income requirement.",
        Regime = 2,
            Amount & " down is "
                & FORMAT ( DIVIDE ( Down, Price ), "0.0%" )
                & " of the published median price — below the legal minimum for "
                & "this price. No figure is shown, because the purchase is not "
                & "one a lender may make.",
        Regime = 3,
            Amount & " down is "
                & FORMAT ( DIVIDE ( Down, Price ), "0.0%" )
                & " of the published median price: at or below 80 % "
                & "loan-to-value, so uninsured and with no CMHC premium.",
        Amount & " down is "
            & FORMAT ( DIVIDE ( Down, Price ), "0.0%" )
            & " of the published median price: above 80 % loan-to-value, so "
            & "insured, and the CMHC premium is added to the loan."
    )
```

**The card was the thing that stopped the page implying it modelled savings.
Now that the page does model them, the card is what stops it implying the
figure is complete.** It names the amount, the share of the price, and the
regime — three things that change together at the 20 % threshold and that a
reader cannot infer from a bar chart.

⚠️ **It refuses to state a share when more than one sector is in context**, for
the reason section 13.8 gives: the share would be computed against a mean of
medians.

⚠️ **No example of its output is reproduced in this file.** The share is a typed
number divided by an APCIQ median, so printing one here would reproduce the
median indirectly. Read it on screen.

### ⚠️ This card is ALSO on page 2, and rewriting it broke that page

Found on 2026-09-09, reading `Report/Layout` after D8 was applied: page 2
carries a full-width `cardVisual` bound to `Down payment assumption` — a card
the page-2 element list above never mentioned. Once the measure became
dynamic, that card started announcing the typed down payment on a page whose
every figure is computed **in SQL at the legal minimum**. `Down payment input`
is not synchronised to page 2, so `SELECTEDVALUE` fell back to its default of
50 000 $ and the card stated it as fact.

⚠️ **The acceptance case *page 2 unchanged at every slider position* would not
have caught it.** No page-2 *figure* moves. A sentence did. A check that reads
only numbers walks straight past it.

**Page 2 gets its own measure**, carrying the exact text `Down payment
assumption` held before D8:

```dax
Down payment note =
"Assumes the legal minimum down payment for this price, insured. "
    & "A larger down payment is not modelled."
```

It reads neither `Down payment input` nor `fact_mortgage_scenario`, so page 2
is insensitive to the slider **by construction** rather than by care.

⚠️ **Reservation, written rather than forgotten**: that text says *insured*,
which is untrue of the scenarios at or above 1.5 M$, where the legal minimum of
20 % leaves the loan uninsured. The flaw predates this session and correcting it
would change what page 2 claims — out of scope for block D, to be picked up with
`limitations.md` in J4.4.

## 13.10 What changes on page 3

| Element | Before | After |
|---|---|---|
| Slicer | `Income input` | `Income input` **and `Down payment input`** |
| Bar | `Income required, lower bound (mean)` | **`Income required at this down payment`** |
| Bar colour | `Sector bar colour` | unchanged name, new body, five colours |
| Map colour | `Sector bar colour` | idem |
| Map / bar tooltips | `Verdict for this income` | **`Verdict at this down payment`**, plus `Down payment assumption` |
| Table | `Verdict for this income`, `Income required, lower bound (mean)` | the two measures above |
| KPI | within reach · borderline · of priced | **plus `Sectors below the legal minimum`** |
| Card | `Down payment assumption` | rewritten, section 13.9 |

⚠️ **`Income required, lower bound (mean)` is NOT deleted — page 2's KPI row
reads it.** The two coexist because they answer different scenarios on different
pages, and the rule that keeps them apart is simple: **they must never appear on
the same page.** On page 2 the down payment is the legal minimum; on page 3 it is
whatever the reader typed.

⚠️ **`Verdict for this income` is superseded by `Verdict at this down payment`,
and `Verdict for the selected place` was already renamed** by section 12.4.
Delete the old verdict **after** rebranching everything that reads it — the bar,
the map, the table, the colour measure, and `Verdict for the selected sector`.
Power BI reports a broken measure where it is *used*, not where it was deleted.

### Section 12.4, still outstanding, belongs in this same session

Applied nowhere as of 2026-09-09. It is page 3, so it is done here:

1. Synchronise the `Sector[name]` slicer of section 12.1 onto page 3 — pages
   **1 and 3**, never page 4.
2. Rename `Verdict for the selected place` to **`Verdict for the selected
   sector`**, and swap its test to `[Area is narrowed] = 1`.
3. Put `REMOVEFILTERS ( Sector )` on the three island KPI cards. **`Place` is
   gone, so `Sector` alone is now enough** — and it is the only form that still
   resolves.
4. Point `Verdict for the selected sector` at `[Verdict at this down payment]`.

## 13.11 Acceptance

Run the oracle, read the blocks titled **"PAGE 3 — The typed down payment"**.

```bash
.venv/Scripts/python.exe scripts/report_oracle.py
.venv/Scripts/python.exe scripts/report_oracle.py --down-payment 100000
```

**The counts below are counts of sectors, so they are written here.** Every
dollar figure on this page derives from an APCIQ median and is therefore printed
by the oracle at run time and nowhere else.

Most recent quarter, income **95 000 $**, the six verdicts read off the table:

| Down payment | Type | Within | Border | Out | Below min | Cash | No price |
|---|---|---|---|---|---|---|---|
| **0 $** | condominium | 0 | 0 | 0 | **17** | 0 | 1 |
| **25 000 $** | condominium | 6 | 1 | 2 | 8 | 0 | 1 |
| **50 000 $** *(default)* | condominium | **7** | **2** | **7** | **1** | 0 | **1** |
| 100 000 $ | condominium | 10 | 2 | 5 | 0 | 0 | 1 |
| 150 000 $ | condominium | 13 | 3 | 1 | 0 | 0 | 1 |
| 300 000 $ | condominium | 16 | 1 | 0 | 0 | 0 | 1 |
| **50 000 $** | plex | 0 | 0 | 0 | **9** | 0 | **9** |
| **50 000 $** | single-family | 0 | 0 | 5 | 9 | 0 | 4 |
| 300 000 $ | single-family | 4 | 2 | 7 | **1** | 0 | 4 |

**Every row totals 18.** That is the check to run first, and it is the one that
catches a measure applying its own threshold.

| Case | What must happen |
|---|---|
| **Slider at 0 $** | every priced sector reads *Below the legal minimum*; the bar chart is empty of bars and the KPI cards read a firm **0**, never blank |
| **Slider at 300 000 $, single-family** | **one sector still refuses.** The refusal branch is never empty, not even at the ceiling — those are the sectors whose median is at or above 1.5 M$, where the legal minimum is 20 % |
| **Slider at 100 000 $, condominium** | both regimes are on screen at once — nine sectors uninsured, eight insured. `Down payment assumption` must change its sentence as the map selection moves between them |
| **Two sectors selected** | `Verdict at this down payment` reads *Several areas selected*, and `Down payment assumption` refuses to state a share |
| **An early quarter at 300 000 $** | *Cash purchase* appears, coloured as within reach. It never appears on the most recent quarter at any slider position |
| **Page 2** | **unchanged at every slider position.** If a page 2 figure moves when the down payment slider moves, a page 3 measure has been dropped into the wrong page |

⚠️ **Dragging the slider is part of the acceptance, not a nicety.** The
constant line at `Income input Value` and the bars now move on two independent
axes, and the fault this page is exposed to is a card frozen on one of them
while the other moves — every figure right, the verdict false. That is the same
fault the typed constant line was warned about on 2026-08-30.

## 13.12 The page-3 map moves onto the 36 places

**2026-09-09, proposed while block C was being applied.** The map
now draws the same 36 administrative places as page 1, coloured by the verdict
of the APCIQ sector each one belongs to.

**It repairs a justification that had quietly expired.** The page-3 map section
above argues for eighteen sectors partly because the map *"reuses the shape file
of page 1 at no extra cost"*. That stopped being true on **2026-09-01**, when
page 1 moved to the 36 land-clipped places. From then until now the report drew
the island twice, with two different outlines, and the sentence that justified
the choice no longer described anything.

**Measured before the change, on the marts:**

| | |
|---|---|
| shapes in `marts.map_place` | **36** |
| APCIQ sectors they reach | **18** — all of them |
| shapes carrying no sector | **0** |
| sectors drawn by 1 shape · 2 · 4 · 7 | 9 · 6 · 2 · 1 |

That last row is the whole cost of the change, and it has to be stated rather
than discovered: **one sector can be seven shapes.** Sector 1 gathers seven
municipalities, so a single verdict paints seven polygons.

### The one real risk, and what answers it

On the acceptance slice — most recent quarter, condominium, 95 000 $, at the
legal minimum — **6 sectors within reach are painted as 12 shapes**, while the
KPI card beside the map reads **6**. Both are right, and a reader who counts
blue patches finds a third number.

**Page 1 did not carry this risk and page 3 does**, which is why it needs an
answer here: page 1's map paints a **price**, so nothing invites counting. Page
3 paints a **verdict**, and the KPI row counts verdicts a few centimetres away.

The answer is the pattern page 1 already established on 2026-09-01: **a static
text box under the map, carrying no figure at all.**

```text
Each shape is a borough or a linked city, coloured by the verdict of its APCIQ
sector — so neighbouring shapes share one published figure, and the number of
shapes is not the number of sectors. The line dividing Côte-des-Neiges from
Notre-Dame-de-Grâce is not published by APCIQ: the city's 2014 sociological
boundary stands in for it.
```

⚠️ **No figure, no count, no quarter in that box, ever.** A text box is filtered
by nothing and refreshes never. The middle clause is the one that defuses the
12-against-6: it tells the reader not to count patches. The last clause carries
the only assumed line on the map, exactly as page 1's box does.

⚠️ **A measure was proposed for that box and was wrong.** The argument for it —
"a frozen line would still say 36 the day the model holds 37" — only bites if
the line carries counts. It carries none, which is what makes a text box safe
here. Page 1 settled this on 2026-09-01 and the same ruling applies.

### The build

| Well | Field |
|---|---|
| Location | **`Place_map[place_code]`** |
| Format visual > Map settings > Add map | `powerbi/shapes/admin_place_island.geojson` |
| Colors > Location > `fx` > Format style | **Field value**, on `Sector bar colour` — unchanged measure |
| Tooltips | `Place_map[place_name]`, `Place_map[apciq_sector_name]`, the verdict, the required income |

⚠️ **Load the shape file into this visual even though page 1 already has it.**
A `shapeMap` carries **one** `map.geoJson` binding, read in the `.pbix`
definition on 2026-08-31. The two visuals hold their own copies.

⚠️ **Changing the Location field resets the `fx` colour binding.** Re-apply it
*after*, never before — done the other way round the map comes out in a single
colour and nothing says why.

⚠️ **`Tracts priced` leaves the tooltip.** At place grain it would print the
**sector's** tract count on a **place's** shape, and a reader takes it for that
place's. Same fault as `Min(Sector[name])` on the page-2 map, and harder to
catch because the number is plausible.

**The tooltip is two columns and no measure**, following page 1: the place name
and its sector answer *where does this figure come from* better than a sentence
does, and a tooltip past one line is not read at all. The columns resolve
because they belong to `Place_map` itself — no propagation involved, which is
the lesson page 2 paid for on 2026-09-02.

### Acceptance

Most recent quarter, 95 000 $, at the legal minimum — the state block C leaves:

| Condominium | Sectors | Shapes |
|---|---|---|
| Within reach | 6 | **12** |
| Borderline | 1 | 1 |
| Out of reach | 10 | 22 |
| No published price | 1 | 1 |
| **Total** | **18** | **36** |

Then switch to **plex: 24 shapes of 36 are grey** — the grey-dominant case, the
only one that shows whether an absence reads as an absence. `scripts/report_oracle.py`
prints both columns in its *KPI row AND map colours* block.

⚠️ **A map that comes out entirely grey is a join failure, not a colour
failure.** `place_code` must be **Text** in the model: the shape file's key is a
string, and a code typed as a number loads without error and matches nothing.
Same trap as `4620001.00` becoming `4620001` on the tract map.

## 13.13 `Verdict for the selected sector`

**It did not exist.** Section 12.4 says to *rename* `Verdict for the selected
place` — but that measure was step **B7** of block B, which stopped at B5 on
2026-09-01 and was then abandoned. Found on 2026-09-09, while applying
block C: without this card the sector slicer drives **nothing** on page 3 once
the interactions of C4 are set, and the block cannot be accepted.

```dax
Verdict for the selected sector =
VAR Chosen = COUNTROWS ( VALUES ( fact_affordability[apciq_sector_number] ) )
VAR SectorName = SELECTEDVALUE ( Sector[name] )
RETURN
    SWITCH (
        TRUE (),
        [Area is narrowed] = 0,
            "Select a sector to see whether it is within reach",
        Chosen > 1,
            Chosen & " sectors selected — a median of medians does not exist",
        SectorName & " — " & [Verdict at this down payment] & Sentence
    )
```

**Written in full, as applied on 2026-09-09 (block D11):**

```dax
Verdict for the selected sector =
VAR Chosen = COUNTROWS ( VALUES ( fact_affordability[apciq_sector_number] ) )
VAR SectorName = SELECTEDVALUE ( Sector[name] )
VAR Sectors =
    CALCULATETABLE (
        VALUES ( fact_mortgage_scenario[area_code] ),
        REMOVEFILTERS ( Sector ),
        fact_mortgage_scenario[is_island_aggregate] = FALSE
    )
VAR Scored =
    FILTER (
        ADDCOLUMNS (
            Sectors,
            "@required",
                CALCULATE ( [Income required at this down payment], REMOVEFILTERS ( Sector ) )
        ),
        NOT ISBLANK ( [@required] )
    )
VAR Evaluated = COUNTROWS ( Scored )
VAR Mine = [Income required at this down payment]
VAR Position = RANKX ( Scored, [@required], Mine, ASC, DENSE )
VAR Sentence =
    IF (
        NOT ISBLANK ( Mine ) && Evaluated > 0,
        " — " & Position & " of " & Evaluated & " by required income",
        ""
    )
RETURN
    SWITCH (
        TRUE (),
        [Area is narrowed] = 0,
            "Select a sector to see whether it is within reach",
        Chosen > 1,
            Chosen & " sectors selected — a median of medians does not exist",
        SectorName & " — " & [Verdict at this down payment] & Sentence
    )
```

**The rank ascends: rank 1 is the lowest required income**, so the most
reachable sector. **The denominator is computed, never written down.** "of 17"
was the count at the legal minimum; at 50 000 $ on condominium only **16**
sectors carry a calculable required income — the other two are a refusal and an
absent price. A hard-coded denominator would be wrong at every other slider
position.

⚠️ **`REMOVEFILTERS ( Sector )` appears twice here too**, for the reason 13.8
gives. Without it in the inner `CALCULATE`, the ranking universe collapses to
the selected sector and the rank reads 1 whatever is chosen.

⚠️ **The variable is `Position`, not `Rank`.** `RANK` is a DAX function and a
variable of that name has the expression rejected — the **fourth** collision of
this kind in the project, after `Name` in this very measure, `Current` in DAX on
2026-09-02 and `trailing` in PostgreSQL in J3.5.

**When the chosen sector is not evaluable** — below the legal minimum, or with
no published price — `Mine` is blank and the rank sentence disappears on its
own. No rank is invented for a sector that carries no figure.

⚠️ **`NAME` is a reserved word in DAX.** The variable was first written `Name`
and the expression was rejected. Third collision of this kind in the project,
after `Current` in DAX on 2026-09-02 and `trailing` in PostgreSQL in J3.5. The
**column** `Sector[name]` stays valid — inside brackets the parser is not
looking for a keyword.

**The three branches, in this order:**

⚠️ **`[Area is narrowed] = 0` first**, and it reads that measure rather than
`ISFILTERED` for the reason section 11.2 gives: `ISFILTERED` only sees a filter
placed *directly* on the column it names, so a **click on a bar** — which
reaches `Sector` by propagation — would leave it FALSE and the card would go on
inviting the reader to choose a sector that is visibly chosen. That click is the
acceptance case that proves it.

⚠️ **`Chosen > 1` second.** The slicer allows multiple selection, and with two
sectors `[Verdict for this income]` averages two required incomes into a figure
belonging to no property. The card refuses, exactly as `Median price` refuses on
page 1 — and section 12.5 asked for that refusal on this page.

**The name is printed with the verdict.** On a page where the slicer, a bar and
a map can each have designated something, a verdict without its subject reads as
a verdict about the island.

**The rank was added in D11, on 2026-09-09**, once `[Verdict at this down
payment]` existed to be ranked on. ⚠️ **No DAX for it had been written** — this
section announced it and stopped. Written above, in full.

---

# 14. J4.2¾ · 4 — The quarter-over-quarter badges

> ⚠️ **THE COMPARISON WINDOW OF THIS SECTION IS SUPERSEDED BY SECTION 16
> (2026-09-17): the badges compare the same quarter ONE YEAR EARLIER.** What
> 14.1 records as decided was reversed after the badges were read on screen, and
> 16.1 carries the measurement that settles it. **Three functions are renamed**
> — `ValueOneQuarterEarlier` → `ValueOneYearEarlier`, `QuarterBadge` →
> `YoYBadge`, `QuarterBadgeColour` → `YoYBadgeColour` — so every `-3` and every
> `QuarterBadge` below is the historical version. **Take the DAX from 16.3.**
>
> Everything else here stands and is not repeated in 16: the mechanism (14.2),
> the query that tests the functions before saving (14.2 bis), the colour
> convention (14.4), the measured palette (14.5), the ways a badge must be
> absent (14.6), the icons (14.8, 14.8 bis) and the build notes (14.10).

> **Specified 2026-09-10. Nothing in dbt moves** — every figure below already
> exists in `fact_market` and `fact_affordability`. This section is DAX,
> formatting, and one page of refusals. The build stays at PASS=353 and 140
> pytest, and `git status` on `dbt/` is how that claim is checked.

**"Badge" is this file's word, not Power BI's.** It means the small line under a
card's main figure -- what Power BI calls a **reference label**, and what reads
as "▲ 4.2 % vs 2026 Q1" on screen. Three things are wired per card: the icon
beside the big number (*Callout > Image*), the badge text (*Reference labels >
Add label*), and its colour (the **fx** on that label).

Seven KPI cards gain a small line under the figure: how the same measure stood
**one calendar quarter earlier**, as a signed percentage (or in points, where a
percentage would be wrong), coloured, with an arrow, and **naming the quarter it
compares to**.

## 14.1 What was asked, what was measured, and what was decided anyway

The request was a variation against the previous quarter. **The measurement
argued against it and the choice was confirmed**, so that is what this section
builds. The argument is written down here rather than discarded, because it
decides two things that follow: what the badge is allowed to claim, and what has
to sit on screen beside it.

**Three of the four page-1 metrics are seasonal, and the fourth is not.**
Measured on the island row, twenty-one transitions of each kind (seven years ×
three property types):

| Metric | Q1 → Q2 | Q2 → Q3 | Reads as |
|---|---|---|---|
| Sales | **18 rises of 21** | **18 falls of 21** | the calendar |
| Active listings | **19 rises of 21** | 6 rises of 21 | the calendar |
| Days on market | **2 rises of 21** | 16 rises of 21 | the calendar |
| **Median price** | 19 of 21 | 13 of 21 | a trend, not a season |

A badge on sales will be green every spring and red every summer whatever the
market does. That is not a defect to be fixed in DAX — it is what a sequential
comparison of a seasonal series *is*. The answer is not to hide it but to
**name it on screen**, which 14.9 does, and to **name the quarter in the badge
itself** so the reader is never told merely "up" but always "up on 2026 Q1".

**⚠️ There is a year-over-year figure sitting unused in the mart, and it is a
published one.** `fact_market` has carried five `*_change_pct_yoy` columns since
J3.5 — the percentages APCIQ prints, « par rapport au même trimestre de l'année
précédente », never recomputed. Coverage is **87 of 87 on the island row** for
all four page-1 metrics, and 1 211 to 1 418 of 1 566 on the sectors. It is an
observation; what this section builds is a derivation. Two measurements say why
they are not interchangeable, and both are worth keeping:

- **Recomputing the year-over-year change from our own levels does not
  reproduce the published one.** Island sales: **31 exact agreements of 75**
  after rounding to the integer APCIQ prints, mean **signed** gap **+0.68
  point** — the published figure systematically the larger. That is the J3.5
  vintage finding seen from the other end: APCIQ divides by a year-ago figure it
  has since revised downward, and we hold the first publication. On median price
  the same test gives 834 of 992 and a signed gap of ≈ 0, so it is the
  **counts** that drift, not the medians.
- **The published figure covers more, including a quarter no arithmetic can
  reach**: 1 211 published price changes against 1 110 computable
  quarter-over-quarter, and it exists on **2019 Q2**, where there is no 2019 Q1
  in the model to subtract.

**⚠️ The published columns are integers.** The staging model casts
`change_percent_text` with `::int` after stripping everything but digits and a
minus sign. Swept over the whole raw table, **no cell carries a decimal mark** —
every shape is `NN%`, `-N%`, `NNN%` and their spaced variants. So the cast is
safe, and any future comparison against them must round before it compares. A
test written to 0.15 point will fail on arithmetic that is perfectly correct.

**None of that is thrown away.** The reference label of the new card visual has
a second level, `Detail`. If the year-over-year figure is ever wanted, it goes
there, reading `median_price_change_pct_yoy` directly, and no measure below
changes.

## 14.2 The previous quarter is decided in exactly one place

Seven badges, seven colours, and three notes would otherwise hold seven copies
of one rule. **DAX user-defined functions are generally available since June
2026** and this model runs on Desktop **2026.08**, so the rule is a function.

⚠️ **THREE names in these eleven lines collide with DAX built-ins, and two of
them were found the hard way on 2026-09-10.** `PREVIOUSQUARTER` is a function,
so the first one cannot be called `PreviousQuarter`. **`NOW` is a function**, so
no variable may be called `Now`. **`EARLIER` is a function** — the one from
calculated columns — so no variable may be called `Earlier` either, which is how
a rename from `Before` (itself a visual-calculation keyword, with `AFTER` and
`CURRENT`) moved the error instead of fixing it.

⚠️ **An error that follows a rename is still about the name.** Both names were
reserved, which made a single symptom look like two different causes and sent
the first reading of it in the wrong direction. Sixth, seventh and eighth
collisions of this kind on this project, after `trailing` in PostgreSQL,
`Current`, `Name` and `RANK`. **The habit is now to check a name against the DAX
function list before typing the body, not after.**

Create these in **TMDL view** (*Apply*) or **DAX query view** (*Update model*).
They land under *Functions* in Model explorer.

```tmdl
createOrReplace
	/// The same measure, re-evaluated on the calendar quarter before the one in
	/// filter context. BLANK when the context does not hold exactly one quarter.
	/// @param {AnyRef} m - the measure to re-evaluate
	/// @returns its value one quarter earlier, or BLANK
	function ValueOneQuarterEarlier = (m : ANYREF) =>
		VAR ThisQuarterStart = SELECTEDVALUE ( 'date'[quarter_start_date] )
		VAR EarlierQuarterStart = EDATE ( ThisQuarterStart, -3 )
		RETURN
			IF (
				NOT ISBLANK ( ThisQuarterStart ),
				CALCULATE (
					m,
					REMOVEFILTERS ( 'date' ),
					'date'[date_key] = EarlierQuarterStart
				)
			)
```

**Four things in eleven lines, each of which would otherwise be a separate
guard.**

- **`SELECTEDVALUE ( 'date'[quarter_start_date] )` buys the multi-quarter guard
  for nothing.** Every one of the ninety-odd rows of `'date'` inside one
  selected quarter carries the *same* `quarter_start_date`, so `SELECTEDVALUE`
  returns it. Select two quarters and it returns BLANK, the badge vanishes, and
  no card ever compares a two-quarter aggregate to a one-quarter figure. The
  quarter slicers are `strictSingleSelect` on pages 1, 2 and 3 — read out of
  `Report/Layout` — so this should never fire. It is written because a slicer
  setting is one click from being changed and a wrong badge would not look
  wrong.
- **`REMOVEFILTERS ( 'date' )` before re-filtering, and it is not optional.**
  The slicer filters `'date'[quarter_label]`, a *text* column. Leaving it in
  place and adding a date filter intersects "2026 Q2" with the days of 2026 Q1
  and returns the empty set — the badge would be blank on every card, always,
  with nothing to diagnose.
- **The re-filter is on `date_key`, not on `quarter_start_date`.** All five
  relationships run from `'date'[date_key]` to a fact column that holds the
  quarter's first day (`powerbi/README.md` §5). Filtering `date_key` to that one
  day leaves exactly one row of `'date'` standing and reaches exactly one fact
  row per geography. Filtering `quarter_start_date` would work too, by leaving
  ninety rows of which one matches — the same answer through a mechanism nobody
  should have to reason about twice.
- **`EDATE ( .., -3 )` handles the year boundary and cannot land on a short
  month**, because a quarter always starts on the first.

✅ **Verified in DAX query view on 2026-09-10: this works.** The parser accepts
all three and the query runs. That matters because `QuarterBadge` hands its own
`expr` parameter on to `ValueOneQuarterEarlier`, another `expr` parameter —
nesting UDFs is documented, **forwarding an unevaluated expression from one lazy
parameter into another is not**, and the reference warns of parser
inconsistencies in exactly that area. It was tested before fourteen measures
were laid on top, which is what 14.2 bis exists for.

Two more functions compose what the reader sees, so each of the fourteen
measures below is a single line. **They go in the same script, below the
first** — `createOrReplace` appears once, at the top.

```tmdl
	/// The badge text for a measure: arrow, size of the change, and the quarter
	/// it is measured against. BLANK whenever the comparison cannot be made.
	/// @param {AnyRef} m - the measure to compare
	/// @param {String} unitMode - "percent", "points" or "count"
	/// @returns e.g. "▲ 4.2 % vs 2026 Q1", or BLANK
	function QuarterBadge = (m : ANYREF, unitMode : STRING) =>
		VAR Latest = m
		VAR PriorValue = ValueOneQuarterEarlier ( m )
		VAR EarlierLabel =
			CALCULATE (
				SELECTEDVALUE ( 'date'[quarter_label] ),
				REMOVEFILTERS ( 'date' ),
				'date'[date_key] = EDATE ( SELECTEDVALUE ( 'date'[quarter_start_date] ), -3 )
			)
		VAR Movement =
			SWITCH (
				unitMode,
				"percent", DIVIDE ( Latest - PriorValue, PriorValue ),
				Latest - PriorValue
			)
		VAR Marker = SWITCH ( TRUE (), Movement > 0, "▲ ", Movement < 0, "▼ ", "— " )
		VAR Magnitude =
			SWITCH (
				unitMode,
				"percent", FORMAT ( ABS ( Movement ) * 100, "0.0" ) & " %",
				"points",  FORMAT ( ABS ( Movement ) * 100, "0.0" ) & " pts",
				FORMAT ( ABS ( Movement ), "#,0" )
			)
		RETURN
			IF (
				NOT ISBLANK ( Latest ) && NOT ISBLANK ( PriorValue )
					&& NOT ( unitMode = "percent" && PriorValue = 0 ),
				Marker & Magnitude & " vs " & EarlierLabel
			)

	/// The badge colour. higherIsBetter says which direction is good FOR A
	/// FIRST-TIME BUYER, which is not the same as "up".
	/// @param {AnyRef} m - the measure the badge is about
	/// @param {Boolean} higherIsBetter - TRUE when a rise favours the buyer
	/// @returns a #RRGGBB string, or BLANK when there is no badge to colour
	function QuarterBadgeColour = (m : ANYREF, higherIsBetter : BOOLEAN) =>
		VAR Latest = m
		VAR PriorValue = ValueOneQuarterEarlier ( m )
		VAR Movement = Latest - PriorValue
		VAR Favourable = IF ( higherIsBetter, Movement > 0, Movement < 0 )
		RETURN
			IF (
				NOT ISBLANK ( Latest ) && NOT ISBLANK ( PriorValue ),
				SWITCH (
					TRUE (),
					Movement = 0,  "#8FA3B5",
					Favourable,    "#B8E0C5",
					"#FA584C"
				)
			)
```

⚠️ **THE `* 100` WAS MISSING WHEN THIS WAS FIRST WRITTEN, AND SIX OF THE SEVEN
BADGES SHIPPED WRONG (found 2026-09-11).** `DIVIDE ( Latest - PriorValue,
PriorValue )` is a **fraction** — 0.042 for a rise of 4.2 % — and
`FORMAT ( 0.042, "0.0" )` is the string `"0.0"`. Every percent badge read
`▲ 0.0 %` or `▲ 0.1 %`; only `Tracts evaluated change`, the one in `"count"`,
was right. **It was found on screen, by reading four badges that all
claimed a tenth of a percent.**

**It is a defect of this section, not of the build** — the DAX in Desktop was a
faithful copy of what was written here. Two things follow. The acceptance case
that would have caught it exists and is precise — case 2, *"matching the oracle
to one decimal"* — and **it had not been run yet**: the badges were wired,
looked plausible and were believed. And the fault is the reverse of every other
one this project has found: it **did** show, loudly, in the only place a reader
looks. A percentage stuck at 0.0 across four unrelated cards is not a subtle
fault; it survived twenty-four hours because nobody had compared it to anything.

⚠️ **`"points"` expects a measure that is a proportion between 0 and 1** — that
is the function's contract, and the `* 100` in that branch is what makes it one.
`Share of tracts affordable` is a `DIVIDE`, so 0.781, and the badge must read
`43.1 pts`, not `0.4 pts`. `"percent"` needs no such assumption: a relative
change is a fraction whatever the measure's own scale is.

⚠️ **`Movement` itself is deliberately left unscaled.** The arrow and
`QuarterBadgeColour` both read only its **sign**, which no multiplication
changes. Scaling the display and not the value keeps the two functions in
agreement about when a badge exists and which way it points — scaling `Movement`
would have been the same number of characters and one more thing to keep in step.

⚠️ **`ABS` in the text and the sign in the arrow, deliberately.** A badge
reading `▼ -4.2 %` says the same thing twice and reads as a double negative. The
arrow carries the direction; the number carries the size.

⚠️ **The two functions re-evaluate `Before` independently.** That is one extra
evaluation per card, on a model of 1 653 rows, and it buys something worth more:
neither function can be used without the other agreeing on when a badge exists.
Passing the value between them would mean a third measure per card.

## 14.2 bis The query that tests the functions before they are saved

**DAX query view, not TMDL view** — it is the one place in the Power BI half of
this project where something can be evaluated *without* being written into the
model. TMDL view has *Apply*, which saves first and asks questions later.

**The query is already in the file.** It was written on 2026-09-10 and Power BI
keeps query tabs inside the `.pbix`, at `DAXQueries/Requête 1.dax`. Open the
report, go to DAX query view, and the three functions are there as typed.

```dax
DEFINE
    FUNCTION ValueOneQuarterEarlier = ( m : ANYREF ) => …
    FUNCTION QuarterBadge           = ( m : ANYREF, unitMode : STRING ) => …
    FUNCTION QuarterBadgeColour     = ( m : ANYREF, higherIsBetter : BOOLEAN ) => …

EVALUATE
SUMMARIZECOLUMNS (
    'date'[quarter_label],
    TREATAS ( { "Condominium" }, property_type[name_en] ),
    "Now",    [Sales (island, as published)],
    "Before", ValueOneQuarterEarlier ( [Sales (island, as published)] ),
    "Badge",  QuarterBadge ( [Sales (island, as published)], "percent" ),
    "Colour", QuarterBadgeColour ( [Sales (island, as published)], FALSE )
)
ORDER BY 'date'[quarter_label]
```

The bodies are in 14.2. What matters here is the **shape**: `Now` and `Before`
beside the `Badge` that is derived from them, so the badge can be checked
against its own inputs on the same row, with no oracle and no second screen.

**What it must return**

| Column | Must read |
|---|---|
| `Now`, `Before` | the measure, and the measure one quarter earlier. The first quarter of the archive has a `Now` and **no** `Before` |
| `Badge` | `▲`/`▼`/`—`, a size, ` vs `, and the label of the quarter in `Before` |
| | **and the size must equal `\|Now − Before\| / Before` as a percentage** — check one row by hand |
| `Colour` | `#B8E0C5`, `#FA584C` or `#8FA3B5`, and BLANK on exactly the rows where `Badge` is blank |
| First row | `Badge` and `Colour` both **blank**. Nothing precedes the first quarter |

⚠️ **DO NOT PASTE THE OUTPUT ANYWHERE.** `Now` and `Before` are APCIQ sales
counts. Same rule as `scripts/report_oracle.py`: read it on screen, close it.

**Then, and only then**, the *Update model with changes* link above `DEFINE`.

### The scale check, which needs no data at all

⚠️ **This is the one that was skipped on 2026-09-10, and it costs two lines.**

```dax
EVALUATE
ROW (
    "as first written", FORMAT ( 0.042, "0.0" ) & " %",
    "as written now",   FORMAT ( 0.042 * 100, "0.0" ) & " %"
)
```

`0.0 %` and `4.2 %`. `DIVIDE` returns a **fraction**, and a format string is not
a multiplication: `"0.0"` rounds 0.042 to one decimal and gets zero. Every
percent badge in the report read `0.0 %` or `0.1 %` for a day because of it.

**The check that would have caught it was already on screen.** The query above
prints `Now` and `Before` next to `Badge`. On 2026-09-10 it was read for one
question — *does the parser accept a UDF that forwards an `expr` parameter into
another UDF* — and the answer was yes, so the tab was closed. **The columns that
disagreed were in the same table, unread.** A query that returns three things
answers three questions only if three are asked.

### Three things that make this tab fail for reasons that are not the DAX

- ⚠️ **Clear the tab before pasting.** DAX query view opens with a sample query
  in it and `DEFINE` must precede every `EVALUATE`. Pasting underneath gives
  *The syntax for 'DEFINE' is incorrect*, pointing at your `DEFINE` rather than
  at the sample that caused it.
- ⚠️ **User-defined functions need compatibility level 1702.** If the model
  refuses them outright, look there before suspecting the syntax.
- ⚠️ **Three names in these bodies collide with DAX built-ins**: no function
  called `PreviousQuarter`, no variable called `Now` or `Earlier`. The variables
  here are `Latest` and `PriorValue` for that reason, and the column headers in
  the `EVALUATE` are strings, which is why `"Now"` is allowed there and
  `VAR Now` is not.


## 14.3 The fourteen measures

Each is one line. Nothing but the measure reference and two flags changes, and
that is the point — **the rule they share is above, not repeated here.**

**Page 1 — Market.** The measure inside the badge is the `(selected area)`
wrapper, not the bare measure, so the badge follows the sector slicer exactly as
the card above it does. Reading the bare measure would produce a badge about the
island under a figure about one sector.

```dax
Sales change            = QuarterBadge ( [Sales (selected area)], "percent" )
Sales change colour     = QuarterBadgeColour ( [Sales (selected area)], FALSE )

Price change            = QuarterBadge ( [Median price (selected area)], "percent" )
Price change colour     = QuarterBadgeColour ( [Median price (selected area)], FALSE )

Time on market change   = QuarterBadge ( [Days on market (selected area)], "percent" )
Time on market colour   = QuarterBadgeColour ( [Days on market (selected area)], TRUE )

Listings change         = QuarterBadge ( [Active listings (selected area)], "percent" )
Listings change colour  = QuarterBadgeColour ( [Active listings (selected area)], TRUE )
```

**Page 2 — Affordability.**

```dax
Share change            = QuarterBadge ( [Share of tracts affordable], "points" )
Share change colour     = QuarterBadgeColour ( [Share of tracts affordable], TRUE )

Tracts evaluated change = QuarterBadge ( [Tracts evaluated], "count" )
Tracts evaluated colour = "#8FA3B5"

Required income change        = QuarterBadge ( [Income required, lower bound (mean)], "percent" )
Required income change colour = QuarterBadgeColour ( [Income required, lower bound (mean)], FALSE )
```

⚠️ **`Share of tracts affordable` is in POINTS, never in percent.** A share that
goes from 40 % to 44 % has risen four points and ten percent, and the two
sentences are both true and describe different things. Section 41.2 of the brief
is about exactly this kind of quiet ambiguity.

⚠️ **`Tracts evaluated colour` is a constant grey, and it is the most important
line in this block.** That card is the **denominator**, not a result: more
tracts evaluated is neither good nor bad news, it means the base of comparison
moved. Colouring it would say the model got better or worse when only APCIQ's
coverage changed. It carries a badge — with an arrow and a count — because the
reader needs to see the base move; it never carries a verdict.

**The denominator does move, and far more than one would guess.** Across 28
transitions on the couple profile:

| Type | Quarters where the denominator held | Mean absolute move | Worst |
|---|---|---|---|
| Condominium | 16 of 28 | 8.4 tracts | — |
| Plex | **2 of 28** | 40.6 tracts | — |
| Single-family | **3 of 28** | 85.0 tracts | **−258** |

On single-family, a share that moves ten points can be entirely the arrival or
departure of 258 tracts from the calculation. Without the grey badge beside it,
nothing on the page would say so.

## 14.4 Green means favourable to a first-time buyer

**Decided on 2026-09-10, against the convention the project's own mock-ups
use.** On the fourth mock-up, `Days on Market 54 ▼ −18 %` is red. On a tool
built to answer *where can a first-time buyer still buy*, a market that sells
faster is worse news, not better: less time to decide, more competition. And
"green = up" would paint a rising median price green on a page about
affordability.

| Card | A rise means | Flag |
|---|---|---|
| Sales | more competition for the same stock | `FALSE` |
| Median price | it costs more | `FALSE` |
| Days on market | **more time to decide** | `TRUE` |
| Active listings | **more to choose from** | `TRUE` |
| Share of tracts affordable | more of the island within reach | `TRUE` |
| Income required, lower bound | a higher bar to clear | `FALSE` |
| Tracts evaluated | *nothing* — it is the denominator | *never coloured* |

**This convention is declared on screen**, in `Colour convention note` (14.9).
An unexplained green on a falling price reads as a bug.

⚠️ **The colour is never the only carrier.** Every badge starts with ▲, ▼ or —.
A reader who sees no colour at all still reads the direction, which is what
makes the palette below a refinement rather than a dependency.

## 14.5 The palette, measured on the theme this report actually uses

**⚠️ The report is on a dark theme and that changes the whole answer.**
`Montreal Immobilier - Executive PropTech Dark`, canvas `#0E1A25`, visual
background `#192A3A`, read out of the `.pbix`. Colours picked for a white page
are the wrong colours here, and none of the obvious candidates survives.

Run through `scripts/validate_palette.py` — CIEDE2000 across normal vision and
the three dichromacies, threshold 10:

| Candidate | Worst pair | Verdict |
|---|---|---|
| The theme's own `good` / `bad` / `neutral` | **2.2** — bad vs neutral in tritanopia | FAIL |
| Fluent green `#107C10` / red `#A80000` | **4.2** in deuteranopia | FAIL |
| Okabe-Ito teal / vermilion | 6.6 in deuteranopia | FAIL |
| Theme `good` / `bad` with a grey neutral | 8.5 in deuteranopia | FAIL |
| **`#B8E0C5` / `#FA584C` / `#8FA3B5`** | **24.0** | **PASS** |

**Red and green collapse onto one axis in protanopia and deuteranopia — that is
what those conditions are.** The only thing left to separate them with is
*lightness*, and on a dark background every usable colour has to be light, which
spends most of the lightness range before the palette starts. The pair that
passes is therefore a **pale** green against a **mid** red, and it is still a
green (hue 140) and still a red (hue 4): a search over 5 696 passing
combinations returned this as the least drifted from canonical green and red.

| Role | Colour | L\* | Contrast on `#192A3A` | Contrast on `#0E1A25` |
|---|---|---|---|---|
| Favourable | `#B8E0C5` | 86 | 10.12 : 1 | 12.16 : 1 |
| Unfavourable | `#FA584C` | 60 | 4.58 : 1 | 5.50 : 1 |
| Flat, and the denominator badge | `#8FA3B5` | 66 | 5.63 : 1 | 6.77 : 1 |

All three clear WCAG 4.5 : 1 for normal text on the darker of the two
backgrounds.

⚠️ **This palette is FOR THE DARK THEME and fails on a light one.** `#B8E0C5`
on white is **1.45 : 1** — invisible. If the theme is ever swapped, these three
values are the first thing to remeasure, and `validate_palette.py --palette
page1-badge` is how.

✅ **The theme WAS swapped, and the palette was remeasured on 2026-09-11 rather
than assumed to survive.** `v10` runs *Montreal Immobilier — Reference Dark v3*,
read out of the `.pbix`: canvas still `#0E1A25`, visual background **`#192938`**
instead of `#192A3A`. The two backgrounds are **CIEDE2000 0.5** apart — one
colour, as far as a reader is concerned — and every badge colour still separates
from the panel by at least **39.8**, the closest being the red in protanopia.
The three badge-against-badge pairs are untouched at 24.0, 14.1 and 32.6. **The
palette holds.** What the new theme actually adds is `listSlicer` and
`advancedSlicerVisual` styling, which is why the slicers changed and the badges
did not.

⚠️ **A thing to look at in Desktop, not decided here.** The same measurement,
turned on the palettes already in the report, puts `page2-off-ramp`'s
`#0d366b` at **1.23 : 1** and CIEDE2000 **10.2** against the visual background,
and `page3-verdict`'s `#17527A` at 1.76 : 1. Those were chosen on 2026-09-02 and
2026-09-09 without the theme in the measurement. **This is not a verdict** — a
shape map may paint on its own background, and Desktop is the authority (the
`albersUsa` lesson of 2026-09-01). **Look at the deepest blue on the page-2 map
and say whether it reads.** If it does not, that is its own session, not this
one.

## 14.6 Five ways a badge must be ABSENT rather than zero

This is the **ninth and tenth appearance** of the blank/zero trap on this
project, and the shape is always the same: DAX compares BLANK as if it were 0,
so a missing previous quarter becomes "−100 %" or "0.0 %" instead of nothing.

| # | Situation | What a naive measure shows | Handled by |
|---|---|---|---|
| 1 | 2019 Q2 — the first quarter in `fact_market`, nothing before it | `▼ 100.0 %` | `ISBLANK ( Before )` |
| 2 | A sector priced this quarter and not last | `▲ …` from zero | `ISBLANK ( Before )` |
| 3 | Two quarters selected | a one-quarter comparison under a two-quarter figure | `SELECTEDVALUE` returning BLANK |
| 4 | A previous value of exactly 0 | division error, or ∞ | `Before = 0` in percent mode |
| 5 | Active listings on a quarter APCIQ contradicts | a change derived from a figure the mart declares unreliable | 14.7 |

**Cases 1 and 3 fire on the island; case 2 fires only on sectors, and it is the
acceptance case worth running.** Measured across the archive:

| Where | Transitions | Badges that must vanish |
|---|---|---|
| Island, all four metrics | 84 | **0** |
| Sectors, condominium price | 504 | 6 |
| Sectors, plex price | 504 | **24** |
| Sectors, single-family price | 504 | **35** |

So the island never exercises the guard and the report looks finished without
it. **Select a sector on plex and step through the quarters** — that is where a
badge has to disappear, 24 times.

## 14.7 The listings badge refuses a contradicted quarter

> ⚠️ **SUPERSEDED for the measure, still true for the mechanism.**
> `Listings change` is no longer on any card — 16.4 replaced the active-listings
> card with months of inventory, and moved the refusal onto the **value** rather
> than the badge. This section is kept because it is the report's only worked
> example of a corroboration guard, and because 16.4 explains itself by
> contrast with it.

`fact_market` carries `active_listings_corroboration`, three states, from J3.2:
1 425 rows `corroborated`, 168 `contradicted_on_its_page`, 60
`not_reconciled_across_pages`. The negative verdicts sit on **2021 Q4, 2022 Q1,
2022 Q2 and 2023 Q4** — the editions declared defective in J3.2, where active
listings reconcile nowhere.

**A change derived from two figures, one of which the mart says is unreliable,
is not a change.** And the three defective inventory quarters are *adjacent*, so
a sequential comparison is contaminated on both sides of each:

```dax
Listings change =
VAR ThisOne = SELECTEDVALUE ( fact_market[active_listings_corroboration] )
VAR PriorOne =
    CALCULATE (
        SELECTEDVALUE ( fact_market[active_listings_corroboration] ),
        REMOVEFILTERS ( 'date' ),
        'date'[date_key] = EDATE ( SELECTEDVALUE ( 'date'[quarter_start_date] ), -3 )
    )
RETURN
    IF (
        ThisOne = "corroborated" && PriorOne = "corroborated",
        QuarterBadge ( [Active listings (selected area)], "percent" ),
        "inventory not reconciled this quarter"
    )
```

`Listings change colour` gets the same guard, returning `"#8FA3B5"` on the
refusal so the sentence is not painted as a verdict.

**Six quarters lose the badge**: 2021 Q4, 2022 Q1, 2022 Q2 and 2023 Q4 for their
own figure, plus **2022 Q3 and 2024 Q1** because the quarter they subtract is
defective. Two of those six are quarters whose own inventory figure is fine —
which is the whole point, and which no guard written on the current quarter
alone would catch.

⚠️ **This makes `Listings change` the one measure that is not a one-liner**, and
it is written out here in full rather than described as "the same shape as the
others". That shortcut was taken on 2026-09-01, three measures were left
unwritten, and only a reader noticed.

## 14.8 The callout icons

The card visual takes an image inside the callout from a measure, when the
measure returns a data URI and its **data category is set to Image URL**. So the
icons are DAX, versioned in this file, with no file to lose and nothing to
attribute.

**Seventeen are drawn here since 2026-09-17, of which fifteen are in use** —
rather than lifted from Lucide or Feather. 24 × 24, 1.6 px, round caps,
**stroke only with one stated exception: the quote mark is filled**, for the
reason measured below.

⚠️ **`Active listings icon` and `Tracts evaluated icon` are orphaned by section
16** — the cards they sat on now hold months of inventory and the median tract
income. They are kept here and deleted from the model, for the reason in 16.6:
the document keeps the memory, the model stays clean.

> ### The colour changed on 2026-09-12: `#8FA3B5` → **`#B4C8DA`**
>
> Changed on request, for something harmonised and slightly more
> vivid. **The old colour was the badge's own "flat" grey**, so an icon and a
> state of the data carried the same hue — at CIEDE2000 **0.0**. That alone
> justified moving.
>
> Six candidates were measured against the three badge colours, the three map
> ramps and the real card background `#1C2F41`. **None passes everywhere: this
> report has spent its blue.** Every scale in it is blue, so any vivid blue
> collides with a ramp — `#85C9F4`, the theme accent, lands at ΔE **2.4** from
> the blue arm's threshold colour on page 2.
>
> | | contrast on the card | vs the green and red badges | worst collision |
> |---|---|---|---|
> | `#8FA3B5` old | 5.27 : 1 | 14.1 | **0.0** — it *was* the flat badge |
> | **`#B4C8DA` chosen** | **7.97 : 1** | **5.0** | 3.0 vs the page-2 threshold blue |
> | `#F2F6FA` rejected | 12.62 : 1 | 12.4 | 2.5 vs "no published price" |
>
> ⚠️ **What the choice costs, and it is written here rather than discovered
> later: `#B4C8DA` sits only 5.0 from the green and red badge colours.** An icon
> can therefore read as a washed-out badge state. Three things keep them apart
> and none is the colour: the icon is a 1.6 px outline where a badge is a filled
> glyph with an arrow, it lives in the callout area rather than under the figure,
> and it never changes while a badge does. `#F2F6FA` measured better on that
> pair and was declined as too vivid against the figure it sits beside.

**An icon is chrome and must not compete with the badge that carries data** —
that is still the rule, and it is now enforced by weight and position rather
than by hue alone.

⚠️ **All fifteen were parsed before being written into this file.** An SVG with a
malformed path renders as *nothing* in Power BI, with no error — a missing icon
looks exactly like a formatting toggle left off. `scratchpad/make_icons.py`
built and parsed them; the check is one line of `xml.etree` and it is the
difference between an icon that is absent and an icon that was never valid.

```dax
// ---- page 1, the four KPI cards

Sales icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12.5V4a1 1 0 0 1 1-1h8.5L21 11.5a1.5 1.5 0 0 1 0 2.1l-7.4 7.4a1.5 1.5 0 0 1-2.1 0L3 12.5Z'/%3E%3Ccircle cx='7.5' cy='7.5' r='1.4'/%3E%3C/svg%3E"

Median price icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M12 6.5v11M14.8 9.2a2.8 2.8 0 0 0-2.8-1.4h-.4a2.2 2.2 0 0 0 0 4.4h.8a2.2 2.2 0 0 1 0 4.4H12a2.8 2.8 0 0 1-2.8-1.4'/%3E%3C/svg%3E"

Days on market icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M12 6.8V12l3.6 2.2'/%3E%3C/svg%3E"

Months of inventory icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6.5 3.2h11M6.5 20.8h11'/%3E%3Cpath d='M8 3.2v3.1c0 2.3 4 3.9 4 5.7 0 1.8-4 3.4-4 5.7v3.1'/%3E%3Cpath d='M16 3.2v3.1c0 2.3-4 3.9-4 5.7 0 1.8 4 3.4 4 5.7v3.1'/%3E%3C/svg%3E"

// ⚠️ An hourglass, not a clock. The measure IS a drain time — how long the
// stock lasts at the current pace — and it sits beside Days on market, which
// is a clock. The two speak of time on purpose; a circle and a double triangle
// share no silhouette at 24 px, which is what settles it.

Active listings icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 6.5h10M4 12h10M4 17.5h10'/%3E%3Ccircle cx='19' cy='6.5' r='1.3'/%3E%3Ccircle cx='19' cy='12' r='1.3'/%3E%3Ccircle cx='19' cy='17.5' r='1.3'/%3E%3C/svg%3E"

// ---- page 2, the four KPI cards

Share affordable icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='8' cy='15.5' r='4.2'/%3E%3Cpath d='M11 12.5 20 3.5M17 6.5l2.4 2.4M14.6 8.9l2.4 2.4'/%3E%3C/svg%3E"

Household income icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2.5' y='6.5' width='19' height='11' rx='1.8'/%3E%3Cpath d='M12 8.6v6.8M13.7 10.2a1.8 1.8 0 0 0-1.7-1h-.3a1.4 1.4 0 0 0 0 2.8h.6a1.4 1.4 0 0 1 0 2.8H12a1.8 1.8 0 0 1-1.7-1'/%3E%3C/svg%3E"

// ⚠️ A bill, and deliberately FLATTER than the wallet that stays on
// Income required, its neighbour in the same row: 19 × 11 against 17 × 14,
// ratio 1.73 against 1.21. Drawn at the wallet's proportions the two
// silhouettes collapsed into one and the whole distinction rested on a dollar
// sign against a small pocket. It is also flatter than Sectors priced icon on
// page 3, which is the same glyph carrying a different meaning.

Tracts evaluated icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 3.5h7v7h-7zM13.5 3.5h7v7h-7zM3.5 13.5h7v7h-7zM13.5 13.5h7v7h-7z'/%3E%3C/svg%3E"

Income required icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 7.5A2 2 0 0 1 5.5 5.5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z'/%3E%3Cpath d='M20.5 10.5h-4a2 2 0 0 0 0 4h4'/%3E%3C/svg%3E"

Change since peak icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 18.5 7.5 13 12 6.5'/%3E%3Ccircle cx='12' cy='6.5' r='1.5'/%3E%3Cpath d='M12 6.5 16.5 13 21 18.5'/%3E%3C/svg%3E"

// ---- page 3, the five KPI cards

Within reach icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M7.8 12.4 10.7 15.3 16.4 9.2'/%3E%3C/svg%3E"

Borderline icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M12 7.3v5.4'/%3E%3Cpath d='M12 16.2v.6'/%3E%3C/svg%3E"

Sectors priced icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 7A2 2 0 0 1 5.5 5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z'/%3E%3Cpath d='M12 8.2v7.6M13.9 10.1a2 2 0 0 0-1.9-1h-.3a1.5 1.5 0 0 0 0 3h.6a1.5 1.5 0 0 1 0 3H12a2 2 0 0 1-1.9-1'/%3E%3C/svg%3E"

Below minimum icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='9'/%3E%3Cpath d='M5.6 5.6 18.4 18.4'/%3E%3C/svg%3E"

Selected sector icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21.5s7-6.1 7-11a7 7 0 0 0-14 0c0 4.9 7 11 7 11Z'/%3E%3Ccircle cx='12' cy='10.2' r='2.6'/%3E%3C/svg%3E"

// ---- page 4, the spread card

Posted minus contract icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 6.5h17M3.5 17.5h17'/%3E%3Cpath d='M12 8.6v6.8'/%3E%3Cpath d='m9.9 10.7 2.1-2.1 2.1 2.1M9.9 13.3l2.1 2.1 2.1-2.1'/%3E%3C/svg%3E"

// ---- not bound to a card yet: the opening quotation mark

Quote icon = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23B4C8DA' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M10.2 6.4c-3.4 0.9 -5.7 3.6 -5.7 6.9 0 2.4 1.6 4.1 3.8 4.1 2 0 3.5 -1.5 3.5 -3.5 0 -1.9 -1.4 -3.3 -3.2 -3.3 -0.3 0 -0.6 0 -0.9 0.1 0.5 -1.4 1.7 -2.5 3.3 -3.1z' fill='%23B4C8DA' stroke='none'/%3E%3Cpath d='M19.7 6.4c-3.4 0.9 -5.7 3.6 -5.7 6.9 0 2.4 1.6 4.1 3.8 4.1 2 0 3.5 -1.5 3.5 -3.5 0 -1.9 -1.4 -3.3 -3.2 -3.3 -0.3 0 -0.6 0 -0.9 0.1 0.5 -1.4 1.7 -2.5 3.3 -3.1z' fill='%23B4C8DA' stroke='none'/%3E%3C/svg%3E"
```

**Two encoding rules that make the difference between an icon and a blank:**
`#` must be written `%23` — a raw `#` truncates the URI at the fragment — and
every attribute uses **single** quotes, because DAX delimits the string with
double ones.

**The six drawn on 2026-09-12**, and what each one says: a line that rises to a
marked peak and falls for *change since peak* · a rounded price plate for
*sectors priced*, so it cannot be taken for the pointed tag of `Sales icon` nor
the circle-and-dollar of `Median price icon` · a map pin for the *selected
sector* · and **one circle carrying three different marks** for the three
verdicts of the page-3 row: a tick for *within reach*, a vertical mark for
*borderline*, a cross for *below the legal minimum*.

**The shared circle is a decision, not a collision.** Three verdicts of the same
quantity are read faster as three states of one object than as three unrelated
drawings, so what distinguishes them is the content of the circle and not its
outline.

**The two added on 2026-09-12, and what each cost to get right.**
*Posted minus contract* is **two levels with the gap measured between them** by a
double-headed arrow — the idiom a reader already owns for "the difference between
these two". Three other ideas were drawn and **all three failed at 24 px, which is
the only size that counts**: two diverging rates closed by a vertical stroke
became a **play button**; two bars with the difference bracketed on top became an
unnamed glyph; the same two rates left open read as a plain **`<`**. None of them
failed at 64 px.

⚠️ **The quote mark is the only FILLED drawing of the fifteen, and that is a
measurement rather than a preference.** Drawn as a 1.6 outline to match the
others, the two commas read as the digits **`66`** — looked at before choosing,
not reasoned about. A quotation mark is a **typographic sign, not a pictogram**:
it is set solid wherever a pull quote is set, and hollowing it turns it into two
numerals. The cost is that one icon of the set no longer shares the outline
weight of the other fourteen; what keeps it in the family is the grid, the
colour and the size.

⚠️ **The quote mark is shipped in BOTH forms, because its destination is not
fixed.** As the measure above if it goes in the callout of a card; as
`powerbi/icons/quote-mark.png` if it sits on the canvas beside a block of text,
which is what "opening a quotation" usually means. **The two are the same
drawing by construction** — the measure is the file's own SVG, URL-encoded — so
choosing one later costs nothing and they cannot drift. See 14.8 bis.

⚠️ **Two of the six were redrawn the same day, and the reasons are worth
keeping.** *Change since peak* first put its peak at x=15: the asymmetry is what
made it read as odd, and centring it fixed it without changing the idea.
*Borderline* was first a beam balance, which **reads as an aerial at 24 px** —
a shape that survives at 64 px can fail at the size it will actually be used,
which is why the contact sheet renders both sizes one above the other.

⚠️ **The largest number in any of these is 24.** `scripts/check_powerbi_project.py`
flags numbers above 10 000 in a `.pbip` definition, so seven SVGs of viewBox
coordinates cannot trip it. Worth stating because it is the kind of thing that
gets discovered at the gate instead of here.

## 14.8 bis The icons that are FILES, not measures

Added 2026-09-12: a house beside the property-type
slicer, a figure beside the household-profile slicer — and, later the same day,
an opening quotation mark, which is a file **for a different reason**: not
because a slicer has no callout, but because a text box has none either.

> ### ⚠️ The mechanism is not the one in 14.8, and confusing them costs a session
>
> A measure whose data category is **Image URL** renders in the **callout of a
> card visual**. **A slicer has no callout.** So an icon beside a slicer is a
> canvas image — *Insert > Image* — and it needs a real file on disk. That is
> the whole difference, and it is why these are versioned as files while
> the icon measures live in this document as DAX. **A text box has no callout
> either**, which is what puts the quote mark on this side of the line the day
> it ornaments a paragraph rather than a card.

| File | Beside | Drawing |
|---|---|---|
| `powerbi/icons/house.png` | the property-type slicer | roof, walls, door |
| `powerbi/icons/person-one.png` | the one-person profile | head and shoulders |
| `powerbi/icons/person-two.png` | the couple profile | two figures, separated |
| `powerbi/icons/quote-mark.png` | a quotation, on the canvas | two filled commas — **also a measure**, see 14.8 |

**`scripts/generate_slicer_icons.py` draws them**, PNG and SVG from **one set of
coordinates**, so the versioned source and the file pasted into Desktop cannot
drift apart. `--preview out.html` writes a contact sheet. Re-running it produces
no git diff. Same 24 × 24 grid, 1.6 stroke, round caps and `#B4C8DA` as the
card icons, so the report keeps one hand.

**The PNGs are 128 px on a transparent ground.** Take the PNG: it inserts
without question. The SVG is kept as the readable source — whether Desktop
accepts it at insertion was **not verified**, so it is not the one to try first.

⚠️ **A canvas image is STATIC.** It does not follow the slicer: the two figures
stay two figures when the reader picks "one person". **It names what the slicer
filters, not what is selected** — and the household-profile slicer has *three*
values, not two, the third being `Total × Total`. An icon per value does not
exist on a native slicer.

⚠️ **A torso is not a half circle.** The first attempt drew the shoulders as a
true half-circle and it read as an **archway** under a ball; the second figure
read as a dot and a comma. Both were found by **looking at the render at 36 px**,
not by reasoning about the coordinates. The fix is a flattened half-ellipse with
two short uprights. That is why the generator has a contact sheet at all, and
why it renders each icon at 72 px **and** at the size it will really be used —
a drawing that survives at 72 px can fail at 28.

**Three measures carrying these same three drawings are written in the paste
file, and they are for a CARD if one ever wants them there.** They are of no use
beside a slicer. An unused measure in the model is one more thing to understand
in six months: do not create them without a use.

**`check-secrets.sh` lists the three PNGs in its section 6**, the files it cannot
look inside — the same conscious decision the ERD PNG needed on 2026-08-31. It
is an easy one here, and for a reason worth stating: **the SVG beside each PNG is
plain text and says exactly what the PNG contains**, and `generate_slicer_icons.py`
rebuilds both from coordinates in this repository. The binary is therefore
verifiable by a second, readable route — which is precisely what a `.pbix` is
not.

## 14.9 The two notes, and why they are constant strings

> ## ⚠️ NEITHER NOTE WAS BUILT, AND THAT IS A DECISION — 2026-09-12
>
> **Decided:** neither card goes on the report. The reason: the report is
> already well filled, and the colour convention is
> intuitive from a buyer's point of view. Read out of
> `mhi-Dashboard_v11.pbix` first — they appear on no page — so this records a
> choice, not an omission.
>
> **The DAX below is kept, unbuilt**, for the same reason section 15.3 is kept:
> the measurement it carries is still true and still needed elsewhere.
>
> **What the decision costs, and where it is paid instead — both free of
> pixels:**
>
> | Lost from the screen | Where it must land |
> |---|---|
> | the seasonality of three of the four page-1 metrics | `docs/limitations.md`, J4.4. The badge already **names** the quarter it compares, which is the half that mattered most |
> | green = favourable to a first-time buyer | `docs/methodology.md`, J4.4 |
>
> ⚠️ **The colour convention is intuitive for a buyer and counter-intuitive for
> anyone else** — a reader who is not buying sees a falling price in green.
> That is the reason the note is written down somewhere rather than dropped.

```dax
Quarter comparison note =
"Change is against the previous quarter. Montréal sales, listings and time on
market are strongly seasonal: sales rose in 18 of 21 first-to-second quarters
and fell in 18 of 21 second-to-third. Median price is not seasonal in the same
way. Read a single quarter's move as a season before reading it as a market."

Colour convention note =
"Green marks a move that favours a first-time buyer, red one that does not — so
a falling price and a lengthening time on market are both green."
```

⚠️ **Both are constant strings that read no table and no parameter, by
construction.** `Down payment assumption` was made dynamic on 2026-09-09 and
silently broke page 2, where the same card announced a typed down payment over
figures computed at the legal minimum — **and the acceptance case "page 2
unchanged at every slider position" could not catch it, because no figure moved,
only a sentence.** A note that cannot vary cannot repeat that.

`Quarter comparison note` goes on page 1 and page 2. `Colour convention note`
goes on page 1, where four badges point in two directions at once and the
question actually arises.

## 14.10 The build, in Desktop

Everything below is formatting on cards that already exist. **All seven are
already `cardVisual`** — the new card visual, generally available since November
2025, read out of `Report/Layout`. Nothing is replaced.

1. Create the three functions (TMDL view → *Apply*).
2. Create the fourteen measures and the seven icon measures in `_Measures`.
   **Home table matters**: two measures were left in `Down payment input` on
   2026-09-09, and recreating a what-if parameter takes its lodgers with it.
3. On each icon measure: *Column tools* → **Data category** → **Image URL**.
4. Per card, *Format visual* → **Callout** → **Image** → on → *Image type* =
   **Select from data** → the icon measure → *Image fit* **Center**, *Size*
   **32 px**.
5. Per card, *Format visual* → **Reference labels** → *Apply settings to* = that
   card → drag the badge measure into **Add label** → select it.
6. On the reference label, *Values* → **fx** → *Format style* **Field value** →
   the matching colour measure.
7. Turn the reference-label **background off** (*Reference labels layout* →
   *Background*). It defaults on since the November 2025 release and puts a
   panel behind a one-line badge.
8. Add the two note cards.

⚠️ **Step 6 is where a badge silently loses its colour.** *Field value* is the
only style that takes a `#RRGGBB` measure; the rule-based styles will happily
accept the text measure and colour nothing.

⚠️ **STEP 4 TRAVELS BETWEEN VISUALS, AND THIS SECTION DID NOT SEE IT COMING.**
The trap written above was *Apply settings to* = **All** inside one visual. What
happened on 2026-09-11 is one level up: setting the callout image on one card
and then reaching for a format painter — or formatting several cards at once —
carries **the image binding itself, measure and all**, onto every card it
touches. Measured `v09` against `v10`: one card carried a callout image before,
**twelve** after, where seven were asked for. Four of the five strays are on
page 3, which acceptance case 9 requires to be untouched, and they carry the
sales price-tag icon.

> ## ⚠️ WHAT `Report/Layout` DOES NOT TELL YOU — settled 2026-09-12
>
> This document leans on `Report/Layout` constantly, and rightly: it names the
> tables, columns and measures of every visual, and it is how half the defects
> of block D and E were found. **But it is a record of what has been SET, not of
> what is RENDERED, and the two diverge in at least three ways now measured:**
>
> | What the file shows | What Desktop does |
> |---|---|
> | a `referenceLabel` bound to a metadata key the card does not carry | **inert** — proved on 2026-09-11 by a card holding an orphan and showing one badge |
> | a `dataPoint` `fill` pinned to one `scopeId` **under an `fx` rule** | **inert** — the conditional rule covers it. Checked on screen, 2026-09-12: the page-2 map has no hard-coloured tract, although the entry is still in the file |
> | **`shape.projectionEnum`** | **does not follow the setting.** The page-3 map reads `albersUsa` in a file saved 2026-09-12 at 20:04 and is **`mercator`** in Desktop |
>
> ⚠️ **The projection one was raised as a defect twice, on 2026-09-01 and again
> on 2026-09-12, from the same misreading.** The first time it was written off as
> "false, or stale". It is neither: two readings eleven days apart, on two
> different files, both saved after the setting was made, return the same wrong
> value. **The property is simply not authoritative in the layout.**
>
> **The rule this settles, and it is not "read the file again":** `Report/Layout`
> answers *does this object exist, and what is it bound to*. It does not answer
> *what does the reader see*. For anything about rendering — a projection, a
> colour that a conditional rule may override, whether a toggle actually took —
> **Desktop is the authority and the check is a glance.** Raising a rendering
> defect from the file alone costs a look in Desktop and costs this document a
> correction; it has now done both twice.

**The reference label that travels with it is harmless and the image is not, for
a reason worth keeping.** A reference label is scoped to a metadata key — the
field it belongs to — so on a card that does not have that field it is inert;
the proof is that page 1's `Median price` card holds the orphan `Sales change`
label and **shows one badge, not two**. The callout image is scoped to
`{"id": "default"}`, that is, to nothing, **so it renders wherever it lands**.
Set the image card by card, and read case 9 as a real case rather than a
formality.

## 14.11 Acceptance

Run `.venv/Scripts/python.exe scripts/report_oracle.py --quarter <q>` beside
Desktop. The oracle prints, for each of the badged cards, the current value, the
previous quarter's value, the movement, the arrow and the colour it must show.

> ⚠️ **"Seven cards" is stale: the report carries EIGHT badged cards — 2026-09-12.**
> Read out of `mhi-Dashboard_v11.pbix`. The eighth is
> `Affordability change since peak (points)` on page 2, added directly in
> Desktop, which carries a live `Peak quarter` reference label and its own callout
> icon. **It is a card that was built, not formatting that travelled** — the
> difference is readable in the file: a live label is bound to a metadata key
> that matches its own card's field, an orphan is bound to another card's.
> `scripts/` has no tool for this; the check is the `badges.py` probe pattern
> described at the end of this section.

| # | Set this | Expect |
|---|---|---|
| 1 | Page 1, condominium, **2019 Q2**, no sector | **all four badges absent.** Nothing precedes the first quarter |
| 2 | Page 1, condominium, 2026 Q2, no sector | four badges, each naming **2026 Q1**, matching the oracle to one decimal |
| 3 | Page 1, **plex**, one sector, step through the quarters | the price badge **disappears** on the quarters the oracle lists — 24 of them across the sectors |
| 4 | Page 1, **2022 Q3**, any type | `Listings change` reads *inventory not reconciled this quarter*, in grey. The other three badges are normal |
| 5 | Page 1, **2024 Q1** | same refusal — the quarter it subtracts is 2023 Q4 |
| 6 | Page 1, ctrl-click a **second quarter** if the slicer allows it | every badge vanishes. Nothing reads "0.0 %" |
| 7 | Page 2, **single-family**, 2026 Q2 | the share badge in **points**; the `Tracts evaluated` badge **grey**, showing a count that the oracle confirms moved |
| 8 | ~~Page 2, any quarter~~ | ~~the two note cards are unchanged when the slider moves~~ — **void since 2026-09-12: neither note card was built, see 14.9.** What still has to hold on page 2 is the card that *is* dynamic: `Down payment note` must not move with the slider, which is the defect of 2026-09-09 |
| 9 | Page 3 and page 4 | ⚠️ **REWRITTEN 2026-09-12 — page 3 now carries five icons by design.** What must hold: **no badge** on either page, and on page 3 each of the five icons is bound to *its own* measure — never `Sales icon`, which is what all five were bound to while switched off. ⚠️ **AMENDED again the same day: page 4 now carries ONE icon by decision** (`Posted minus contract icon`), so "no icon on page 4" is no longer the test — what is, is that the spread card carries that measure and the other three cards of page 4 carry none |

**Case 3 is the one that fails if the guards were written from the island.**
Cases 4 and 5 are the ones that fail if the corroboration guard was written on
the current quarter only.

### ⚠️ The icon count changed twice on 2026-09-12: 8 badged cards, **14 carrying an icon**

An icon and a badge are **not** the same wiring, and the acceptance has to keep
them apart:

| | Badge (reference label) | Callout icon |
|---|---|---|
| Page 1 | 4 | 4 |
| Page 2 | 4 | 4 |
| **Page 3** | **0 — and that stands** | **5, added by decision** |
| Page 4 | **0 — and that stands** | **1, added by decision** — the spread card |

**Fifteen icon measures exist for fourteen cards.** The fifteenth is
`Quote icon`, which has no card yet: it is drawn and parsed and waiting, and it
also exists as a file for the canvas. A measure nothing reads costs nothing and
is not a defect — but it is the kind of thing that gets counted as one, so it is
counted here instead.

Icons were added to page 3 on 2026-09-12. Those five cards already held
an `image` object, **switched off and bound to `Sales icon`** — the formatting
that travelled on 2026-09-11. They are now bound to their own measures and
switched on, which is why case 9 above no longer reads "no icon". **The part of
case 9 that still bites is the absence of badges on both pages, and that each
icon is bound to its own measure rather than to whichever one travelled there.**

⚠️ **Case 9 is not a formality, and on 2026-09-11 it failed.** It costs one look
— open page 3, look to the left of the four KPI figures, a small grey tag icon
is the defect — and it can also be answered off the file, which is how it was
actually caught: `Report/Layout` names the measure behind every callout image,
so listing the cards that carry one and comparing that list against the seven of
this section is a mechanical check on a saved `.pbix`. **The case exists because
formatting propagates; see the warning at the end of 14.10.**

# 15. J4.2¾ · 5 — The page menu

> **Specified 2026-09-11.** Nothing in dbt moves: this section is a layout pass
> and four buttons. `dbt build` stays at PASS=353 and pytest at 140, and
> `git status` on `dbt/` is how that claim is checked.
>
> ⚠️ **This section gains none of the eleven criteria of brief §44**, which stay
> at 8 of 11. It is finish work, taken on by decision on
> 2026-09-11, with the cost measured before the choice was made.

The Back button of page 1 was deleted on 2026-09-11, deliberately. In its place:
a vertical menu of the four pages, with an unselected state, a hover state, a
selected state that says which page the reader is on, and an icon per entry.

> ## ⚠️ WHAT WAS BUILT ON 2026-09-11 IS NOT WHAT 15.3 AND 15.4 SPECIFY
>
> Read out of `mhi-Dashboard_v11.pbix`, saved at 22:38. **What was built is the
> Page navigator, not sixteen buttons**, laid out differently:
>
> | | Specified in 15.3 / 15.4 | Built |
> |---|---|---|
> | Control | 16 `actionButton` | **1 `pageNavigator` per page**, 262 × 300 |
> | Frame | none | a `shape` panel, **263 × 352**, behind it |
> | Place | full-height rail, x 0→176 | **top-left block**, x 0→263, y 0→352 |
> | Pages carrying it | 4 | ~~2~~ → **4, since 2026-09-12** |
> | Layout pass | `plan_left_rail.py` | **done by hand**, on all four pages |
> | Glyphs | in the button text | **none yet** — the four pages keep their plain names |
>
> **15.3 and 15.4 are therefore superseded as instructions.** They are kept
> because the measurement in 15.1, the palette in 15.5 and the acceptance in
> 15.6 still hold whichever control carries the menu — and because the reason
> the sixteen-button route existed is the same reason the icons are still
> missing.
>
> **The open question of 15.4 is answered, by the file itself.** The navigator's
> formatting objects are `accentBar, fill, glow, layout, pages, rotation,
> shadow, shape, text`. **There is no `icon`.** The documentation was right:
> the only way to put a mark in front of an entry is the **page display name**.
>
> ✅ **And the file turned up a formatting card the documentation does not
> list: `accentBar`**, already bound to *hover* in the file. A bar is a
> better carrier than a fill on a dark theme — it does not have to clear a
> contrast threshold against the panel to be seen, it only has to exist. That
> is worth knowing before anyone reaches for the fill-based hover of 15.5.
>
> ## ✅ THE MENU IS ON ALL FOUR PAGES — read out of the file, 2026-09-12
>
> `mhi-Dashboard_v11.pbix`, saved 16:13. A `pageNavigator` at **x=0 y=18,
> 262 × 300**, inside a `shape` panel, on **Market, Affordability, First-time
> buyer and Rates** — identical coordinates on all four. On Rates the panel
> runs the full height (262 × 1080); on the other three it is 263 × 352.
>
> **And the layout pass came with it.** Pages 2, 3 and 4 were rebuilt by hand
> onto the grid page 1 already used: KPI row at **y=140**, cards at
> **x=275 / 600 / 927 / 1252**, the fifth slot at 1577, chart zones 807 wide at
> y≈290, the trend line at y=775. Checked field by field rather than by eye:
> **no measure of pages 1, 2 or 3 was lost in the move.**
>
> **The glyphs are still not placed**, and the reason is unchanged: a
> `pageNavigator` has no `icon` object, so a mark would have to live in the
> page display name.
>
> **What remains of block E**: `Sectors priced` on two cards of page 3 (E6),
> and the acceptance of 14.11. **E5 is closed as a decision, not as work** —
> see the banner at 14.9.


## 15.1 The one measurement that decides the whole shape

**A Power BI button has no *selected* state.** Its states are *Default*,
*On hover*, *On press*, *Disabled* and *Loading* — and none of them means "this
button is the page you are looking at", because a button does not know.

That was confirmed twice, from two independent places, before anything was
designed:

| Where | What it says |
|---|---|
| Microsoft's button documentation | the four cards that vary by state are Shape, Style and Rotation, over *Default · On hover · On press · Disabled · Loading* |
| **`powerbi/Theme/Montreal_Immobilier_Dark_v02.json`** | `pageNavigator` and `bookmarkNavigator` each carry a `"$id": "selected"` for `fill` **and** `text`. **`actionButton` does not.** |

The second is the stronger of the two: it is not a doc page that could be out of
date, it is the schema Power BI accepted from this very report.

**And the Page navigator, which does have a selected state, has no icon.** Its
formatting cards are Fill, Text, Outline, Shape, Shape shadow, Shape glow,
Rotation, plus Grid layout and Selected state. There is no Icon card, and the
button labels are the page display names, so the only way to put a mark in front
of one is to rename the page.

**Icon and selected state are therefore mutually exclusive in the native
controls.** The icon was chosen on 2026-09-11, which means the selected
state has to be simulated: **four buttons, copied onto four pages, and on each
page the one that stands for that page is styled differently.** Sixteen objects,
and that number is the price of the choice, not an accident of it.

## 15.2 There is no free space, and clearing it is the real work

The canvas is **1920 × 1080** and on 2026-09-11 the visuals filled it to both
edges on all four pages. Free margin at the top: 16 px on Market, 44 on
Affordability, **0** on the other two. At the left: **0 everywhere.**

A 176 px rail intrudes on **20 visuals**, and seven of them are full width, so
they have to be narrowed as well as moved:

| Page | Visuals inside the rail | Full-width among them |
|---|---|---|
| Market | 3 | 1 |
| Affordability | 7 | 3 |
| First-time buyer | 5 | 1 |
| Rates | 5 | 2 |

**The rule, and it is the only one a script may apply.** Every visual is
compressed horizontally into the band that is left:

```
k         = (1920 − 176) / 1920 = 0.90833
new_left  = 176 + left  × k
new_right = 176 + right × k
```

Y and Height are never touched. This preserves every proportion and every
gutter, cannot create a collision that did not already exist, and cannot push
anything off the canvas — a visual flush against 1920 lands on exactly 1920.
The tempting alternative, *move only what intrudes*, leaves a visual that was at
x = 0 sitting against one that was at x = 180 and needs an eye on every page:
that is Desktop's job, not a script's.

**`scripts/plan_left_rail.py` does it**, and prints the plan whether or not you
let it write:

```
.venv/Scripts/python.exe scripts/plan_left_rail.py
.venv/Scripts/python.exe scripts/plan_left_rail.py --write powerbi/mhi-Dashboard_v11.pbix
.venv/Scripts/python.exe scripts/plan_left_rail.py --verify powerbi/mhi-Dashboard_v11.pbix
```

It reads the geometry out of the `.pbix` rather than out of this file, so
re-running it after any layout change is what stops the plan going quietly
stale — the same arrangement as `scripts/generate_erd.py`.

**What the rewrite was proved to do, on 2026-09-11**: `v11` holds the same zip
entries in the same order as `v10`; **`Report/Layout` is the only entry whose
bytes differ** — DataModel, SecurityBindings, the theme, the three GeoJSON
resources and the saved DAX query are byte-identical; and the layout JSON is
**identical once X and Width are removed from every visual**, so not one other
property moved.

⚠️ **That is a structural proof, not a verdict.** Whether Desktop opens a
rezipped `.pbix` is Desktop's answer and nobody else's — the file carries a
`SecurityBindings` entry the script copies without understanding. The script
refuses to write over its input for exactly that reason: `v10` stays whole, and
if `v11` will not open, the printed plan is the fallback and the cost was one
attempt. **Same rule as `albersUsa` on 2026-09-01: the product is the
authority.**

⚠️ **Typing is the fallback, and it is not dragging.** *Format visual > General
> Properties* has numeric **X / Y / Width / Height** fields. The plan prints
`X now → X` and `W now → W` per visual, sorted top to bottom, labelled by title
or by the field the visual carries. 56 visuals, two numbers each.

## 15.3 Four buttons, built once and pasted three times  — SUPERSEDED, see the note under 15

Rail from x = 0 to 176, full height. Buttons at **x = 8, width 160, height 44**,
tops at **y = 32, 88, 144, 200**.

1. *Insert > Buttons > Blank*, four times, on **Market**.
2. Each one: *Style > Text* = the page name with its glyph (15.4) ·
   *Action* **On** · *Type* **Page navigation** · *Destination* = its page.
3. Select all four, **Ctrl+C**, then **Ctrl+V** on each of the other three
   pages. Paste preserves position, which is what keeps the menu from jumping
   as the reader moves between pages.
4. On each page, restyle **the one button that stands for that page**: *Style >
   Fill*, state **Default**, `#87CEFA`; *Style > Text*, state **Default**,
   `#0E1A25`, **bold**.

⚠️ **On the selected button, set the *On hover* fill to `#87CEFA` as well.**
Otherwise it drops back to the ordinary hover colour under the mouse, and the
"you are here" mark disappears at the exact moment the reader points at it.

**Leave its Action on.** Navigating to the page you are already on is invisible,
and turning the action off is an invitation to the *Disabled* state's grey,
which means something else.

## 15.4 The icon goes in the text, and that is not a downgrade  — SUPERSEDED for the control, still true for the glyph

⚠️ **To be constated in Desktop, because the documentation does not answer it**:
does *Style > Icon > Icon type* offer **Custom**, and is there an **fx** beside
it? The button documentation lists built-in icon types and **fill images browsed
from disk**, and documents conditional formatting for the *tooltip* and the
*destination* — **not for the icon**. The theme's `actionButton` has no `icon`
entry either.

There is a route that needs neither an answer nor a file: **put the glyph in the
button's text**, `▦  Market`.

**It is better than an image here, for a reason that is measured rather than
aesthetic.** *Style > Icon* can be set per state, but an image carries its own
colours into every state; a glyph inside the text **takes the text colour of the
state it is in** — `#C2D0DE` at rest, `#F2F6FA` on hover, `#0E1A25` bold on the
selected button. The four-variant icon set that the image route would need in
order to look right on the selected button is what the text route gets for free.

The objection that ruled the glyph out for the Page navigator does not apply
here: **that** route took its labels from the page display names, so a glyph
meant renaming the pages. A hand-built button has text of its own.

| Page | Glyph | Codepoint | Reads as |
|---|---|---|---|
| Market | `▦` | U+25A6 | a grid — the board of sectors |
| Affordability | `◑` | U+25D1 | a share of a whole |
| First-time buyer | `◈` | U+25C8 | a single household |
| Rates | `◉` | U+25C9 | a target, a rate to clear |

Two spaces between the glyph and the word; the theme already puts a 12 px left
margin on button text.

⚠️ **Do not use `▲` or `▼`.** Since section 14 those two mean *change against
the previous quarter* everywhere on this report, and a menu is not a change.

⚠️ **All four are from the Geometric Shapes block, U+25A0–U+25FF**, which Segoe
UI covers. If one comes out as an empty box in Desktop it is the font and not
the character: take another from the same block rather than reaching for an
emoji, which renders in colour and would be the only coloured thing on the page.

## 15.5 The palette already exists, and one value of it has to change

Every colour below is taken from `pageNavigator` in
`Montreal_Immobilier_Dark_v02.json` — the states already defined
for the control that ended up not being used. Nothing new to invent, and the text
contrasts are comfortable:

| State | Fill | Text | Contrast |
|---|---|---|---|
| Default | `#182735` | `#C2D0DE` | **9.69 : 1** |
| On hover | `#23394C` → **`#2B4760`** | `#F2F6FA` | 10.98 → **8.90 : 1** |
| Selected | `#87CEFA` | `#0E1A25` bold | **10.26 : 1** |

All three clear WCAG AAA for normal text, before and after the change below.

⚠️ **THE HOVER FILL HAS TO CHANGE, AND THIS IS THE FINDING OF THE SECTION.**
`#23394C` is **CIEDE2000 6.0** from the default `#182735` — below the floor of
**10** this project uses for colours a reader must tell apart without comparing
them deliberately. On a page navigator that is survivable, because the selected
state carries the signal. **Here hover is one of the three things that were
asked for**, and at 6.0 it barely registers.

`#2B4760` was chosen by walking the ramp and stopping at the first value that
clears the floor:

| Candidate | ΔE vs default | ΔE vs selected | ΔE vs canvas | white text |
|---|---|---|---|---|
| `#23394C` *(current)* | **6.0** | 57.2 | 10.1 | 10.98 : 1 |
| `#274156` | 8.6 | 52.7 | 12.8 | 9.78 : 1 |
| **`#2B4760`** | **10.8** | 49.2 | 15.0 | 8.90 : 1 |
| `#2F4D6A` | 13.1 | 45.8 | 17.2 | 8.09 : 1 |

**Change it in the theme, not on sixteen buttons** —
`visualStyles.actionButton.*.fill`, the entry with `"$id": "hover"`. There is no
other action button in the report since the Back button was deleted, so the
theme is a single place and the sixteen inherit *Default* and *On hover* from it
without being touched. Only the four selected buttons need per-visual overrides.

⚠️ **At rest the menu is text, not tiles.** `#182735` against the `#0E1A25`
canvas is **1.16 : 1**. That is a consequence of the theme itself and it is why the
selected state carries all the signal. Making the tiles visible at rest is a
second theme edit and it would have to be remeasured against the canvas, the
hover and the selected fill — it is not free, and it is not part of this section.

## 15.6 Acceptance

| # | Set this | Expect |
|---|---|---|
| 1 | Open each of the four pages | **exactly one** button selected, and it is that page's |
| 2 | Hover the selected button | **nothing changes** — this is the flicker guard of 15.3 |
| 3 | Hover any other button | it visibly lightens. **The case the ΔE 6.0 finding exists for**: if it looks the same, the theme edit did not land |
| 4 | Click each button in turn | the right page, and **the menu does not jump** — identical geometry on all four |
| 5 | `plan_left_rail.py --verify` on the saved file | the rail is clear on every page and nothing overflows |
| 6 | Page 1 and page 2, against the oracle | **the block-E badges read what they read before.** A layout pass touches geometry only: a figure that moved means something else happened |

**Case 6 is the one that gets skipped**, and it is the cheapest insurance in the
section: 56 visuals were repositioned by a script, and the only way to know it
repositioned rather than rebound them is to read a number that has nothing to do
with geometry.

# 16. J4.2¾ · 6 — The badges become year-over-year, and two cards change what they hold

Three changes, asked for on 2026-09-17 after reading the built report:

1. the seven change badges compare **the same quarter one year earlier** instead
   of the previous quarter — pages 1 and 2 both;
2. page 1 replaces `Active listings` with **months of inventory**;
3. page 2 replaces `Tracts evaluated` with the **median tract's theoretical
   income**.

**Nothing in dbt moves.** Every figure below already exists in `fact_market` and
`fact_affordability`; months of inventory is a ratio of two columns that sit on
the same row. The work is in Desktop, and `powerbi/apply-changes.md` carries it
as **BLOCK G** — F is the page menu.

⚠️ **This reverses what 14.1 records as settled on 2026-09-10.** That section
carries the warning that the previous quarter would mostly measure the season,
and records that the previous quarter was kept regardless. It was reopened on
2026-09-17 after the badges had been read on a built page: quarter-to-quarter
movement is small enough that the cards mostly showed noise. **The measurement
in 16.1 confirms the reversal, though not by the route that prompted it** — what
condemns the quarterly window is not the size of the movement but its season.
**The reversal is deliberate and is not to be reopened.**

## 16.1 The measurement that decides it is seasonality, not size

Measured on the 87 island rows, three property types, **median** absolute
change:

| Metric | vs previous quarter | vs one year earlier | |
|---|---|---|---|
| Median price | 2.29 % | **6.10 %** | ×2.7 |
| Active listings | 7.85 % | **14.48 %** | ×1.8 |
| Days on market | 12.25 % | 13.43 % | ×1.1 |
| **Sales** | 18.56 % | 18.03 % | **×0.97** |

**Sales contradict the premise**: their quarter-over-quarter swing is *larger*
than their annual one. That is what settles the question rather than weakening
it, because of where the swing comes from — the same 21 transitions, by calendar
quarter:

| Transition into → | Sales | Active listings | Days on market | Median price |
|---|---|---|---|---|
| Q2 | **18/21 up, +21.5 %** | **19/21 up, +12.2 %** | **2/21 up, −18.2 %** | 19/21, +2.7 % |
| Q3 | **3/21 up, −16.2 %** | 6/21, +1.1 % | 16/21, +7.2 % | 13/21, +0.5 % |
| Q1 | 13/21, +1.9 % | 7/21, −4.2 % | 13/21, +8.1 % | 19/21, +2.1 % |
| Q4 | 13/21, +5.1 % | 8/21, −2.4 % | 13/21, +4.5 % | 15/21, +1.1 % |

**Three of the four page-1 badges measure a season.** A badge reading ▲ 21 %
every spring and ▼ 16 % every summer tells the reader the calendar, not the
market. Median price is the only one that is not seasonal — and it is also the
one the quarterly comparison flattens most. Both readings point the same way.

Page 2, condo × couple, 28 transitions:

| | vs previous quarter | vs one year earlier | |
|---|---|---|---|
| Share of tracts affordable | 3.1 pts | **7.0 pts** | ×2.3 |
| Income required, lower bound | 2.79 % | **8.70 %** | ×3.1 |

Required income gains the most, which follows: it tracks the qualifying rate,
which moves by central-bank decision and not by season.

**The cost, counted**: the island goes from **84 to 75** badge-bearing slices,
and page 2 from **28 to 25** transitions. The four opening quarters of the
archive — 2019 Q2 through 2020 Q1 — have no predecessor twelve months back.
**Nine more silent slices on page 1, three on page 2, all at the start.**

**And it rejoins the publisher's own convention.** Page 65 of the Baromètre
defines its change rates as *« calculés par rapport au même trimestre de l'année
précédente »*. The badge stopped disagreeing with the source it sits on.

## 16.2 ⚠️ The published YoY columns are NOT what gets read, and one of them is mislabelled

`fact_market` has carried five `*_change_pct_yoy` columns since J3.5 — APCIQ's
own printed change rates — which no measure reads. The obvious move is to read
them now that the badge asks the same question. **It was measured first, and it
is refused.** Our computed YoY against the published one, island rows, after
rounding to the integer APCIQ prints:

| | Exact matches / 75 | Mean signed gap |
|---|---|---|
| Median price | 64 | +0.01 pt |
| Sales | 31 | −0.69 pt |
| Active listings | 9 | −1.59 pt |
| **Days on market** | **8** | worst gap **74 points** |

The first three are the J3.5 vintage seen from the other end: APCIQ divides by a
figure it has since revised down, we hold the first publication. **Days on
market is something else.** Read as a **number of days** rather than a percent:
**51 of 75 exact, 63 within one day**.

⚠️ **`days_on_market_change_pct_yoy` does not hold a percentage. It holds
days.** The column name has been wrong since J3.5 and nothing caught it, because
nothing reads the column. Wiring a badge to it would print `▲ 12 %` where APCIQ
prints *+12 jours*. **Debt recorded, not paid** — renaming a mart column is a
dbt change, and this session changes no model. It is written in
`docs/limitations.md` and here.

Three reasons the badge computes its own, and they compound:

1. **Page 2 cannot read APCIQ at all.** `Share of tracts affordable` and
   `Income required` are our derivations; no publisher prints a change rate for
   them. Sourcing page 1 from the publisher and page 2 from a formula would put
   two definitions of one badge in one report — the defect of 2026-08-30, which
   disagreed on 44 slices out of 87.
2. **The counts drift** — the vintage, above.
3. **One of the columns is not what its name says.**

## 16.3 The three functions, renamed and re-pointed

The mechanism does not change: one place decides what "earlier" means, and
fourteen one-line measures sit on top. **`EDATE ( .., -3 )` becomes
`EDATE ( .., -12 )`, and the three functions are renamed** so the names stop
lying. Everything else in 14.2 stands — the `REMOVEFILTERS ( 'date' )` before
re-filtering, the re-filter on `date_key`, the deliberately unscaled `Movement`,
the `* 100` at display time.

⚠️ **Retype them under the new names in the DAX query tab and run 14.2 bis
BEFORE saving**, exactly as on 2026-09-10. Forwarding a lazy parameter from one
UDF into another is still undocumented, and this project is at five collisions
with reserved DAX names — `trailing`, `Current`, `Name`, `RANK`,
`PreviousQuarter`. `YoYBadge`, `YoYBadgeColour` and `ValueOneYearEarlier`
collide with nothing known, **which is not the same as verified**.

```tmdl
	/// The value of a measure in the same quarter one year earlier.
	/// @param {AnyRef} m - the measure to evaluate in the earlier quarter
	/// @returns the earlier value, or BLANK when no single quarter is in context
	function ValueOneYearEarlier = (m : ANYREF) =>
		VAR ThisQuarterStart = SELECTEDVALUE ( 'date'[quarter_start_date] )
		VAR EarlierQuarterStart = EDATE ( ThisQuarterStart, -12 )
		RETURN
			IF (
				NOT ISBLANK ( ThisQuarterStart ),
				CALCULATE (
					m,
					REMOVEFILTERS ( 'date' ),
					'date'[date_key] = EarlierQuarterStart
				)
			)

	/// The badge text: arrow, size of the change, and the quarter compared to.
	/// BLANK whenever the comparison cannot be made.
	/// @param {AnyRef} m - the measure to compare
	/// @param {String} unitMode - "percent", "points" or "count"
	/// @returns e.g. "▲ 4.2 % vs 2025 Q2", or BLANK
	function YoYBadge = (m : ANYREF, unitMode : STRING) =>
		VAR Latest = m
		VAR PriorValue = ValueOneYearEarlier ( m )
		VAR EarlierLabel =
			CALCULATE (
				SELECTEDVALUE ( 'date'[quarter_label] ),
				REMOVEFILTERS ( 'date' ),
				'date'[date_key] = EDATE ( SELECTEDVALUE ( 'date'[quarter_start_date] ), -12 )
			)
		VAR Movement =
			SWITCH (
				unitMode,
				"percent", DIVIDE ( Latest - PriorValue, PriorValue ),
				Latest - PriorValue
			)
		VAR Marker = SWITCH ( TRUE (), Movement > 0, "▲ ", Movement < 0, "▼ ", "— " )
		VAR Magnitude =
			SWITCH (
				unitMode,
				"percent", FORMAT ( ABS ( Movement ) * 100, "0.0" ) & " %",
				"points",  FORMAT ( ABS ( Movement ) * 100, "0.0" ) & " pts",
				FORMAT ( ABS ( Movement ), "#,0" )
			)
		RETURN
			IF (
				NOT ISBLANK ( Latest ) && NOT ISBLANK ( PriorValue )
					&& NOT ( unitMode = "percent" && PriorValue = 0 ),
				Marker & Magnitude & " vs " & EarlierLabel
			)

	/// The badge colour. higherIsBetter says which direction is good FOR A
	/// FIRST-TIME BUYER, which is not the same as "up".
	/// @param {AnyRef} m - the measure the badge is about
	/// @param {Boolean} higherIsBetter - TRUE when a rise favours the buyer
	/// @returns a #RRGGBB string, or BLANK when there is no badge to colour
	function YoYBadgeColour = (m : ANYREF, higherIsBetter : BOOLEAN) =>
		VAR Latest = m
		VAR PriorValue = ValueOneYearEarlier ( m )
		VAR Movement = Latest - PriorValue
		VAR Favourable = IF ( higherIsBetter, Movement > 0, Movement < 0 )
		RETURN
			IF (
				NOT ISBLANK ( Latest ) && NOT ISBLANK ( PriorValue ),
				SWITCH (
					TRUE (),
					Movement = 0,  "#8FA3B5",
					Favourable,    "#B8E0C5",
					"#FA584C"
				)
			)
```

⚠️ **The `* 100` is still there, twice.** It is the defect that shipped six of
seven badges wrong on 2026-09-10 and was found by reading the screen a day
later. Copying this block wholesale is how it stays fixed; retyping from memory
is how it comes back.

**The fourteen measures of 14.3 change by one word each** — `QuarterBadge` →
`YoYBadge`, `QuarterBadgeColour` → `YoYBadgeColour`. Their names, their unit
modes and their `higherIsBetter` flags are unchanged. Two of them are replaced
outright by 16.4 and 16.6, which is the only structural change in the set.

## 16.4 Page 1: months of inventory replaces active listings

`Active listings` is APCIQ's *inscriptions en vigueur*, defined on page 65 as
*« la moyenne des données mensuelles pour la période visée »* — an average
**stock**, not a flow. On its own it is not interpretable: N properties offered
is a lot or a little depending on how fast they leave.

**The publisher answers that question itself**, on its glossary page rather than
in the PDF — <https://apciq.ca/en/definitions-and-explanatory-notes>, read
2026-09-17, quoted in full in `docs/apciq.md` section 4:

> « The number of months needed to sell the entire inventory of properties for
> sale, calculated according to the pace of sales of the past 12 months. It is
> obtained by dividing the inventory **by the average number of sales in the
> past 12 months**. »

```
months of inventory = twelve-month inventory ÷ (twelve-month sales ÷ 12)
```

Both columns are on `marts.fact_market_trailing_12m`, built in J3.5 and until
now read by nothing. No model, no seed, no ingestion.

### ⚠️ THE DENOMINATOR IS TWELVE MONTHS, AND THE FIRST VERSION OF THIS SECTION GOT IT WRONG

Written on 2026-09-17 as the quarter's listings over the quarter's sales ÷ 3,
and corrected the same day when the publisher's glossary was read. **The error
was not arithmetic, it was the one this very session exists to remove**: sales
are strongly seasonal — 18 of 21 transitions into Q2 are rises averaging
+21.5 %, 18 of 21 into Q3 are falls averaging −16.2 % (16.1) — so a quarterly
denominator builds the calendar into the value, in the session that takes the
calendar out of the badge.

Measured, island rows, the wrong formula against the right one:

| | Mean gap | Worst gap |
|---|---|---|
| Condominium | 0.34 months | **3.48** |
| Plex | 0.23 | **5.14** |
| Single-family | 0.17 | **3.32** |

And **11 of 75 island slices fall in a different market condition**. The
quarterly version put plex above 10 months and would have shown a buyer's
market that has never happened.

⚠️ **The two also tell different stories, and only one of them is the market.**
Condo, island, the correct formula: a monotonic climb from **3.4** at the 2022
trough to **8.3** in 2026 Q2, without a single reversal. The quarterly version
ran 3.2 → 7.4 → 8.3 → 7.2 → 5.5 → 7.6 over the same span. **The oscillation was
the season, not the market.**

This is also section 29 of the brief, *Market Regime*, which had never been
built.

### The bands are the publisher's, the arithmetic is ours

| Months of inventory | As APCIQ words it |
|---|---|
| **< 8** | « favours sellers (seller's market) » |
| **8 to 10** | « balanced, meaning that it does not favour buyers or sellers » |
| **> 10** | « favours buyers (buyer's market) » |

⚠️ **They live in the DAX below rather than in a seed, and that was decided
rather than overlooked.** By the rule of J4.1 a published constant belongs in a
seed carrying `source_url` and `retrieved_on` per row, as the three mortgage
schedules do. A seed would have turned a Desktop-only change into a dbt change.
**This is the second place that rule is knowingly bent**, after the 80 %
loan-to-value threshold, and it is written down as such in
`docs/limitations.md` limitation 21. The control is `scripts/report_oracle.py`,
which classifies the same three bands from SQL.

⚠️ **Do not reach for these thresholds from memory.** They are 8 and 10, not the
4-to-6 of the North American convention, and guessing would have put the island
in a buyer's market for years.

**What they say about the island**, 29 quarters × 3 types, APCIQ's formula and
bands: **87 slices, zero in a buyer's market, ever.** Condominium is a seller's
market on 28 of 29 quarters; its single balanced quarter is **2026 Q2, the last
of the archive**. Plex is balanced on two, single-family on none.

### The measures

**The `(selected area)` wrapper is read from the live model, not from 9.5.**
That section describes it as two `ISFILTERED` tests on `Place`; the model has
since factored the test into a measure, `[Area is narrowed]`, and
`Active listings (selected area)` reads
`VAR PlaceChosen = [Area is narrowed] = 1`. **Everything below mirrors that
exactly** — a wrapper that tests something else returns the island aggregate
under a selected sector, which is a plausible number and not an error.

⚠️ **Confirmed in Desktop on 2026-09-17: `fact_market_trailing_12m` IS in the
model, and its relationship to `'date'` runs from `edition_quarter_start_date`.**
The nine-month trap below did not happen. It is written down because the table
had never been read by a visual, and because the same check was skipped on
2026-09-09 and cost a session.

```dax
Inventory corroboration (selected area) =
VAR PlaceChosen = [Area is narrowed] = 1
RETURN
    IF (
        PlaceChosen,
        CALCULATE (
            SELECTEDVALUE ( fact_market_trailing_12m[active_listings_corroboration] ),
            fact_market_trailing_12m[is_island_aggregate] = FALSE ()
        ),
        CALCULATE (
            SELECTEDVALUE ( fact_market_trailing_12m[active_listings_corroboration] ),
            fact_market_trailing_12m[is_island_aggregate] = TRUE ()
        )
    )
```

⚠️ **THIS MEASURE EXISTS BECAUSE THE VERDICT MUST BE READ IN THE SAME PERIMETER
AS THE SUMS.** A bare `SELECTEDVALUE ( fact_market_trailing_12m[…] )` sees
**nineteen rows** when no sector is selected — the island *and* its eighteen
sectors — and returns BLANK the moment any two of them disagree. Today they
never do: on the four defective editions every geography carries
`not_reconciled_across_pages`, so the bare version would work by luck. Wrapping
it makes it read the one row the card is about.

It is also the only place the verdict is fetched, so the value measure and the
detail line cannot drift apart.

```dax
Months of inventory (selected area) =
VAR PlaceChosen = [Area is narrowed] = 1
VAR Inventory =
    IF (
        PlaceChosen,
        CALCULATE (
            SUM ( fact_market_trailing_12m[active_listings] ),
            fact_market_trailing_12m[is_island_aggregate] = FALSE ()
        ),
        CALCULATE (
            SUM ( fact_market_trailing_12m[active_listings] ),
            fact_market_trailing_12m[is_island_aggregate] = TRUE ()
        )
    )
VAR SalesTrailing =
    IF (
        PlaceChosen,
        CALCULATE (
            SUM ( fact_market_trailing_12m[sales_count] ),
            fact_market_trailing_12m[is_island_aggregate] = FALSE ()
        ),
        CALCULATE (
            SUM ( fact_market_trailing_12m[sales_count] ),
            fact_market_trailing_12m[is_island_aggregate] = TRUE ()
        )
    )
RETURN
    IF (
        [Inventory corroboration (selected area)] = "corroborated",
        DIVIDE ( Inventory, DIVIDE ( SalesTrailing, 12 ) )
    )
```

⚠️ **The island / sectors switch is exclusive by construction here too**, for
the reason measured on 2026-08-31: without a geography filter the nineteen rows
add up and sales come to exactly ×2.0000 the island row. A card that silently
doubled its denominator would show half the months of inventory, and 4.2 is as
plausible as 8.3.

**Format `0.0" months"`.** Not a currency, not a percent.

**Numerator and denominator are each summed before the division**, which is what
makes the measure correct on a selection of several sectors. A ratio of sums is
not a sum of ratios, and the card must not average eighteen sector ratios.

```dax
Months of inventory change        = YoYBadge ( [Months of inventory (selected area)], "percent" )
Months of inventory change colour = YoYBadgeColour ( [Months of inventory (selected area)], TRUE )
```

`higherIsBetter = TRUE`: more months of inventory means more choice and less
competition for a first-time buyer. Same convention as `Days on market`, and
`Colour convention note` covers it.

### ⚠️ THE REFUSAL IS ON THE VALUE, NOT ONLY ON THE BADGE

14.7 lets the card print `Active listings` on a contradicted quarter and refuses
only the change, which is right: the count is what APCIQ published, and we show
what it published. **Months of inventory is ours** — a figure APCIQ never
printed for a sector, derived from a numerator the mart declares unreliable.
Showing it would assert something we cannot support, and **no control total
covers it**: it inherits whatever the inventory column is worth.

The quarters are the same four as ever — 2021 Q4, 2022 Q1, 2022 Q2, 2023 Q4,
twelve island slices — carried on `fact_market_trailing_12m` as
`not_reconciled_across_pages`.

And the reason it matters here rather than there is measured: on those quarters
the twelve-month ratio comes out at **3.5, 3.4, 3.4 and 7.0**, each sitting
inside its own trend. **A wrong number that looks wrong costs nothing; this one
looks right.**

No extra guard is needed on the badge: `YoYBadge` receives BLANK from the value
measure and returns BLANK by its own `ISBLANK` test. **The refusal is written
once, in the value.**

### ⚠️ `fact_market_trailing_12m` MAY NOT BE WIRED IN THE MODEL

It has been in the database since J3.5 and **no visual has ever read it**. This
is exactly the position `fact_mortgage_scenario` was in on 2026-09-09: in the
model since J4.1, its relationship to `'date'` missing, and the first measure to
touch it returned a perfectly plausible number in which the property type
filtered and the quarter did not.

Before building anything: check the table is in the model, and that it has a
relationship to `'date'` and to `Sector`.

⚠️ **The relationship runs from `edition_quarter_start_date`, never from
`period_start_date`.** The second is the first day of the twelve-month window,
nine months earlier — the quarter slicer would silently select the wrong row.
`period_start_date` and `period_end_date` are there to say what the window
covers, not to join on.

## 16.5 The raw stock does not disappear, it moves down a level

The card visual carries a second level under the reference label — `Detail` —
which is what makes this a replacement and not a loss. One card, three lines:

```
8.3 months
▲ 23.9 % vs 2025 Q2
Balanced market
```

⚠️ **The detail carries the MARKET CONDITION, not the raw stock** — decided
2026-09-17, once the publisher's thresholds were in hand. A reader who sees
`8.3 months` still has to know what 8.3 means; a reader who sees
`Balanced market` does not. The stock leaves the page, and that is the trade:
it is the numerator, it is in the oracle, and nothing on the page derived
from it is now hidden.

```dax
Inventory detail =
VAR Months = [Months of inventory (selected area)]
RETURN
    SWITCH (
        TRUE (),
        [Inventory corroboration (selected area)] <> "corroborated",
            "inventory contradicted by the publisher this quarter",
        ISBLANK ( Months ),
            "no inventory published",
        Months < 8,   "Seller's market",
        Months <= 10, "Balanced market",
        "Buyer's market"
    )
```

⚠️ **8 and 10 are APCIQ's, and this is the one place they are written.** The
value measure does not classify and the detail does not compute — so there is
exactly one definition of each band on the page, which is the lesson of
2026-08-30, when two definitions of one threshold disagreed on 44 slices out
of 87.

⚠️ **The order of the branches is the guard.** Corroboration first, blank
second, bands last. Tested the other way round, `BLANK () < 8` is TRUE in DAX
and a quarter with no figure would read *Seller's market* — the blank/zero
trap, eleventh appearance on this project.

**The detail is where the refusal explains itself.** A blank card with no
sentence under it reads as a broken visual; a blank card that says *inventory
contradicted by the publisher this quarter* reads as a report that knows what it
does not know. This is the same device as `Price status`, and it costs no
visual.

## 16.6 Page 2: the median tract's income replaces `Tracts evaluated`

### Why not price-to-income

Condo × couple, restated basis — the one on screen:

| Quarter | Median ratio | Share within reach |
|---|---|---|
| 2021 Q4 | 4.52 | 82.8 % |
| 2023 Q4 | **4.32** | **56.3 %** |
| 2026 Q2 | **4.31** | **78.1 %** |

**Two quarters whose ratio agrees to 0.01, twenty-two points of affordability
apart.** A card reading `4.31 ▼ 0.2 %` beside a card reading `78.1 % ▲ 22 pts`
contradicts its neighbour on screen. This is the 2026-09-02 result — the one
that took the ratio out of the map tooltip — remeasured on 2026-09-17 and
unchanged: **a price-to-income ratio contains no interest rate**, and the rate
is what made the round trip.

### The measure, and why the existing one cannot be used

⚠️ **`Household income (theoretical)` returns BLANK above a single census
tract, by design** — it is verrou n° 1 of J4, and 8.4 spells it out. Dropped on
a KPI card that aggregates 512 tracts it would be permanently empty. What the
card can honestly show is the **median of the tract medians**, a statement about
the distribution, which is not the same object as a median income of the island
— that one does not exist in this model and cannot be computed from it.

```dax
Household income (median tract) =
VAR TractsWithIncome =
    FILTER (
        VALUES ( Census_Tract[geography_code] ),
        NOT ISBLANK ( [Household income (theoretical)] )
    )
RETURN
    MEDIANX ( TractsWithIncome, [Household income (theoretical)] )
```

Each iteration holds one tract, so the guard inside `Household income
(theoretical)` is satisfied and the model's single hardest rule is respected
rather than worked around.

### ⚠️ THE `FILTER` IS NOT DECORATION — WITHOUT IT THE CARD READ 109,760 RATHER THAN 111,022

Written without it on 2026-09-17, built, and caught on screen. **The wrong
figure is exactly the median of all 541 tracts with the 11 that publish no
income counted as zero** — verified in SQL: rank 264 is 109,760, rank 265 is
111,022, and `coalesce ( income, 0 )` over 541 rows returns 109,760 to the
dollar.

Eleven census tracts StatCan suppresses were pulling the median down. That is
**section 41.1 of the brief broken in the place it is hardest to see**: not an
invented figure, a missing one silently valued at zero — and on the one card
whose whole purpose is to say what a household earns.

⚠️ **The lesson is about the guard, not about MEDIANX.** `Household income
(theoretical)` returns BLANK above one tract *and* on a tract with no income.
The guard is written, it fires, and it was trusted because an iterator was
assumed to skip blanks. **A guard that returns BLANK is only a guard if
whatever consumes it honours the BLANK.** Twelfth appearance of the blank/zero
trap here, and the first one written into a specification by someone who had
just finished listing the other eleven.

**The control is the oracle**, which medians over tracts that have a value and
whose figure the card must match to the dollar. It was made to count distinct
tracts earlier the same day, for a different reason — which is why the two
figures could be compared at all.

**Label the card *Median tract income (theoretical)*.** The parenthesis carries
what was done to the number, in the one place a reader is looking.

### ⚠️ It takes no badge, and the reason is measured

`household_income` — the 2020 census figure every restated value derives from —
has **exactly one distinct median across all 29 quarters: $88,000**. The
restated median moves from $87,128 in 2019 Q2 to $111,022 in 2026 Q2, and
**every dollar of that movement is the CPI factor**. A badge on this card would
be an inflation gauge wearing the livery of a market indicator, sitting in a row
where the other three badges report the market.

So: **no reference label on this card.** Not a grey one — a grey badge in a row
of green and red ones still invites the reading it must not get.

What the card earns instead is its position. Placed beside `Income required,
lower bound`, the two numbers are both in dollars and **the gap between them is
exactly what the map below colours**. The reader reads the shortfall instead of
computing it.

### `Tracts evaluated` moves into the detail

```dax
Tracts detail =
VAR Evaluated = [Tracts evaluated]
RETURN
    IF (
        NOT ISBLANK ( Evaluated ),
        "of " & FORMAT ( Evaluated, "#,0" ) & " tracts evaluated"
    )
```

It goes under `Share of tracts within reach`, whose denominator it is.

⚠️ **Keeping it on screen is not politeness, it is the 2026-09-10 finding.**
Across 28 transitions the evaluated count moves by ±8.4 tracts on condo, **±40.6
on plex and ±85.0 on single-family, worst case −258**. A share that moves ten
points can be entirely tracts entering or leaving the base. Dropping the number
off the page without putting it anywhere would leave a percentage whose
denominator nobody can see.

`Tracts evaluated change` and `Tracts evaluated colour` become unused, as do
`Listings change` and `Listings change colour` from 16.4.

⚠️ **The four are deleted FROM THE MODEL and kept in THIS FILE**, and the
distinction matters in both directions. In the model, a measure no visual reads
and that still calls `QuarterBadge` blocks the deletion of the old functions —
Desktop refuses, for a reason unrelated to anything still being in use. In this
file, 14.7 keeps `Listings change` written out in full because it is the
report's only worked example of a corroboration guard, and the 3.2 index marks
all four SUPERSEDED with what replaced them.

**The document keeps the memory; the model stays clean.** A live definition
nobody reads is a measure waiting to be dropped onto the wrong card — which is
exactly what happened on 2026-09-12 with two stale definitions found in this
very file.

## 16.7 What does not change, and it is worth stating

- **No dbt model, seed or test moves.** `git status` on `dbt/` is the proof, and
  the build is not re-run because there is nothing to rebuild.
- **Pages 3 and 4 keep no badges**, for the reasons in 14.1: page 3's
  denominator runs from 7 to 18 sectors, and page 4 slices by **year**, multi-
  select, where "the previous period" has no meaning. Acceptance case 9 still
  requires page 3 to come back untouched.
- **The palette is unchanged.** `#B8E0C5` / `#FA584C` / `#8FA3B5`, measured
  against the dark theme on 2026-09-11, worst pair 24.0. Nothing about the
  comparison window touches colour.
- **The seven callout icons are unchanged**, except that the listings icon now
  sits on a card about inventory duration rather than inventory size. It is a
  stack of layers; it still reads.

## 16.8 Acceptance

Run `python scripts/report_oracle.py` with the tunnel open and compare on
screen. **Cases 2, 5 and 7 are the ones that bite.**

| # | Set this | Expect |
|---|---|---|
| 1 | Page 1, condo, any quarter from 2020 Q2 on | four badges, each ending **`vs <same quarter, previous year>`** |
| 2 | Page 1, condo, 2026 Q2 | **the four badges match the oracle to one decimal.** This is the case that was skipped on 2026-09-10 and let six wrong badges ship |
| 3 | Page 1, condo, **2019 Q2 → 2020 Q1** | **no badge at all**, on any of the four cards. Four quarters, not one |
| 4 | Page 1, plex, a sector with a gap | the badge is absent where the oracle says absent — the island never exercises this guard |
| 5 | Page 1, condo, **2021 Q4 / 2022 Q1 / 2022 Q2 / 2023 Q4** | the inventory card is **empty**, and the detail reads *inventory contradicted by the publisher this quarter*. ⚠️ A number in the 3–4 range here means the guard did not land |
| 6 | Page 1, condo, step 2023 Q1 → 2026 Q2 | **5.9 → 8.3, climbing every step but one.** The quarterly formula oscillated here; this one must not |
| 7 | Page 2, condo × couple, 2026 Q2 | income card reads **$111,022** and **carries no badge**. A badge here is the defect of 16.6 |
| 8 | Page 2, the share card | detail reads *of 512 tracts evaluated*, and the share still matches the oracle |
| 9 | Page 3 and page 4 | **unchanged.** No badge, no new card, no moved visual |
| 10 | Any page, two quarters selected in the slicer | every badge **disappears**. `SELECTEDVALUE` returns BLANK on two quarters and that is the intended behaviour |

⚠️ **Case 3 is the one that will look like a defect and is not.** Four blank
quarters at the start of the archive is the honest cost of the twelve-month
window, it is written in 16.1, and it must not be "fixed" by falling back to the
previous quarter — that would put two comparison windows in one badge with
nothing on screen saying which is in force. The oracle counts them: **72 sector
slices per property type** carry no badge, which is 18 sectors × 4 quarters.

⚠️ **AND CASE 2 CARRIES A TRAP THAT LOOKS EXACTLY LIKE THE 2026-09-10 DEFECT.**
On the recipe slice — 2026 Q2, condo, island — the median price badge reads
**▲ 0.1 %**, because the condo median really is flat against 2025 Q2. A badge
reading a tenth of a percent is precisely what the missing `* 100` produced, and
the instinct will be to "fix" a figure that is right.

**What separates the two is how many cards say it.** The defect put a tenth of a
percent on *four unrelated cards at once*; here the other three read −10.3 %,
+12.5 % and +29.5 % on the same slice. **One small number is a market; four are
a bug.** Check the neighbours before touching the formula.

⚠️ **A movement may disagree with the oracle by 0.1 and both be right.** The
oracle rounds the two shares and prints their difference; `YoYBadge` subtracts
the full-precision values and rounds once. On the page-2 share this is visibly
78.1 − 76.2 printed as **2.0**. Same class of false disagreement as `rank()`
against `RANKX ( .., DENSE )` and 56.25 % rounded two ways — **read the oracle's
own movement column, not the subtraction of its two neighbours.**

**Where a price badge must vanish, after the window change** (sector slices from
2020 Q2 on): condo **5**, plex **16**, single-family **33**. Fewer than under
the quarterly window — a price missing twelve months back is rarer than one
missing three months back, on series that fill in over time. **Case 4 is still
run on plex**, which has three times the gaps of condo.
