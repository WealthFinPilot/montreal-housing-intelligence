# Montreal Housing Intelligence

Analytics platform on the residential real-estate market of the **Island of
Montreal**: heterogeneous public sources brought into one PostgreSQL/PostGIS
model, transformed and tested with dbt, consumed in Power BI.

The question it exists to answer is not "what does a condo cost in Montreal"
but **"where can a first-time buyer still buy, on what income, and how has that
changed?"**

> **Status: milestone J2 in progress.** One source (Bank of Canada) is being
> taken end to end -- ingestion, staging, one Power BI visual -- to cross the
> whole stack once before widening. Not yet reproducible end to end; this README
> is completed as J2 closes.

## Historical perimeter

**2019 Q2 onward**, not 2015. The APCIQ quarterly archive does not go back
further (29 consecutive quarters verified on 2026-08-21). This is a documented
limitation, not an omission -- see `docs/data-sources.md` section 2.1.

## Sources

Seven datasets, each verified against a real HTTP request with its status code
and test date. See **[`docs/data-sources.md`](docs/data-sources.md)** for the
full matrix: variables actually observed, geographic and temporal grain,
licence quoted with its URL, and automation difficulty.

## Stack

Python · PostgreSQL + PostGIS · dbt Core · n8n · Docker · Power BI

## Analytical ground rules

These are enforced in the code and the models, not just stated:

- `asking_price` != `sale_price` != municipal assessment.
- A withdrawn listing is **not** a sale.
- Observed data, derived data and assumption are always distinguished.
- "Association", never "cause".
- Sources have different grains. That is exposed, never hidden behind an
  implicit join.
- A missing value is never invented or silently interpolated.

## Repository layout

```
docs/           Data Source Matrix, original brief, methodology
ingestion/      One module per source
dbt/            staging -> intermediate -> marts
sample_data/    Small real extracts, so the matrix can be checked without downloading
powerbi/        Report files
```

## Licence and attribution

Code under this repository is the author's. **The data is not**: each source
keeps its own licence, quoted with its URL in `docs/data-sources.md`. APCIQ
figures in particular are usable for non-commercial purposes with attribution
and are **not** redistributed here.
