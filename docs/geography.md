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

### `marts.dim_geography` — 54 rows

| `geography_type` | Rows | Geometry | Parent |
|---|---|---|---|
| `island` | 1 | ✅ union of the 34 | — |
| `municipality` | 16 | ✅ | `island:mtl` |
| `borough` | 19 | ✅ | `municipality:66023` |
| `apciq_sector` | 18 | ❌ **NULL** | `island:mtl` |

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

---

## 5. Why APCIQ sectors have no geometry

Their true outlines are reconstructible. Two further CC-BY city datasets were
checked on 2026-08-23:

| Dataset | Features | Solves | Does not solve |
|---|---|---|---|
| `quartiers-sociologiques` | 32 | **CDN / NDG** — both named explicitly | Verdun is one block |
| `quartiers` (Quartiers de référence en habitation) | 91 | **Verdun / Ile-des-Soeurs** | CDN–NDG split into 7 differently-named quarters |

Neither solves both. Building exact sector polygons means assembling geometries
from three files and then proving with PostGIS that the result tiles the island
with no gap and no overlap. That work has not been done.

Until it is, the geometry is NULL. **A NULL that says "not established" is
worth more than a polygon that looks authoritative and is approximate** —
particularly on a map, where nobody questions a shape.

### How it will be built, and why not by union

The obvious construction is `ST_Union(neighbourhood, linked_city)`. It is the
wrong one. The two polygons come from different files drawn twelve years apart,
so their shared edges do not coincide exactly; a union leaves slivers of gap
where they fall short and slivers of overlap where they cross.

The construction that cannot fail is to **cut the administrative polygon using
the neighbourhood polygon as a knife**, and never to take an outer edge from
anywhere but the official file:

```sql
ndg_part = ST_Intersection( borough_REM34 , ndg_sociological )
cdn_part = ST_Difference  ( borough_REM34 , ndg_sociological )
```

By construction `ndg_part ∪ cdn_part = borough_REM34` exactly. The
sociological file supplies only the dividing line.

**Measured on 2026-08-23**, comparing each borough against the union of the
neighbourhood pieces that should fill it:

| Borough | Cutting file | Admin area | Pieces | Difference |
|---|---|---|---|---|
| CDN–NDG (`REM34`) | quartiers sociologiques | 21.4909 km² | 21.4880 km² | **0.44 %** |
| Verdun (`REM12`) | quartiers de référence | 22.2952 km² | 9.8467 km² | **55.9 %** |

The first is digitising noise, and the cut removes it entirely.

**The second is not an error, and it matters beyond this one borough:
administrative boundaries include water.** Verdun extends to the middle of the
St. Lawrence; the housing-reference neighbourhoods cover only inhabited land.
The same effect is why the island measures 619 km² here rather than its land
area. `ST_Difference` simply assigns the river to the larger piece — nobody
sells a condo on it — but a map built without knowing this would show an
inexplicable hole.

**Sequencing.** This construction was waiting on open question 1 below —
whether sector 4 excludes L'Île-des-Sœurs or overlaps sector 10 — because the
answer decides how sector 4 is cut. **The Baromètre settled it on 2026-08-23:
no overlap.** The construction is unblocked.

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

---

## 7. Measured values

| Level | Count | Area (km²) |
|---|---|---|
| Island | 1 | 619.320 |
| Municipalities | 16 | 619.320 |
| Boroughs | 19 | 433.0 |

These are **boundary areas**, which include the water each entity extends over.
They are not land areas and are used as a consistency check, not as an
analytical figure.

---

## 8. Open questions

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
2. **Exact sector geometries** — see section 5. Method decided, prerequisite
   now cleared, construction not started.
3. **Census tract to island** — CMA 462 includes Laval and both shores.
   Restricting to the island is a spatial join against `dim_geography`, to be
   done in J3.3.

---

## 9. Stability of the APCIQ carving

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
