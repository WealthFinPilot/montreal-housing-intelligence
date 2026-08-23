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

Automation difficulty: 1 = stable documented API, 5 = recurring manual extraction.

Rows 8 and 9 were verified on 2026-08-23 while building the geography model.
Neither is ingested yet. They matter because **each one resolves one of the two
places where APCIQ cuts a borough in half, and neither resolves both** — see
`docs/geography.md` section 5.

Données Montréal resource UUIDs are abbreviated in the table for width. Full URLs are
resolved at runtime through the CKAN API: `GET /api/3/action/package_show?id={dataset}`
(**HTTP 200**, no `User-Agent` needed) — which is the right way to fetch them anyway, since
the portal can reissue resource ids.

---

## 2. Source risks

### 2.1 APCIQ — verdict: obtainable, but not over the requested history

The original brief (section 8.4) asks for 2015 to present. **That is not
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
**Positional extraction works.** `extract_words()` on the Plateau page recovers clean
horizontal bands:

```
y= 521.5  médian **  -  <chiffre retire -- licence APCIQ>  -> Unifamiliale
y= 956.5  médian <chiffre retire -- licence APCIQ>  -> Copropriété
y=1391.5  médian <chiffre retire -- licence APCIQ>  -> Plex
```

Band spacing is a constant 435 pt: the template is stable. Budget the parser accordingly, and
assert on the band count per page rather than trusting absolute positions.

Naming is *not* perfectly regular: `202504-bar-mtl-fr.pdf` carries an `-fr` suffix that the
other 28 files do not. The fetcher must try both forms.

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

### 2.3 The `fact_market` dependency is single-sourced

APCIQ remains the only verified source of realised-market statistics. Principle 41.6 of the
brief protects the pipeline against losing Apify; it has **no equivalent for APCIQ**. Given
that the archive is quarterly PDFs whose URL pattern and layout can change without notice,
add one: *every downloaded PDF is archived locally on first fetch, so the historical series
survives the source changing shape.* 29 files at roughly 7 MB each is about 200 MB, kept
outside git.

### 2.4 Statistics Canada — two traps found

- The full `98100058` CSV (68.7 MB uncompressed, 484 871 rows) contains **short rows**: a
  strict positional parser raises `IndexError` partway through. Parse defensively.
- **CMA 462 is not the Island of Montréal.** It includes Laval, Longueuil, and the North and
  South Shores. Restricting to the island requires joining CT geography to the boundary file
  of row 5. Do not treat "Montréal CMA" as the project perimeter.

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

APCIQ PDFs are deliberately **not** committed — see 2.2.
