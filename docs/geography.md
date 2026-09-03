# The geography model

Geography is the axis every source in this project joins on, and no two sources
carve the island the same way. This document states how the model handles that,
what is verified, and what is deliberately left undone.

Everything below was checked on **2026-08-23** against files actually
downloaded. Nothing is recalled.

---

## 1. Three carvings of one island

| Carving | Who publishes it | Units | Grain |
|---|---|---|---|
| Administrative | Ville de Montréal | 19 boroughs + 15 linked cities = **34** | Borough / municipality |
| Market | APCIQ, *Baromètre résidentiel* | **18 sectors** on the island (51 in the metro area) | Sector |
| Statistical | Statistics Canada | 1 004 census tracts in CMA 462 | Census tract |

They do not nest into one another. The model exposes that rather than
smoothing it, which is section 22 of the original brief.

---

## 2. What the model contains

### `marts.dim_geography` — 595 rows

| `geography_type` | Rows | Geometry | Parent |
|---|---|---|---|
| `island` | 1 | ✅ union of the 34 | — |
| `municipality` | 16 | ✅ | `island:mtl` |
| `borough` | 19 | ✅ | `municipality:66023` |
| `apciq_sector` | 18 | ✅ union of the tracts each draws — section 5 | `island:mtl` |
| `census_tract` | 541 | ✅ | `municipality:…` |

Census tracts are parented to their **municipality**, not to their borough,
because no published source says which borough a tract is in. Ville de Montréal
therefore holds 485 tracts directly, which looks coarse and is honest. Reaching
the borough — and the APCIQ sector — is section 7.

Since 2026-09-02 the census tract rows also carry **`admin_place_name`**, the
borough or linked city a reader would call the tract's neighbourhood. It is
NULL on every other level, where the row already is a place. It names a tract;
it never groups a figure — section 7.4.

`area_km2` carries `area_basis` beside it, because the families do not mean the
same thing by "area": administrative boundaries run out into the water (the
island measures 619 km²), tract polygons stop at the shore (499 km²). Both are
correct about different questions, and adding them is not one of them. **APCIQ
sectors sit with the tracts** — they are built from tract polygons, so the 18 of
them measure the same 499 km², and a sector cannot be compared on area with a
borough without reading that column.

The key is readable rather than hashed: `borough:REM19`, `municipality:66112`,
`apciq_sector:8`. A row is identifiable at a glance in Power BI and in a
failing test.

**The island is 16 municipalities, not one.** Ville de Montréal (MAMH code
`66023`) plus 15 linked cities. Only Ville de Montréal is subdivided, into 19
boroughs — which is why `borough_code` is legitimately NULL for 15 % of the
assessment roll rather than missing.

Ville de Montréal is not a feature in the source file. It is assembled as the
union of its 19 boroughs.

### `marts.bridge_apciq_sector_geography` — 36 rows

One row per (sector, administrative entity) link, each marked `full` or `part`.
36 links for 34 entities: the two extras are the two boroughs APCIQ splits.

### `marts.bridge_census_tract_apciq_sector` — 543 rows

One row per (tract, sector), with the share of the tract's population that the
row accounts for. 543 rows for 541 tracts: one tract is genuinely shared, one
more reaches into a second sector across land where nobody lives. **This is the
table that lets a census income meet an APCIQ price** — section 7.

---

## 3. The join key, and why it works

`CODEMAMH`, in the city boundary file, carries **two nomenclatures at once**:

```
Ville liée      ->  5-digit MAMH municipality code   66112 = Baie-D'Urfé
Arrondissement  ->  REMxx borough code               REM19 = Ville-Marie
```

The MAMH assessment roll already extracted (`ingestion/mamh_roll/`) carries
both, in `municipality_code` and `borough_code`. The 15 linked-city codes in
the boundary file match the 15 non-Montréal municipality codes in the roll,
one for one.

**Geography therefore joins to the assessment roll on published codes, never on
names that resemble each other.**

---

## 4. The two splits, and what they forbid

APCIQ's sector boundaries cross two borough boundaries:

| Borough | Sector A | Sector B |
|---|---|---|
| Côte-des-Neiges–Notre-Dame-de-Grâce (`REM34`) | **7** — NDG + Montréal-Ouest | **8** — Côte-des-Neiges + Côte-Saint-Luc |
| Verdun (`REM12`) | **4** — Verdun + Le Sud-Ouest | **10** — L'Île-des-Sœurs |

Both boroughs are single polygons in the city file; the sector line runs
*inside* them. Each sector also picks up a linked city that is not part of the
borough at all.

**What this makes impossible:**

- There is **no APCIQ median price for the borough CDN–NDG.** Two medians of
  two overlapping-but-different populations do not combine into one.
- A borough-level figure (assessment roll, census) **cannot be split** between
  sectors 7 and 8 without an assumption.

**What the model does about it:** the bridge returns two rows for each of these
boroughs. Anyone who joins market data to boroughs sees the ambiguity in the
result instead of a single confident wrong number. This is a detrompeur, not a
comment in a README.

### A name that hides its contents

Sector **9 is called "Centre"** and contains Hampstead, Mont-Royal, Outremont
and Westmount — three linked cities and one borough, none of them central.
Sector names must never be read as geography.

### What this costs anything that filters by place, measured 2026-08-31

The two splits above are the celebrated cases, and they are not the common
one. **The direction that matters is sector → places, not place → sector.**
32 of the 34 administrative entities resolve to exactly one APCIQ sector — a
true statement that invites the wrong conclusion, because a sector usually
holds several entities.

Counting the other way, over the 36 bridge rows:

| Entities also shown when one is picked | Entities |
|---|---|
| none — the sector holds only it | **8 of 34** |
| one more | 10 |
| two more | 1 |
| three more | 8 |
| **six more** | **7** |

The seven worst are the municipalities of sector 1, *Ouest-de-l'Île-Sud*:
Baie-D'Urfé, Beaconsfield, Dorval, L'Île-Dorval, Pointe-Claire,
Sainte-Anne-de-Bellevue and Senneville. Asking for any one of them returns all
seven, because APCIQ prices the group and not its members.

The eight that answer for themselves alone: Saint-Laurent,
Ahuntsic-Cartierville, Ville-Marie, Le Plateau-Mont-Royal, Rosemont–La
Petite-Patrie, Villeray–Saint-Michel–Parc-Extension,
Mercier–Hochelaga-Maisonneuve, Montréal-Nord.

**Consequence for any report that lets a reader choose a place:** naming what
is actually on screen is not a courtesy for two edge cases, it is a permanent
requirement for twenty-six of thirty-four. `coverage` flags the two split
boroughs; it does **not** flag this, because nothing is split here — the place
is whole, the sector around it is simply larger. See `powerbi/report-design.md`
section 9.

⚠️ **And a place that reaches two sectors is not automatically a place without
data.** Verdun's sector 10 (*L'Île-des-Sœurs*) has no plex price in any of the
29 quarters, while its sector 4 has all 29. Counted over bridge rows, Verdun
looks unpriced on plex; counted as a place — which is what a reader selects —
it is priced. **16 places have no plex price ever, not 17.**

---

## 5. Where APCIQ sector outlines come from

> **Built on 2026-08-31, session J4.2½.** This section used to be titled *Why
> APCIQ sectors have no geometry*, and it described a construction that was
> never carried out. The 18 sectors now carry a polygon in
> `marts.dim_geography`. **The construction that was finally used is not the
> one this document planned**, and the reason is section 7: once every census
> tract had a sector, the sectors could be assembled from the tracts.

APCIQ publishes no boundary file. Page 6 of the Baromètre lists which
municipalities and boroughs make up each sector, and that is all. The outlines
here are therefore **derived**, and the derivation is one line long:

> **A sector is the union of the census tract polygons it draws.**

One source file — the Statistics Canada cartographic boundaries — so there are
no two shorelines to reconcile, and the map is drawn on exactly the geography
the figures are attached to.

### The rule the union needs, and what it costs

`bridge_census_tract_apciq_sector` shares a tract between sectors **by
population**, because population is what a household income describes. A
surface cannot be shared that way. A map paints whole polygons: a tract
weighted 92.9 % / 7.1 % would be painted in both sectors, and painting it twice
is not a shared shape, it is an overlap.

So the bridge carries a second rule for drawing only, in the column
`is_drawn_in_this_sector`: **each tract is drawn in the sector where the
majority of its residents live.** Exactly one row per tract carries it, 541 of
the 543.

Without that rule, measured on 2026-08-31:

| Overlapping pair | Area | Where it comes from |
|---|---|---|
| sectors **2 and 5** | 1.529 km² | `4620511.02`, the genuinely shared tract of J3.4 |
| sectors **5 and 6** | 0.304 km² | `4620421.05`, which carries a **zero-weight** row |

The second one is worth pausing on. J3.4 deliberately kept a zero-weight bridge
row for a tract that reaches into a second sector across land where nobody
lives — *"the reach is real and a later census could put people there"*. That
decision is right for the figures and wrong for the drawing, because **a
surface has no weight**: a zero-weight row hands over the whole polygon. A
bridge built to divide residents cannot be reused unchanged to divide pixels.

**What the rule costs is one disagreement between the map and the tables**, and
it is a column rather than a silent adjustment so that anyone can find it:

    4620511.02    476 residents COUNTED in sector 5, DRAWN in sector 2
    4620421.05    a zero-weight row in sector 6, drawn in sector 5

476 people is 0.024 % of the island, on 1 tract out of 541. The alternative —
cutting the shared polygon — is what J3.4 examined and rejected, and nothing
here reopens it: the cut would follow a line APCIQ has never published.

The rule also needs no tie-break, and that was **measured, not assumed**: no
tract has two rows of equal weight. The sector number decides if one ever
appears, so a redraw stays reproducible.

### The proof, which is an equality and not a tolerance

Measured 2026-08-31, and held by
`assert_apciq_sector_geometry_tiles_the_island`:

| Measurement | Value |
|---|---|
| sum of the 18 sector areas | **499.627 km²** |
| area of their union | **499.627 km²** |
| area of the 541 census tracts | **499.627 km²** |
| overlapping pairs above 1 m² | **0** |

Only a partition produces those three numbers at once: dropping a tract lowers
the first two, duplicating one raises the first alone. A second, independent
check agrees — the exported sector file and the exported tract file have the
**same bounding box to the last published decimal on all four sides**.

Two positive witnesses were run before the result was believed. Removing the
majority clause returned 501.462 km² and named both overlapping pairs; dropping
a single tract from the drawing returned 499.163 km². The test sees both
failure modes.

### Three things this geometry is not

**1. It is not APCIQ's own line.** Where APCIQ splits a borough it publishes
two names and no boundary. Which tracts fall on each side was settled in
section 7 against a city neighbourhood file — a derived assumption, carried on
every bridge row by `assignment_method`, and inherited by these polygons.

**2. It does not tile in the topological sense.** The union is exact in
**area**, but the source polygons do not all touch. Sector 3 comes out as two
halves of 17.48 and 15.95 km², **13.3 m apart, with no other sector between
them** — the tracts of one municipality that the source file did not draw
edge to edge. Sector 11 (Ville-Marie) carries three interior rings downtown, of
0.223, 0.222 and 0.003 km², which no island tract covers. None of this is
visible at the scale any map here is read at, but *"it tiles by construction"*
would claim more than has been measured, so it is stated instead.

**3. A sector is not one piece, and that is mostly correct.** Ten of the
eighteen come out in several parts, from three different causes that must not
be confused:

| Sector | Parts | Cause |
|---|---|---|
| 3 — Lachine/Lasalle | 34 | the sub-metric gaps above, plus islands |
| 2 — Ouest-de-l'Île-Nord | 18 | the archipelago |
| 1 — Ouest-de-l'Île-Sud | 14 | the archipelago; 99.6 % sits in one part |
| 9 — Centre | 3 | **real geography** — Hampstead, Mont-Royal, Outremont and Westmount do not all touch |

Sector 9 in three large pieces is a **non-regression signal**, not a defect:
the fragmentation reproduces the composition APCIQ publishes on page 6.

### Why the carving planned here was abandoned

The construction this section used to describe was to cut the two split
boroughs with a neighbourhood file as a knife
(`ST_Intersection` / `ST_Difference`) and assemble three files. It was sound,
and it is no longer the best available, for one reason: **a cut inherits every
disagreement between the files it cuts.** The measurements that made the case
for it are still true and still useful — they are kept here because they
document the source, not the method:

| Borough | Cutting file | Admin area | Neighbourhood pieces | Difference |
|---|---|---|---|---|
| CDN–NDG (`REM34`) | quartiers sociologiques | 21.4909 km² | 21.4880 km² | **0.44 %** |
| Verdun (`REM12`) | quartiers de référence | 22.2952 km² | 9.8467 km² | **55.9 %** |

The first is digitising noise between two files drawn twelve years apart. **The
second is not an error: administrative boundaries include water.** Verdun
reaches the middle of the St. Lawrence; the housing-reference neighbourhoods
cover inhabited land only. The same effect is why the island measures 619 km²
in the administrative rows and 499 km² in the tract rows.

That is also why `dim_geography.area_basis` puts the sectors with the **tracts**
(`land_only`) and not with the boroughs (`boundary_including_water`). **A
sector and a borough cannot be compared on area without reading that column
first.**

Both neighbourhood files are still in use — but in section 7, to place *points*
inside polygons, which collects none of the edge disagreements a cut would
have.

### The exported shape file

`scripts/export_map_shapes.py` writes both map layers from
`marts.dim_geography`, never from a downloaded lookalike:

| File | Features | Key property | Size |
|---|---|---|---|
| `powerbi/shapes/apciq_sector_island.geojson` | 18 | `sector_id` | 720 kB |
| `powerbi/shapes/census_tract_island.geojson` | 541 | `ct_uid` | 1 307 kB |

**The 18-shape file is the smaller of the two**, because the union erases every
internal border. Both are versioned: the Statistics Canada licence permits
redistribution, and without them nobody could redraw the maps after a clone.

---

## 6. Traps found, and the guards against them

### The dataset publishes two GeoJSON files

`limites-administratives-agglomeration` exposes a WGS84 file **and** a NAD83
one, and the CKAN API lists the NAD83 one first. Its coordinates are metres.

Loading it raises nothing: the row count is right, the geometries are valid,
and every spatial join afterwards returns **no rows**. There is no symptom.

*Guard:* resources are addressed by filename, and `ckan.check_crs()` refuses
anything but CRS84 before a row is written. A test asserts the refusal.

### `ST_GeomFromGeoJSON` returns SRID 0

Not 4326. PostGIS then refuses to compare the result with anything. The staging
model wraps every conversion in `ST_SetSRID(..., 4326)`.

### `ST_Area` on a 4326 geometry returns square degrees

About 0.06 for this island — a number that looks like an area and means
nothing. The model casts to `geography` first. A test fails if the island area
leaves the 100–2 000 km² range, which is a unit guard, not a measurement.

### `ST_Contains` fails where `ST_Covers` succeeds

Ville de Montréal is built as the union of its boroughs, so every borough
touches its outer edge from the inside. `ST_Contains` excludes boundary
contact and would reject all 19. `ST_Covers` is the correct predicate whenever
the container was assembled from the contained.

### `ST_Area` in EPSG:3347 returns metres², and they are 3.3 % too many

Found on 2026-08-24, loading the census tract boundaries. This one is worse
than the square-degrees trap above, because it produces a **plausible** number.

EPSG:3347, *NAD83 / Statistics Canada Lambert*, is the projection Statistics
Canada ships its boundary files in. It is a Lambert **conformal** conic: it
preserves angles, not areas, and its standard parallels are 49° and 77°.
Montréal sits at 45.5°, well south of both, where the scale factor is greater
than one — so every area comes out inflated, by the same amount, silently.

Measured over the 541 tracts of the Island, against the land area the file
states for each one:

| How the area was computed | Total | Against the published figure |
|---|---|---|
| `ST_Area` in EPSG:3347 | 514.69 km² | **+3.29 %** |
| `ST_Area` on `::geography` | 499.63 km² | +0.27 % |
| `ST_Area` in EPSG:32188 (MTM zone 8) | 499.53 km² | +0.25 % |
| Published `LANDAREA` | 498.29 km² | — |

*Guard:* compute areas geodesically by casting to `geography`, or reproject to
a local system such as MTM zone 8. Never in 3347, whatever the file arrived
in. The residual quarter of a percent is not projection error — it is the
polygon holding a little water that the published **land** area excludes.

### Two files can disagree about where the shore is

Also 2026-08-24. Of the 541 census tract polygons, **523 are entirely covered
by the city's administrative boundary and 18 poke out of it** — by 0.000 % to
6.6 % of their own area, with fifteen of the eighteen under 1.6 %.

This is not a tract reaching off the Island. The attribute file places all 541
inside Island municipalities at dissemination-block level, and the decisive
check is that **all 3 228 dissemination-area representative points fall inside
the city boundary, without a single exception.** Two organisations digitised
the same shoreline and did not trace it identically; the disagreement lives on
the water's edge, where nobody lives.

*Guard:* never use one file's polygon to decide membership in another file's
geography. Membership comes from published codes — `csd_uid`, `CODEMAMH` —
and geometry is for drawing and for measuring, not for deciding. Where a
spatial test is unavoidable, test a representative point, not a polygon edge.

---

## 7. Attaching census tracts to APCIQ sectors

This is the join the project existed without until 2026-08-24. Household income
is published at census tract; price is published at APCIQ sector; **nothing
published relates the two.** The relation now lives in
`marts.bridge_census_tract_apciq_sector` — 543 rows for 541 tracts.

### The rule, in one sentence

Every dissemination area is placed by the representative point Statistics
Canada publishes for it; that point falls in exactly one borough or linked
city; `bridge_apciq_sector_geography` says which sector that entity belongs to
— and for the only two entities APCIQ cuts in half, a second point-in-polygon
against a neighbourhood file finishes the job.

**No polygon is cut anywhere, and no membership is decided by a polygon edge.**

### Why the carving planned in section 5 was not needed

The plan recorded at the end of J3.3 was to rebuild the eighteen sector
polygons with `ST_Intersection` / `ST_Difference` and then attach tracts to
them. The measurements below were taken **before** any of it was written, and
they removed the need for all of it:

| Measured 2026-08-24 | Result |
|---|---|
| Representative points falling in exactly one of the 34 administrative entities | **3 228 / 3 228** — none outside, none in two |
| Populated tracts falling entirely inside one entity | **532 / 534** |
| Tracts of the two split boroughs resolving through the neighbourhood files | **62 / 62** — not one straddles a sector line |
| Agreement between the point assignment and the share of the tract polygon, over those 62 | **≤ 1.6 points**, and ≤ 0.2 on 60 of them |

Carving would have produced the same answer for 540 tracts and a worse one for
the rest, because a cut inherits every disagreement between the files it cuts.
Section 6 already records that 18 of the 541 tract polygons spill outside the
city's boundaries by up to 6.6 % of their own area; one of the two tracts that
genuinely reaches two sectors also picks up a 0.00 % sliver of a *third*
borough, which exists only because two organisations drew the same shoreline
differently. A point collects none of that.

### The one tract that is genuinely shared

`4620511.02`, on the Pierrefonds-Roxboro / Saint-Laurent line. It carries two
rows, weighted by the population living on each side, because rounding it to
one sector would discard 476 real residents:

| Sector | By population (points) | By area (polygon) |
|---|---|---|
| 2 — Ouest-de-l'Île-Nord | 92.9 % | 93.2 % |
| 5 — Saint-Laurent | 7.1 % | 6.8 % |

Two independent measurements agreeing to 0.3 points is what makes the split
credible rather than merely computed.

### The one tract that only looked shared

`4620195.02` appeared to be 90 % in sector 15 and 10 % in sector 16 — and it is
**not shared at all**. The refutation comes from a number the source publishes
about itself:

- the dissemination area concerned covers **0.0427 km²**, published;
- the entire intersection between its tract and Saint-Léonard is **0.0076 km²**;
- so the area is **5.6 times too large to be there**. Its representative point
  simply landed 10.9 m on the wrong side of the line.

Its 541 residents were being credited to a sector they demonstrably do not live
in. The bridge reassigns them, and the declaration lives in the seed
`statcan_misplaced_representative_point` with the measurement attached.

### The guard this produced

That refutation generalises, and it is now permanent: **a dissemination area
cannot sit in a space smaller than itself.** Statistics Canada publishes each
area's land area, so the claim "this area is inside that entity" is checkable
by arithmetic rather than believed.

Run over all 3 228 areas of the island, the check separates two populations
that are nowhere near each other:

| Overshoot ratio | Areas | What it is |
|---|---|---|
| 1.000 – 1.016 | 12 | shoreline noise — the section 6 trap, again |
| 2.87 and 5.62 | 2 | genuinely somewhere else |

Three orders of magnitude sit between them, so the 1.5 threshold in
`assert_representative_point_fits_where_it_landed` is not a tuned knob: anything
from 1.05 to 2.8 selects the same two rows. The test fails in **both**
directions — on an undeclared area that no longer fits, and on a declaration
that no longer describes anything.

### What remains an assumption, and it is not small

**APCIQ publishes no line between its sector 7 (NDG) and its sector 8
(Côte-des-Neiges).** There is no such line in any APCIQ document — only the two
names, on page 6 of the Baromètre. What stands in for it is Ville de Montréal's
2014 *sociological* neighbourhood boundary: a community-planning line, drawn by
a different body, for a different purpose, twelve years earlier.

That substitution places **40 tracts and 170 583 people**. It is a derived
assumption, not an observation, and `assignment_method = 'neighbourhood_polygon'`
carries it on every row it touches so that nothing downstream can present it as
measured.

Verdun does not carry the same risk: the line between Ile-des-Sœurs and the rest
of the borough is water, so any reasonable delineation puts the same tracts on
the same side.

### And the temporal gap does not close

Income is 2020. APCIQ prices run to 2026 Q2. This bridge makes them *joinable*;
it does not make them contemporaneous. **A 2026 price-to-income ratio is a
displayed assumption, not an observation**, and `census_year` exists downstream
so that no model can forget it.

---

## 7.4 Naming a tract after a place people know

**Added 2026-09-02.** The page 2 map draws 541 census tracts, and `CT 0250.00`
names nothing a reader recognises. Its tooltip therefore had to say where the
tract is — and the APCIQ sector could not: sector 9 is called *Centre* and
holds Westmount, sector 1 gathers seven municipalities.

**No existing bridge could answer, and the reason is the direction.** Composing
`bridge_census_tract_apciq_sector` with `bridge_apciq_sector_geography` runs
tract → sector → places and returns **every** place of that sector, up to seven
names for one tract. The missing direction was tract → place, and it was in no
table. `marts.bridge_census_tract_admin_place` is that direction: 541 rows, one
per tract.

### The rule, and why it is a third one rather than a reuse

A tract is named after the entity where the **majority of its residents** live.
The project now carries three majority-shaped rules, and they are deliberately
not interchangeable because they answer different questions:

| Rule | Where | Question |
|---|---|---|
| population weights | `bridge_census_tract_apciq_sector` | an income describes people, so a shared tract sends its income to both sectors in proportion |
| `is_drawn_in_this_sector` | same table, section 5 | a polygon cannot be painted twice |
| naming majority | `bridge_census_tract_admin_place` | a tooltip has room for one name |

**Measured cost: 476 residents, 0.0237 % of the island, on 2 tracts of 541** —
and they are the same two tracts the drawing rule isolated on 2026-08-31
(`4620511.02`, the one genuinely shared tract, and `4620421.05`, whose second
entity holds nobody). Three independent rules landing on the same two lines is
the strongest evidence available that there is only one real ambiguity here.

`population_named_elsewhere` and `name_is_a_majority_call` carry the cost as
columns, so anyone comparing this name with a map can find the difference —
the same device as `assignment_method` for the CDN/NDG substitution.

### An independent confirmation, free

485 tracts fall in a borough and 56 in a linked city. That is **exactly** the
split the published `csd_uid` of the Geographic Attribute File gives (2466023
against the other fifteen subdivisions), reached here by point-in-polygon
instead of by a code. Two methods, one partition.

### ⚠️ What this column must never be used for

It **names** a tract. It never **groups** a figure. APCIQ publishes at the
sector, and 26 of the 34 places cover a territory larger than themselves
(section 4). Grouping a median price by `admin_place_name` would repeat a
sector total once per place and present it as that place's own.

### The placement itself now lives in one model

`int_geography__dissemination_area_place` holds the point-in-polygon that puts
each of the 3 228 dissemination areas in one of the 34 entities, with the one
declared misplacement corrected. It was lifted **verbatim** out of
`bridge_census_tract_apciq_sector` when the second reader appeared: two copies
of the same join would agree today and drift the day one of them is corrected.

---

## 8. Measured values

| Level | Count | Area (km²) |
|---|---|---|
| Island | 1 | 619.320 |
| Municipalities | 16 | 619.320 |
| Boroughs | 19 | 433.0 |

These are **boundary areas**, which include the water each entity extends over.
They are not land areas and are used as a consistency check, not as an
analytical figure.

---

## 9. Open questions

1. ~~**Does APCIQ sector 4 include L'Île-des-Sœurs?**~~ **Settled 2026-08-23:
   it does not, and the two sectors do not overlap.**

   Page 6 of the Baromètre describes sector 4 as "Le Sud-Ouest (Montréal),
   Verdun (Montréal)" while sector 10 *is* L'Île-des-Sœurs, part of Verdun.
   Either sector 4 excluded it, or the two double-counted it.

   The arithmetic answers without ambiguity. Page 8 of every edition reports
   an Island of Montréal total, published independently of the sector pages.
   Summing the 18 sector pages gives **exactly** that total, on all three
   property categories, in 2019 Q2, 2019 Q3, 2022 Q4 and 2026 Q2 — twelve
   independent control sums, every one of them off by zero. An overlap would
   make the sectors exceed the island.

   *Consequence:* the reconstruction in section 5 is no longer blocked. Verdun
   is cut in two, sector 10 taking L'Île-des-Sœurs and sector 4 the remainder,
   with no part of the borough counted twice.
2. ~~**Exact sector geometries**~~ **Built 2026-08-31**, as the union of each
   sector's census tract polygons, and held by an equality: sum of the parts =
   area of the union = area of the 541 tracts = 499.627 km². Section 5 has the
   construction, the majority rule it needs, and what that rule costs.

   Two things the wording above got wrong and that the build corrected. The
   union does **not** tile *by construction*: it tiles in area, while the
   source polygons leave sub-metric to decametric gaps — sector 3 comes out in
   two halves 13.3 m apart. And it needs a rule the sentence did not
   anticipate, because the bridge divides *residents* and a surface has no
   weight.
3. ~~**Census tract to island**~~ **Settled 2026-08-24.** No spatial join was
   needed at all. The Geographic Attribute File states the municipality of
   every tract outright, and census division 2466 turns out to be exactly the
   island: 16 subdivisions for 16 municipalities, none missing, none extra. The
   perimeter is `csd_uid LIKE '2466%'`. Of the 1 004 tracts of CMA 462, **541**
   are on the island.

   The route judged preferable in principle when the question was written
   turned out to be the one available in fact.
4. **Which line does APCIQ draw between sectors 7 and 8?** `[UNKNOWN]`, and
   probably unknowable from published sources — APCIQ names Notre-Dame-de-Grâce
   and Côte-des-Neiges without ever drawing the boundary between them. Section 7
   substitutes the city's 2014 sociological line and marks every affected row as
   a derived assumption. Only APCIQ could close this, and only by publishing
   something it has never published.

---

## 10. Stability of the APCIQ carving

The 18 sectors, their numbers and their order are **identical** in the
2019 Q2, 2022 Q4 and 2026 Q2 editions of the Baromètre (pages 9 to 26 in all
three). The mapping therefore needs no validity dates, and the whole
2019 Q2–2026 Q2 history is comparable on this axis.

**But the PDF page size changed**: 1008 × 612 pt in 2019 and 2022, 3825 × 2340
in 2026 — a factor of 3.8. A positional parser calibrated on absolute
coordinates from a recent edition will fail on the first twenty quarters. The
J3.2 parser must work in coordinates relative to page height.

---

## Attribution

- Boundaries and neighbourhood datasets: **Ville de Montréal**, CC-BY 4.0,
  <http://creativecommons.org/licenses/by/4.0/>
- Assessment roll: **MAMH / Données Québec**, CC-BY 4.0
- Sector composition: **APCIQ, by the Centris system**. Non-commercial use
  with attribution. Only the geographic nomenclature is reproduced here — no
  price, volume or delay.
