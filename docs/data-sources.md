# Data Source Matrix

Verified inventory of every source feeding the platform. **Every cell below comes from a
request actually issued on 2026-08-21, or from a file actually downloaded.** Nothing here is
recalled from memory. Cells that could not be verified are marked `[UNKNOWN]`.

Verification host: Windows 11, `curl 8.21.0`, `python 3.13.14`, `pdfplumber`. No proxy.

---

## 1. Matrix

| # | Source | Dataset | Key variables | Geographic grain | Temporal grain | History | Format | Access | Auth | Update freq. | Licence | Autom. | Prio | Target table |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Bank of Canada | Valet — rate series `V122514`, `V80691311`, `V80691335`, `BD.CDN.5YR.DQ.YLD` | Overnight rate, prime rate, 5-yr conventional mortgage rate, 5-yr GoC bond yield | Canada (national only) | Mixed: daily (bond), weekly (prime, mortgage), monthly (overnight) | 2015-01-01 to 2026-08-20 (tested) | JSON, CSV | REST API — `GET /valet/observations/{series}/{json or csv}?start_date=` returns **HTTP 200**, 474 315 B | None | Daily (bond series updated 2026-08-20) | [bankofcanada.ca/terms](https://www.bankofcanada.ca/terms/) — "the Bank permits you to freely use, copy, distribute and transmit its website content" with attribution. **Redistribution allowed** | **1**/5 | P1 | `dim_economic_indicator` |
| 2 | Statistics Canada | Table `98100058` — Household income statistics by household type: CMAs, tracted CAs and **census tracts** | Median household total income 2020 and 2015 (2020 constant $), median after-tax income 2020 and 2015, households 2021 and 2016 | **Census tract** (1 004 CTs in Montréal CMA 462) | 2021 Census, carrying a 2016/2015 comparison | Income years 2015 and 2020 | CSV in ZIP | `GET /t1/wds/rest/getFullTableDownloadCSV/98100058/en` returns **HTTP 200**, then ZIP **HTTP 200**, 6 552 215 B | None | Per census (5 years) | [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence) — "use, reproduce, publish, freely distribute, or sell". **Redistribution allowed** | **2**/5 | P1 | `dim_geography`, `fact_affordability` |
| 3 | Statistics Canada (republishing CMHC) | `34100125` — CMHC housing starts, under construction and completions in large centres | Housing starts, under construction, completions, by type of unit | **53 centres — Montréal is NOT among them.** 11 Quebec entries only: Drummondville, Granby, Rimouski, Saguenay, Saint-Hyacinthe, Saint-Jean-sur-Richelieu, Saint-Jérôme, Shawinigan, Sherbrooke, Trois-Rivières, Valleyfield | Monthly | 1965-01 to 2025-01 | CSV in ZIP (284 492 B, 23 893 rows) | `GET /t1/wds/rest/getFullTableDownloadCSV/34100125/en` returns **HTTP 200**, then ZIP **HTTP 200** | None | Monthly | Same [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence). **Redistribution allowed** | **2**/5 | **P3 — currently unusable for this project, see 2.6** | `dim_economic_indicator` |
| 4 | Données Montréal | `unites-evaluation-fonciere` — property assessment units | `ID_UEV`, `NOM_RUE`, `MUNICIPALITE`, `ETAGE_HORS_SOL`, `NOMBRE_LOGEMENT`, `ANNEE_CONSTRUCTION`, `LIBELLE_UTILISATION`, `CATEGORIE_UEF` (incl. `Condominium`), `MATRICULE83`, `SUPERFICIE_TERRAIN`, `SUPERFICIE_BATIMENT`, `NO_ARROND_ILE_CUM` | Property (assessment unit) | Current snapshot only — no history | Metadata modified 2026-08-19 | CSV (76 347 584 B), GeoJSON, SHP | `GET donnees.montreal.ca/dataset/4ad6baea-.../resource/2b9dfc3d-.../download/uniteevaluationfonciere.csv` returns **HTTP 200** — but **403 without a browser `User-Agent`**, see 2.5. Supports HTTP Range (**206**) | None | `[UNKNOWN]` — CKAN exposes no frequency field | CC-BY 4.0 — [creativecommons.org/licenses/by/4.0](http://creativecommons.org/licenses/by/4.0/). **Redistribution allowed** | **2**/5 | P2 | `dim_property_configuration`, housing-stock context |
| 5 | Données Montréal | `limites-administratives-agglomeration` | `CODEID`, `NOM`, `CODEMAMH`, `NUM`, `ABREV`, `TYPE`, `DATEMODIF`, MultiPolygon geometry | **Borough / linked city** — 19 boroughs + 15 linked cities = 34 features | Current snapshot | Metadata modified 2026-08-01 | GeoJSON (1 258 670 B), SHP; NAD83 variant available | `GET donnees.montreal.ca/dataset/9797a946-.../resource/e18bfd07-.../download/limites-administratives-agglomeration.geojson` returns **HTTP 200** (same `User-Agent` requirement) | None | `[UNKNOWN]` | CC-BY 4.0 — [creativecommons.org/licenses/by/4.0](http://creativecommons.org/licenses/by/4.0/). **Redistribution allowed** | **1**/5 | P1 | `dim_geography` |
| 6 | APCIQ (via Centris) | *Baromètre résidentiel* — Montréal, quarterly PDF | Per sector and category (Unifamiliale / Copropriété / Plex): sales, active listings, new listings, **median price**, average price, volume, **average days on market**, market conditions by price band | **Sector** (approximates borough; p. 8 = Island of Montréal, pp. 9+ one page per sector) | **Quarterly** | **2019 Q2 to 2026 Q2 — 29 consecutive quarters, no gaps.** 2019 Q1 and earlier return **HTTP 404** | PDF, 65 pages, 5–9.5 MB (Power BI export) | `GET https://com.apciq.ca/sam/pdf/bar/{YYYY}/{YYYYQQ}-bar-mtl.pdf` returns **HTTP 200**. `HEAD` always returns 302 — GET with `-L` required | None | Quarterly | See 2.2 — **non-commercial use allowed with attribution; commercial use forbidden without written consent. Redistribution of the data as such: not granted** | **4**/5 | P1 | `fact_market` |

| 7 | Ministère des Affaires municipales et de l'Habitation (MAMH) | `roles-d-evaluation-fonciere-du-quebec` — the **statutory provincial assessment roll** | **Section 4 — assessed values**: `RL0401A` market reference date, `RL0402A` land value, `RL0403A` building value, `RL0404A` total property value, `RL0405A` value on the previous roll. **Section 3 — physical**: `RL0301A` frontage, `RL0302A` lot area, `RL0306A` storeys, `RL0307A` year built (`RL0307B` actual/estimated), `RL0308A` floor area, `RL0309A` physical link, `RL0310A` construction type, `RL0311A` dwelling count | Property (assessment unit), georeferenced in the GPKG/FGDB variants | Roll vintage — **5 vintages available: 2022, 2023, 2024, 2025, 2026** | 2022 to 2026 | XML per municipality; GeoPackage, FGDB, GeoJSON province-wide | `GET donneesouvertes.affmunqc.net/role/indexRole2026.csv` returns **HTTP 200** (1 134 municipalities; Montréal = code `66023`), then `GET .../RL66023_2026.xml` returns **HTTP 200/206**, `Content-Length` **794 991 963 B**. Province-wide GeoPackage 546 MB, full XML archive 236 MB. `Accept-Ranges: bytes` | None | Quarterly index published at `mamh.gouv.qc.ca/role/indexRole.csv` | CC-BY 4.0 — [donneesquebec.ca/licence](https://www.donneesquebec.ca/licence/#cc-by). **Redistribution allowed** | **3**/5 | **P2 — replaces row 4 for anything involving value. Extracted 2026-08-21, see 2.8** | `dim_property_configuration`, `fact_transactions` context |

| 8 | Données Montréal | `quartiers` — *Quartiers de référence en habitation* | `no_qr`, `nom_qr`, `no_arr`, `nom_arr`, `nom_mun`, MultiPolygon geometry | **Neighbourhood** — 91 features: 77 quarters of Ville de Montréal (with their borough) + 14 linked cities. **L'Île-Dorval is absent** | Current snapshot | Metadata modified 2026-08-19 | GeoJSON (1 135 769 B), SHP, CSV | CKAN `package_show` then `GET .../download/quartierreferencehabitation.geojson` returns **HTTP 200** (browser `User-Agent` required, see 2.5) | None | `[UNKNOWN]` | CC-BY 4.0 — [creativecommons.org/licenses/by/4.0](http://creativecommons.org/licenses/by/4.0/). **Redistribution allowed** | **1**/5 | P2 | `dim_geography` |
| 9 | Données Montréal | `quartiers-sociologiques` — *Quartiers sociologiques* | `id`, `Q_sociologique`, `Arrondissement`, `Abreviation`, `nbr_RUI`, `Table`, MultiPolygon geometry | **Sociological neighbourhood** — 32 features, Ville de Montréal only. Names **Côte-des-Neiges** and **Notre-Dame-de-Grâce** separately | 2014 delineation | Metadata modified 2025-02-27 | GeoJSON (292 280 B), SHP, CSV | `GET .../download/quartiers_sociologiques_2014.geojson` returns **HTTP 200** | None | `[UNKNOWN]` — 2014 vintage, no update since | CC-BY 4.0 — [creativecommons.org/licenses/by/4.0](http://creativecommons.org/licenses/by/4.0/). **Redistribution allowed** | **1**/5 | P2 | `dim_geography` |

| 10 | Statistics Canada | **2021 Geographic Attribute File** (92-151-X) — `2021_92-151_X.csv` | 63 columns. The ones that matter here: `CSDUID_SDRIDU` + `CSDNAME_SDRNOM` (municipality), `CTUID_SRIDU` + `CTDGUID_SRIDUGD` (census tract), `CMAUID_RMRIDU`, `DAUID_ADIDU`, `DBUID_IDIDU`, `DBPOP2021_IDPOP2021`, `DBTDWELL2021_IDTLOG2021`, `DBAREA2021_IDSUP2021` | **Dissemination block** — 498 786 rows Canada-wide, **13 844 on the Island**. Carries every coarser code on the same row | 2021 Census | 2021 | CSV in ZIP — 9 832 890 B zipped, 298 768 692 B unzipped | `POST /census-recensement/2021/geo/aip-pia/attribute-attribs/index2021-eng.cfm?Year=2021` with `year=21&lang=_e&getgeo=Continue` returns **302** to `.../files-fichiers/2021_92-151_X.zip`, which returns **HTTP 200** | None | Per census (5 years) | [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence) — not restated inside the file. **Redistribution allowed** | **2**/5 | **P1 — this is what unblocks J3.3, see 2.9** | `dim_geography` |
| 11 | Statistics Canada | **2021 cartographic boundary file — census tracts** (`lct_000b21a_e`) | `CTUID`, `DGUID`, `CTNAME`, `LANDAREA`, `PRUID`, MultiPolygon geometry | **Census tract** — 6 247 features Canada-wide, **541 on the Island** | 2021 Census | 2021 | SHP in ZIP (13 403 271 B) — `.shp` 28 369 348 B. **CRS: NAD83 Statistics Canada Lambert, metres**, read from the `.prj`, not from memory | `POST /census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?Year=21` with `year=21&lang=_e&type=b&bound=ct_&format=a&getgeo=Continue` returns **302** to `.../files-fichiers/lct_000b21a_e.zip`, which returns **HTTP 200** | None | Per census (5 years) | **[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)**, declared in the file's own metadata (`lct_000b21a_e.xml`) — "worldwide, royalty-free, perpetual, non-exclusive licence to use the Information, **including for commercial purposes**", attribution required. **Redistribution allowed** | **2**/5 | **P2 — not required to delimit the Island, see 2.9** | `dim_geography` |

Automation difficulty: 1 = stable documented API, 5 = recurring manual extraction.

Rows 10 and 11 were verified on 2026-08-24 while opening J3.3. Both sit behind an HTML
`POST` form, not a plain link: the file paths below were **returned by the server** in a
`Location` header, never guessed.

Rows 8 and 9 were verified on 2026-08-23 while building the geography model.
Neither is ingested yet. They matter because **each one resolves one of the two
places where APCIQ cuts a borough in half, and neither resolves both** — see
`docs/geography.md` section 5.

Données Montréal resource UUIDs are abbreviated in the table for width. Full URLs are
resolved at runtime through the CKAN API: `GET /api/3/action/package_show?id={dataset}`
(**HTTP 200**, no `User-Agent` needed) — which is the right way to fetch them anyway, since
the portal can reissue resource ids.

---
| 12 | Statistics Canada | Table `18100004` — Consumer Price Index, monthly, not seasonally adjusted | All-items index. Vector `41692876`, coordinate `13.2.0.0.0.0.0.0.0.0`, unit `2002=100`, `statusCode`, `symbolCode` | **Census metropolitan area 462** — wider than the Island (Laval, Longueuil, both shores). No finer geography exists for this series | **Monthly** | 1914-01 to **2026-07** (tested 2026-08-31, released 2026-08-17); loaded from 2014-01 = 151 points | JSON | `POST /t1/wds/rest/getCubeMetadata` then `GET /t1/wds/rest/getDataFromVectorByReferencePeriodRange` with `vectorIds`, `startRefPeriod` and `endReferencePeriod` — all **HTTP 200**. `endReferencePeriod` is mandatory: without it the API answers **406** | None | Monthly, about three weeks after the month ends | [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence) — "use, reproduce, publish, freely distribute, or sell". **Redistribution allowed** | **1**/5 | **P1 — restates the 2020 census income, see 2.10** | `fact_affordability` |

## 2. Source risks

### 2.1 APCIQ — verdict: obtainable, but not over the requested history

The original [brief](brief.md) (section 8.4) asks for 2015 to present. **That is not
available.** The quarterly *Baromètre* archive starts at **2019 Q2**. Every quarter from
2019 Q2 through 2026 Q2 was requested individually: 29 responses of HTTP 200, zero gaps.

What the substitution costs: **four and a half years of history (2015 Q1 to 2019 Q1)**, which
removes the pre-pandemic baseline. The remaining window still contains the rate hiking cycle
and its correction, which is the more interesting period for the rate/price analysis of
section 26.

**Decision, 2026-08-21: accepted.** The project's historical perimeter is **2019 Q2 onward**,
not 2015. Brief section 8.4 and section 32 are superseded on this point. Any chart or README
claim must state the 2019 Q2 start rather than implying a decade of history.

What the source delivers, and it is richer than the brief assumed — verified on
`202602-bar-mtl.pdf` (9 454 347 B, 65 pages):

- p. 7 Montréal CMA, **p. 8 Island of Montréal**, pp. 9+ **one page per sector**, and the
  sector names map onto boroughs (Le Sud-Ouest, Saint-Laurent, Ahuntsic-Cartierville,
  CDN/CSL, Ville-Marie, Le Plateau-Mont-Royal, Rosemont, Villeray,
  Mercier/Hochelaga-Maisonneuve, Anjou/Saint-Léonard, Montréal-Nord, and so on).
- Per sector **and** per category: sales, active listings, new listings, median price,
  average price, volume, average days on market — each for the quarter, the trailing
  12 months, and a 5-year variation.
- **Market conditions by price band** (inventory, sales, months of inventory,
  seller/balanced/buyer market). This feeds the "Market Regime" idea of section 29 directly,
  with no derivation needed.

Extraction is the real cost. `pdfplumber.extract_tables()` returns unusable fragments — the
file is a Power BI export in which labels and values are separate objects.
**Positional extraction works.** `extract_words()` on a sector page recovers clean horizontal
bands, one per metric, each holding the same sequence:

```
y=<top>  <metric label>  <quarter value>  <change>  <trailing value>  <change>  [<5-year change>]
```

No figure is transcribed here, or anywhere else in this repository's text: the repository
does not distribute the source's figures — [`apciq.md`](apciq.md) section 1.

> **Superseded on 2026-08-23 — see `docs/apciq.md`.** Two claims that stood in this section
> after the J1 survey turned out to be wrong once all 29 editions were read:
> band spacing is **not** constant (the page size triples in 2025 Q3, and Power BI moves the
> columns from one page to the next, so the parser calibrates on each page); and the `-fr`
> suffix is a plain **alias**, not a second naming scheme — one URL form is enough.

### 2.2 Licence — the one real constraint

APCIQ terms of use ([apciq.ca/conditions-dutilisation](https://apciq.ca/conditions-dutilisation/),
retrieved 2026-08-21), verbatim:

> « Toute reproduction ou utilisation des données ou des informations publiées sur le site à
> des fins **commerciales est interdite**, à moins d'avoir obtenu au préalable le consentement
> écrit de l'APCIQ. »
>
> « Toute reproduction ou utilisation des données ou des informations publiées sur le site
> doit se faire en donnant comme **référence l'APCIQ**. »

Reading: a non-commercial portfolio project that attributes "Source : APCIQ par le système
Centris" is within the terms. **Selling anything built on this data, or shipping it inside a
paid product, is not** — and no bulk redistribution of APCIQ figures should ship in the repo.
`robots.txt` on apciq.ca is `User-agent: * / Allow: /`.

**Consequence for the repo:** APCIQ-derived figures stay out of any published dataset.
Publish the parser, the schema and the aggregated analysis — not the extracted table.

#### Correction, 2026-08-23: the PDF itself is stricter than the website

Read on page 65 of every edition, verbatim:

> « Toute reproduction de l'information qui s'y retrouve, en tout ou en partie,
> directement ou indirectement, est strictement interdite sans l'autorisation préalable
> écrite du titulaire du droit d'auteur. »

That is not the same permission as the website's terms quoted above. The site allows
non-commercial use with attribution; the document forbids reproduction of its content,
in part and indirectly, without written consent.

**What this changes.** Nothing about ingesting, storing or analysing the figures in a
private database — that is use, not reproduction. It changes what may leave it.

**Settled on 2026-09-16** — the question raised here on 2026-08-23 of what a public
dashboard may show. The project shows the figures under the website terms, credited, in
screenshots and in a report published to the web, and never distributes them as data:
no APCIQ figure in a versioned text file, an exported dataset or a sample. The policy,
what *Publish to web* exposes, and the tension with page 65 stated plainly, are in
[`apciq.md`](apciq.md) section 1.

### 2.3 The `fact_market` dependency is single-sourced

APCIQ remains the only verified source of realised-market statistics. Principle 41.6 of the
brief protects the pipeline against losing Apify; it has **no equivalent for APCIQ**. Given
that the archive is quarterly PDFs whose URL pattern and layout can change without notice,
add one: *every downloaded PDF is archived locally on first fetch, so the historical series
survives the source changing shape.* 29 files at roughly 7 MB each is about 200 MB, kept
outside git.

### 2.4 Statistics Canada — the traps found, and the one that would have cost a day

**The expensive one, found 2026-08-24: `...` prints a zero.** Table `98100058`
never leaves a cell blank when it has nothing to publish — it prints a symbol
in the column beside it, and the two kinds of non-value do **not** look alike:

| Symbol | Meaning, verbatim from `98100058_MetaData.csv` | What the value column holds |
|---|---|---|
| `''` | value published | a real number — **never zero, on an income** |
| `'x'` | "suppressed to meet the confidentiality requirements of the Statistics Act" | **empty** |
| `'...'` | "not applicable" | **the literal `0`** |

Counted over the whole Montréal CMA, per 2020 income measure: 49 641 real
numbers, **18 404 zeros that mean nothing**, 9 340 empties.

A loader that treats "empty" as "missing" therefore keeps eighteen thousand
median household incomes of **nought dollars** per measure. They cast cleanly,
they average quietly, and no figure downstream looks wrong enough to
investigate.

And they cannot be swept up afterwards by discarding zeros, because **a zero is
real data on the household counts**: 19 385 of those are published as zero, a
tract genuinely holding no household of a given size and type. Only the symbol
separates the two cases. That is why the raw layer stores every symbol beside
its value and the conversion keys on the symbol, never on the value looking
empty. Same lesson as APCIQ's `-` / `**` / blank, with a nastier placeholder.

**The table is not one row per geography.** It crosses 7 household sizes with
11 household types, so every geography carries **exactly 77 rows** — 77 385 for
CMA 462, with no geography carrying any other count. Useful as a test: a
re-worded dimension label would insert rows rather than update them.

**Six columns are named `Symbol`.** Reading the file with a dictionary reader
keeps one of them and silently discards five, which erases exactly the
distinction above. It has to be read positionally.



- The full `98100058` CSV (68.7 MB uncompressed, 484 871 rows) contains **short rows**: a
  strict positional parser raises `IndexError` partway through. Parse defensively.
  **Measured 2026-08-24: there are exactly two of them, and they are rows of length
  zero — blank lines, not truncated records.** That distinction matters: a blank line
  is skipped, whereas a genuinely truncated row would mean fields shifting into the
  wrong columns and must abort the load. The parser treats the two differently.
- **CMA 462 is not the Island of Montréal.** It includes Laval, Longueuil, and the North and
  South Shores. Do not treat "Montréal CMA" as the project perimeter. ~~Restricting to the
  island requires joining CT geography to the boundary file of row 5.~~ **Corrected
  2026-08-24: that sentence was wrong, and it presupposed a CT geometry layer this project
  did not have.** Row 5 holds boroughs and linked cities, not census tracts, and no spatial
  join is needed in any case — the published attribute file of row 10 states the municipality
  of every tract outright. Of the 1 004 tracts in CMA 462, **541 are on the Island**. See 2.9.

### 2.5 Données Montréal — `403 RBAC: access denied`

Downloads from `donnees.montreal.ca` return **HTTP 403 with the body `RBAC: access denied`**
when the request carries curl's default `User-Agent`. The same URL returns **HTTP 200** with a
browser `User-Agent`. Every Python client for this source must set a `User-Agent` header. The
CKAN API itself (`/api/3/action/*`) answers fine without one.

### 2.7 The assessment-roll problem, and its resolution

**The problem.** The City of Montréal dataset `unites-evaluation-fonciere` (row 4) has exactly
18 columns, and **none of them is a value**. Verified against the CSV header:

```
ID_UEV, CIVIQUE_DEBUT, CIVIQUE_FIN, NOM_RUE, SUITE_DEBUT, MUNICIPALITE,
ETAGE_HORS_SOL, NOMBRE_LOGEMENT, ANNEE_CONSTRUCTION, CODE_UTILISATION,
LETTRE_DEBUT, LETTRE_FIN, LIBELLE_UTILISATION, CATEGORIE_UEF, MATRICULE83,
SUPERFICIE_TERRAIN, SUPERFICIE_BATIMENT, NO_ARROND_ILE_CUM
```

It is a *physical inventory* of the building stock, not an assessment. It answers "how old,
how big, how many dwellings, is it a condo" and cannot answer "what is it worth". The brief
(section 8.3) treats this source as the basis for a municipal-valuation comparison; on this
file, that comparison is impossible.

**The resolution.** The statutory roll is a provincial dataset, not a municipal one. The MAMH
publishes it on Données Québec as `roles-d-evaluation-fonciere-du-quebec` (row 7), and it
carries the values the city extract omits. Field meanings below are quoted from the MAMH's own
*Guide sur les données du rôle d'évaluation foncière en format ouvert* (26 pages, retrieved
2026-08-21), not inferred:

| Field | Official label | Example, Montréal 2026 |
|---|---|---|
| `RL0401A` | Date de référence du marché | `2024-07-01` |
| `RL0402A` | Valeur du terrain | `1 800 700` |
| `RL0403A` | Valeur du bâtiment | `180 100` |
| `RL0404A` | Valeur de l'immeuble | `1 980 800` |
| `RL0405A` | Valeur de l'immeuble au rôle antérieur | `1 899 400` |

The arithmetic checks out on the sampled record: `RL0402A + RL0403A = RL0404A`.

Three consequences worth stating plainly:

1. **The `RL0405A` field gives a free prior-period comparison.** Every unit carries its value
   on the previous roll, so a single vintage already contains a change measurement.
2. **Five vintages are published (2022 through 2026)**, which turns a static snapshot into a
   short time series of assessed values at the property level.
3. **Section 3 is richer than the city extract**, including `RL0311A` dwelling count and
   `RL0308A` floor area — so row 7 supersedes row 4 for essentially every analytical use.

**The cost.** Volume. Montréal alone is a **795 MB XML file**; the province-wide GeoPackage is
546 MB. Both servers support `Accept-Ranges: bytes`, so sampling is possible, but a full load
needs streaming (`iterparse`, not `parse`) and belongs on the VPS rather than the laptop. That
is what moves this source to automation difficulty 3 rather than 1.

**What does not change.** Brief section 8.3 remains correct and now matters more, not less: a
municipal assessment is **not** a sale price. It is an administrative estimate at a fixed
market reference date (`RL0401A` = 2024-07-01 for the 2026 roll), produced for taxation. Used
as a comparison base against APCIQ median prices it is informative; used as a proxy for
transaction value it is wrong.

### 2.8 Island extraction — done, measured

`ingestion/mamh_roll/extract_roll.py` streams the 2026 roll for the **16 municipalities of the
island** (Ville de Montréal plus the 15 villes liées, codes cross-checked against the city's
own boundary file) and writes one CSV. Run on 2026-08-21:

| Measure | Value |
|---|---|
| Assessment units read | **514 741** |
| Residential kept (use code 1000-1999) | **480 197** |
| Montréal alone | 437 192 units in 78.9 s (~5 500/s) |
| Whole island | ~88 s |
| Output CSV | 52.5 MB |
| **Peak process memory** | **28 MB** |

That last row is the point. The Montréal XML alone is 795 MB and the process never exceeded
28 MB, because each `<RLUEx>` is cleared as soon as its row is written and the tree root is
cleared with it. `ElementTree.parse()` on the same file would have needed several GB.

**Field coverage on the 480 197 residential rows**

| Field | Populated |
|---|---|
| `total_value` | 100.0 % |
| `lot_area_m2` | 100.0 % |
| `year_built` | 99.1 % |
| `dwelling_count` | 97.4 % |
| `floor_area_m2` | 96.7 % |
| `borough_code` | 85.0 % |

`borough_code` at 85 % is not a defect: 408 399 / 480 197 = 85.0 %, exactly the Ville de
Montréal share. The 15 villes liées are municipalities, not boroughs, so they legitimately
have no borough number. Geography must therefore key on municipality first, borough second.

**Plausibility check.** Median total value by municipality ranks Westmount (2 025 000 $),
Hampstead (1 844 100 $) and Mont-Royal (1 545 150 $) at the top, Montréal-Est (441 300 $) at
the bottom, with Ville de Montréal at 659 300 $. That matches the real geography of wealth on
the island, which is the cheapest available evidence that the field mapping is right.

Median change against the previous roll (`RL0405A`): **+10.0 %**, across all 480 197 units.

**Not committed.** The 52.5 MB output is derived data that regenerates in 88 seconds from a
CC-BY source, so it does not belong in git. The repo carries the script, `last_run.json`, and
a 3 057-row stratified sample (`sample_data/mamh_roll_2026_island_sample.csv`, 16
municipalities) instead.

---

### 2.9 Census tract geography — verdict: the spatial join is not needed at all

**The blocker, as stated when J3.3 was opened.** Section 2.4 says restricting census tracts
to the Island requires "joining CT geography to the boundary file of row 5". Row 5 is the
City's administrative boundary file — boroughs and linked cities, not census tracts. That
sentence presupposed a CT geometry layer this project did not have, and no source for one
was documented anywhere in this matrix. Two routes were probed on 2026-08-24, both starting
`[UNKNOWN]`.

**Route 2 — a published CT → municipality correspondence — exists, and it wins.**
The 2021 **Geographic Attribute File** (row 10) carries one row per dissemination block,
and every coarser geographic code sits on that same row: `CSDUID_SDRIDU` (municipality) and
`CTUID_SRIDU` (census tract) side by side, with population, dwellings and land area attached.

Three facts were **measured** from it, not assumed:

| Question | Answer | How it was established |
|---|---|---|
| Is census division **2466** the Island? | **Yes — exactly.** 16 census subdivisions, matching the 16 municipalities of `_ile_municipalites.json` one for one, none missing, none extra | Grouped all 13 844 blocks whose `CSDUID` starts `2466` |
| Does `CSDUID` join to the MAMH municipal code? | **Yes.** `CSDUID = '24' + mamh_code` holds for all 16, names matching | Same pass |
| Do any census tracts **straddle the Island boundary**? | **None. Zero of 541.** No tract on the Island touches a second municipality either | Built CT → set of CSDs from the block file |

**The straddle result was checked against a positive control**, because a clean zero is
exactly the kind of answer that hides a broken test. Run over all of Canada, the same code
finds **69 census tracts that do cross a CSD boundary** (1.1 % of 6 260), and 12 that cross a
census-division boundary. The test can see the phenomenon; it simply does not occur here.

**Consequence: `CSDUID LIKE '2466%'` delimits the Island.** No PostGIS, no spatial join, no
edges that fail to coincide, no water surface, and no arbitrary rule for tracts cut in half —
because there are none. The four PostGIS traps of `geography.md` section 6 are not paid at
all on this axis. Route 2 was preferable in principle when J3.3 was opened; it is now
preferable on evidence.

**Route 1 — a StatCan cartographic boundary file for census tracts — also exists** (row 11),
and all 541 Island tracts are present in it. It is kept as **P2**, because it is still needed
for two things route 2 cannot do: drawing a map in Power BI (brief section 30, page 2), and
the eventual CT ↔ APCIQ-sector join, which is a genuine spatial problem — **boroughs and
APCIQ sectors are not StatCan geographies, so no attribute file will ever carry them.**
Its CRS is NAD83 Statistics Canada Lambert in metres, not WGS84: joining it to
`raw.mtl_administrative_boundary` (EPSG 4326) requires an explicit `ST_Transform`.

**The join to the income table closes on all three files.** Of the 541 Island tracts, **541
appear in the boundary file and 541 appear in table `98100058`** — no orphan in either
direction. The key is the DGUID: `CTDGUID_SRIDUGD` in the attribute file is character-for-
character the `dguid` of the income table (`2021S0507` + `CTUID`).

**Eleven of the 541 tracts carry no median income for 2020**, and they are the near-empty
ones — populations of 0, 10, 15, 21, 30. Ten are in Ville de Montréal, one is L'Île-Dorval.
This is suppression at source, not a parsing defect. Per principle 1 of brief section 41,
**they stay empty**: no interpolation, no borrowing from a neighbouring tract. Any indicator
built on them must show 530 tracts with income and 11 without, rather than 541 with a
silent gap.

**A side corroboration worth recording.** The Island's census-tract land area sums to
**498.29 km²**, against **619 km²** for the same island measured on the City's administrative
boundary file. That is the "administrative boundaries include water" finding of
`geography.md` section 6, arrived at from a completely independent source — the two files
disagree by the river, exactly as they should.

**What remains open after this verdict**, and it is a different problem from the one that was
blocking: attaching income to an APCIQ sector still requires geometry, because a census tract
nests inside a *municipality* but nothing published says which *borough* or *APCIQ sector* it
falls in. That is a J3.4 question, and it now rests on building the sector polygons
(`geography.md` section 5), which was already unblocked on 2026-08-23.

---

### 2.10 The Consumer Price Index — an index, never a replacement for income

**The question asked on 2026-08-31 was whether a household income newer than
the 2020 census exists at the census tract. It does not, and that is a
measured verdict rather than a failure to look.** `getAllCubesListLite`
returned the whole catalogue — **HTTP 200, 5 044 399 bytes, 8 267 cubes** — and
the 27 whose title carries "census tract" all end in 2021. The tax-filer series
`11100017` reaches income year 2023 and stops at CMA 462; `11100190` reaches
2024 and stops there too. **CMA 462 is not the Island**, a fact this project
established in J3.3 and did not have to rediscover.

So the choice was never "which newer income", it was **"index, or keep dividing
2026 by 2020"**. The CPI was chosen over restating the CMA income series for
one decisive reason: **it is the only candidate that reaches the last published
quarter.** The income series stops at 2024; the CPI reaches 2026-07.

**The two candidates were both built before choosing.** Restating the CMA
income in nominal terms and using the CPI alone agree to within **1.3 % over
2021-2024** and diverge by **7.8 % on 2019** — the isolated peak of 2020
pandemic transfers. The income series therefore survives as a **control that
bounds the error**, measured once and recorded in `affordability.md`, rather
than as a second ingested dependency.

**One result worth stating plainly, because it is counter-intuitive**: in real
terms the median income of CMA 462 has **not risen since 2020** — 82 100 $ in
2020, the peak of the series, against 81 100 $ in 2024, both in 2024 constant
dollars (`memberUomCode 455`). What grew was the number of dollars. The entire
error in the affordability ratio was therefore nominal, which is exactly why it
was large.

**The RMR-to-Island assumption was tested rather than asserted.** The census
publishes tract income for both 2015 and 2020, so the assumption is falsifiable.
Real growth 2015 → 2020, measured three ways: census CMA aggregate **×1.1343**,
census Island (529 tracts grouped) **×1.1437**, income survey CMA **×1.1466**.
Two surveys, two units of account, three figures within 1.1 % of each other.
The probe could have failed; it passed.

**Access notes worth keeping.** A coordinate is a position in a cube, not a
name: the neighbouring geography member is the **province** of Quebec, which
would load without error and quietly restate every Montréal income by the wrong
factor. The loader therefore checks the coordinate against the published
`classificationCode` and the resolved `vectorId` before reading a single point
— four positive controls in `tests/test_statcan_cpi.py`, all firing.

## 3. Rejected sources

| Source | Why |
|---|---|
| CMHC / SCHL direct portal | `https://www03.cmhc-schl.gc.ca/hmip-pimh/en/TableMapChart/Table` returned **HTTP 500** on 2026-08-21. Statistics Canada republishes 55 CMHC cubes under the open licence, reachable through the WDS API already built for row 2 — so the direct portal is not needed as a *mechanism*. But see 2.6: the housing-starts cube tested does not cover Montréal, so the substitution is not yet proven for the data itself. |
| Apify / active listings | Phase 2 by design (brief section 33). Not verified in this pass. |
| JLR / individual transactions | Phase 3, explicitly not a MVP dependency (brief section 34). Not verified. |
| APCIQ press releases (`/categorie/statistiques-mensuelles/`) | Narrative HTML, CMA level only. The *Baromètre* PDF supersedes it on every axis. |

---

## 4. Samples on disk

| File | Rows | Provenance |
|---|---|---|
| `sample_data/boc_rates_2015_present.csv` | 2 981 | Valet CSV endpoint, 4 series, from 2015-01-01 |
| `sample_data/statcan_98100058_montreal_ct_income.csv` | 1 006 (1 004 CTs + CMA + header) | Filtered from the 484 871-row full table |
| `sample_data/mtl_role_foncier_extrait.csv` | 10 183 | First 1.5 MB of the 76 MB roll, via HTTP Range |
| `sample_data/mtl_limites_administratives.geojson` | 34 features | Full file, 1 258 670 B |
| `sample_data/statcan_gaf_2021_island_ct.csv` | 541 (one per Island census tract) | Aggregated from the 13 844 Island dissemination blocks of the Geographic Attribute File (row 10). Carries the CT → municipality correspondence, the MAMH code, population, dwellings, land area, and whether the tract has a 2020 income. **This file is the evidence behind 2.9** — it lets a reader re-check the verdict without downloading 298 MB |

| `sample_data/statcan_18100004_montreal_cpi.csv` | 151 (one per month, 2014-01 to 2026-07) | The whole loaded series, with the quarterly factor beside each month. **This file is the evidence behind 2.10**: the last row shows 2026 Q3 with one month of three, an empty factor and `not_indexed` — which is what the guard against a partial quarter looks like from outside |
APCIQ PDFs are deliberately **not** committed — see 2.2.
