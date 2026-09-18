# Power BI

How the report connects, what its semantic model looks like, and what may and
may not leave this folder.

The page design and every DAX measure live in [report-design.md](report-design.md).

---

## 1. Before opening Power BI Desktop

The database is unreachable until the tunnel is open. From the repository root,
**in Git Bash**:

```bash
bash scripts/tunnel-start.sh
```

It prints `OK: PostgreSQL answered at 127.0.0.1:15432` when the far end is
really a PostgreSQL server, not just an open port.

## 2. Two preview features to enable, once

**File > Options and settings > Options > Preview features**, tick both:

* `Power BI Project (.pbip) save option`
* `Store semantic model using TMDL format`

Restart Desktop afterwards.

Together they are what makes this report committable at all. A `.pbix` carries
its data inside the file, compressed, and nothing can look in. A `.pbip` splits
the work into a **definition** — tables, relationships, measures, pages,
visuals, all plain text — and a **data cache**, `.pbi/cache.abf`, which
`.gitignore` excludes. The repository can therefore carry the entire report
without reproducing a single APCIQ figure.

Both features were preview on 2026-08-27 (learn.microsoft.com, page dated
2026-08-18). Preview here means the file format may still change, not that it
is unreliable; the risk it carries is a future Desktop version reading these
files differently, which is a re-save, not a loss.

## 3. Connection settings

| Field | Value |
|---|---|
| Connector | PostgreSQL database |
| Server | `localhost:15432` |
| Database | value of `POSTGRES_DB` in `.env` |
| Data Connectivity mode | **Import** |
| Authentication kind | **Database** (not Windows) |
| User name | value of `POSTGRES_USER` in `.env` |
| Password | value of `POSTGRES_PASSWORD` in `.env` |
| Encrypt connection | **unchecked** |

### The three settings that are not obvious

**Encrypt connection must be unchecked.** Power BI ticks it by default and the
container does not offer TLS, so the connection fails with a message about the
server not supporting SSL. That is not a weakness here: the traffic already
travels inside the SSH tunnel, which is encrypted end to end. Ticking the box
would ask for a second, redundant layer the server was deliberately not
configured to provide.

**Import, not DirectQuery.** Decided on 2026-08-21 and verified in Microsoft
documentation: *Publish to web* is incompatible with DirectQuery, so Import is
mandatory for a publicly shared report anyway. Import also means no gateway, no
Pro licence, and no database exposed to the internet. The data is quarterly at
the analytical grain; freshness is not the constraint here.

**Port 15432, not 5432.** 15432 is the local end of the SSH tunnel. The database
itself listens on 5432 on the server loopback and is unreachable from here.

---

## 4. What to import

Ten tables, all from the `marts` schema. Nothing from `raw` or `staging`:
those layers exist to be transformed, and a report that reaches into them
documents the exception instead of the rule.

### Facts

| Table | Rows | Grain |
|---|---|---|
| `fact_market` | 1 653 | quarter x area x property type |
| `fact_market_trailing_12m` | 1 653 | 12-month window x area x property type |
| `fact_mortgage_scenario` | 1 653 | quarter x area x property type |
| `fact_affordability` | 141 462 | quarter x census tract x property type x household profile |
| `fact_interest_rate` | 4 229 | series x observation date |

### Dimensions

⚠️ **The dimension tables are renamed on import: the `dim_` prefix is dropped.**
The left column is what to select in the connection dialogue, the right column
is what the table is called in the model and therefore in every DAX formula in
`report-design.md`.

| Table in the database | Name in the model | Rows | Note |
|---|---|---|---|
| `marts.dim_date` | `'date'` | 4 383 | one day, 2015-01-01 to end of the current year |
| `marts.dim_property_type` | `property_type` | 3 | |
| `marts.dim_household_profile` | `household_profile` | 3 | |
| `marts.dim_interest_rate_series` | `interest_rate_series` | 3 | |
| `marts.dim_geography` | `Sector` **and** `Census_Tract` | 595 | **split into two queries, see below** |

**The fact tables keep their names.** `fact_market`, `fact_affordability` and
the rest are imported and referenced exactly as the database calls them, so a
name without a prefix is a dimension and a name with `fact_` is a fact — which
is the whole point of dropping the other prefix.

⚠️ **`date` must be written `'date'` in DAX, with single quotes.** `DATE` is a
DAX function, so a bare `ALL ( date )` or `date[quarter_label]` puts a table
name where the parser expects a function call. Single quotes around a table
name are always valid in DAX, whether or not they are required, so every
reference in `report-design.md` carries them. This is the one cost of dropping
the prefix, and it is a small one.

⚠️ **`Census_Tract` carries an underscore, not a space.** It is a Power Query
name, and a DAX formula written `'Census Tract'` will not resolve.

`bridge_census_tract_apciq_sector` is deliberately **not** imported.
`fact_affordability` already carries every column a visual needs from it —
`assignment_method`, `tract_is_shared`, `population_weight` — so importing the
bridge would add a table and no answer.

### `marts.dim_geography` must become two tables

`dim_geography` holds five geography types in one table. Loaded as one
dimension it cannot work: the market facts are keyed on an APCIQ sector, the
affordability fact on a census tract, and one dimension covering both would
filter one fact while leaving the other untouched — silently.

Duplicate the query in Power Query and filter each copy:

| Query name | Filter on `geography_type` | Rows |
|---|---|---|
| `Sector` | `apciq_sector` or `island` | 19 |
| `Census_Tract` | `census_tract` | 541 |

`Sector` keeps the island row on purpose. The island is a real published area,
not a total to be recomputed, and hiding it would mean losing the only figure
APCIQ prints for the whole market. Section 6 says how the measures keep it from
being added to its own parts.

⚠️ **`Census_Tract` carries `admin_place_name` since 2026-09-02** — the borough
or linked city a reader would call the tract's neighbourhood. It is NULL on
every `Sector` row, which is correct: a sector already is a place, and the
column is there for the 541 tracts whose own name (`CT 0250.00`) means nothing
to a reader.

**Do not replace it with a measure.** It is a column of the table the page 2
map groups by, so it sits in the shape's own row context and needs no
relationship to propagate. The measure it replaced read `Sector[name]` through
`fact_affordability` and printed the same borough on all 541 shapes — a
many-to-one relationship does not carry a filter back up, and nothing failed.

### Two columns to remove in Power Query

**`geometry`** — a PostGIS type. Power BI cannot read it as geography, and 541
polygons arrive as megabytes of binary that no visual can use. Remove it in
both geography queries.

**`source_pdf`** on the two market facts — the file name of an APCIQ edition.
It answers nothing in a report and it names a document the licence covers.

---

## 5. Relationships

Thirteen, all one-to-many, all single direction. No bidirectional filter
anywhere: the model has two geography dimensions that deliberately do not reach
the same facts, and a bidirectional relationship is precisely what would make
one of them appear to.

| From (one) | To (many) | On |
|---|---|---|
| `'date'[date_key]` | `fact_market` | `quarter_start_date` |
| `'date'[date_key]` | `fact_market_trailing_12m` | `edition_quarter_start_date` |
| `'date'[date_key]` | `fact_mortgage_scenario` | `quarter_start_date` |
| `'date'[date_key]` | `fact_affordability` | `quarter_start_date` |
| `'date'[date_key]` | `fact_interest_rate` | `observation_date` |
| `Sector[geography_key]` | `fact_market` | `geography_key` |
| `Sector[geography_key]` | `fact_market_trailing_12m` | `geography_key` |
| `Sector[geography_key]` | `fact_mortgage_scenario` | `geography_key` |
| `Sector[geography_key]` | `fact_affordability` | `apciq_geography_key` |
| `Census_Tract[geography_key]` | `fact_affordability` | `census_tract_geography_key` |
| `property_type[property_type_code]` | the four market and affordability facts | `property_type_code` |
| `household_profile[household_profile_code]` | `fact_affordability` | `household_profile_code` |
| `interest_rate_series[series_id]` | `fact_interest_rate` | `series_id` |

### A missing relationship raises nothing — it answers

One of these thirteen was absent when page 2 was built on 2026-08-29:
`property_type` reached `fact_market`, so page 1 worked, but it did not
reach `fact_affordability`. Power BI reported no error. The slicer moved, the
visuals redrew, and every figure on the page was the average of condominium,
plex and single-family together: the mean required income came out roughly half
as high again as the true condominium figure (both amounts derive from APCIQ
medians and are therefore not written here -- `scripts/report_oracle.py` prints
them), and the share read 33.8 % where it was 35.0 %.

**One of the five checked figures was right anyway**, which is what makes this
worth writing down: `Tracts affordable` read 179 either way, because the two
tracts affordable as single-family and the zero as plex are already inside the
condominium 179. A control that happens to agree is not a control that passed.

Two things follow. **Check the relationships against the table above by hand
after importing** — auto-detection created some and not others, with no pattern
worth learning. And **check a group of measures against the database before
drawing a page, not after**: three wrong figures out of five were unmistakable,
whereas the same fault noticed on a finished page looks like a broken visual and
gets debugged in the wrong place.

### The one that needs explaining

`fact_market_trailing_12m` joins `date` on **`edition_quarter_start_date`**,
not on `period_start_date`.

A 12-month window ends at its edition quarter and starts nine months earlier.
Joined on its start date, filtering "2026 Q2" would return nothing, because
that window starts in 2025 Q3. Joined on its edition quarter, filtering
"2026 Q2" returns the twelve months **ending** at 2026 Q2, which is what a
reader means.

The consequence has to stay visible: with 2026 Q2 selected, a quarterly figure
and a 12-month figure on the same page describe different spans of time.

**Page 4 shows both, and it is the only page that does.** Its combo chart reads
`Sales (island, 12 months)` from this table against a quarterly contracted rate,
so the two spans sit side by side in one visual. The guard is the `Trailing
window` measure — a card printing `MIN ( period_start_date )` to
`MAX ( period_end_date )` — written on 2026-08-30 with that page, after an
earlier version of this paragraph had pointed at it for months while it did not
exist. Without it, "2026 Q2" means three months on one axis and twelve on the
other, and nothing on screen says so.

Why the trailing table is on page 4 at all: **island sales by calendar quarter
are strongly seasonal** — indexed to each year's mean over 2020-2025, Q1 100 ·
Q2 117 · Q3 91 · Q4 92, with the strongest quarter beating the weakest by 1.36
to 1.92 within a single year. A twelve-month window contains all four seasons by
construction and that ratio falls to 1.05–1.28. Put the quarterly series against
a rate line and a reader reads the calendar as a response to the rate.

### The relationship that is real in the database and absent here

`docs/erd/` draws a **1—1** between `fact_mortgage_scenario[mortgage_scenario_key]`
and `fact_market[market_key]`. It is not a drawing convention: measured on
2026-08-27, all 1 653 scenario rows match a market row, and the two keys hold
**literally the same values**. dbt tests it with a `relationships` test.

It is deliberately **not** recreated in Power BI, for two reasons.

**The dimensions already carry it.** Both facts are at the same grain and are
joined to the same three dimensions. A visual with `Sector[name]` on the axis
showing `Median price` beside a payment measure works because each measure is
filtered by the shared dimension — which is what a star schema is for. Two
facts of equal grain are compared through their common dimensions, never
through a join between them.

**In Power BI it would close a loop.** A one-to-one relationship always filters
in both directions — Microsoft states it as a property of the cardinality, not
a setting. Combined with three dimensions both facts already share, that closes
three cycles, and Power BI cannot keep an unambiguous filter path through a
loop. Expect it to refuse the relationship or degrade it; either way the model
is worse than without it.

So the relationship does its work one layer down. It is what makes the three
`derived_*` edges in the ERD legitimate: `generate_erd.py` names this exact test
as the upstream guarantee that the scenario table's dimension keys agree with
the market table's. The database asserts integrity; Power BI propagates
filters. Those are two jobs, and only the first one needs this edge.

### Mark date as a date table

**Table tools > Mark as date table**, date column `date_key`. Without it, time
intelligence silently uses Power BI's own auto date hierarchies, which would
give the model a second, invisible calendar. `date` is contiguous by
construction and a dbt test asserts it, which is the condition Power BI
requires.

Also turn **auto date/time off**: *Options > Current file > Data load >
Time intelligence*. One model, one calendar.

---

## 6. Model hygiene, before building a single visual

**Hide every numeric column of every fact table**, and expose measures instead.
This is not tidiness. A user who drags `median_price` onto a visual gets an
implicit `SUM`, and the sum of eighteen medians is a number with no meaning
that looks exactly like an answer. Hiding the column makes the wrong gesture
unavailable rather than merely wrong.

Set **Summarize by = None** on any numeric column that stays visible.

**Do not build a measure that averages `median_price` across areas.** There is
no weighted median of the sectors and no sector median of the tracts —
`docs/market.md` section 7 states it, and the measures in
[report-design.md](report-design.md) enforce it by returning blank rather than
a plausible wrong number.

---

## 7. Saving as a project

**File > Save as > Power BI project file (.pbip)**, into `powerbi/`.

Keep the name short. Windows caps a path at 260 characters and a PBIP is a deep
folder tree; `powerbi/` plus a short name leaves room.

The result:

```
powerbi/
├── mhi.Report/            <- pages, visuals, formatting     COMMITTED
├── mhi.SemanticModel/
│   ├── definition/        <- tables, relationships, DAX     COMMITTED
│   └── .pbi/cache.abf     <- every imported row             IGNORED
└── mhi.pbip                                                 COMMITTED
```

Power BI Desktop writes its own `.gitignore` **only when neither the folder nor
the parent repository already has one**. This repository does, so Desktop will
write nothing, and the rules in the root `.gitignore` are the only thing
between the cache and a commit. They are already there.

### Before every commit

**In Git Bash**, from the repository root:

```bash
.venv/Scripts/python.exe scripts/check_powerbi_project.py
bash scripts/check-secrets.sh
```

The first compares the numbers in the generated files against the figures
actually in the database — not against numbers that merely look like prices —
and reports what it could not inspect instead of passing over it. It ends with
a positive control: it plants a real figure in a file of its own and confirms
it finds it, in three written forms including the non-breaking space. If it
cannot, it declares its own clean verdict worthless.

---

## 8. Governance

**The report is shown; its data is not distributed.** Decided on 2026-09-16:
screenshots of the four pages appear in the README, and the report is published
with *Publish to web*, as a non-commercial portfolio project. The credit
« Source : APCIQ par le système Centris » sits on the page that shows the
report — the README section for the screenshots, the hosting page for the
embedded report — and **not on the report canvas**, so a bare *Publish to web*
link carries no credit and is generated last, after the hosting page is live.
The full policy — including what *Publish to web* exposes, and the tension with
the stricter clause on page 65 of every edition — is in
[`../docs/apciq.md`](../docs/apciq.md) section 1.

What follows from it, and is not negotiable:

* **The `.pbix` of this report is never committed.** `.gitignore` blocks every
  `.pbix` by default, with one named exception: `mhi_interest_rates.pbix`, the
  J2 report, which holds Bank of Canada rates and nothing else. Publishing the
  report is not the same as shipping its data file.
* **`cache.abf` is never committed.** It is the data.
* **No APCIQ figure in a committed text file** — a report definition, a DAX
  comment, a design note. `check_powerbi_project.py` and section 6 of
  `check-secrets.sh` enforce it.
* **Statistics Canada figures are a different matter.** Their licence expressly
  allows redistribution, including sale.

### About the J2 .pbix still in this folder

`mhi_interest_rates.pbix` is committed as a **traced, accepted residual risk**,
not as a verified absence. A secret scanner cannot look inside a `.pbix`:
verified on 2026-08-22 by extracting the archive and searching for a string it
certainly contains, which found nothing, because the model is stored
compressed. `check_powerbi_project.py` reports it as uninspectable every run
rather than passing over it.

---

## 9. Refreshing later

Import mode means the data in the report is a copy taken at load time. To
refresh: open the tunnel, open the project, Refresh. There is no scheduled
refresh and no gateway, by design.

Opening the project on a machine with no `cache.abf` works: Power BI Desktop
opens the report and the full model definition **without data**, and a Refresh
against a reachable database fills it. That is what a reader who clones this
repository gets, and it is the intended experience.
