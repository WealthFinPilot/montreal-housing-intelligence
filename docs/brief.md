# Project brief — scope and principles

The code, the models and the documents of this repository cite "the brief" by
section number: *section 41.1 of the brief*, *principle 2*, *brief §44*. This
is that brief.

It was written in French before the first line of code, as the specification
the project is built against. What follows is **an English translation,
condensed, of the sections the repository cites — under their original
numbers**, which is why the numbering has gaps. Where the project later
diverged from the brief, the divergence is noted in a box and linked to the
document that measured it. The brief itself is never rewritten to match what
was built: the gap between the two is part of the record.

---

## 1. Summary

An analytical platform on the **residential market of the Island of
Montréal**: a system of pipelines that keeps running over time, and a decision
aid for a first home purchase. Not a dashboard of average prices by
neighbourhood — a housing-market intelligence system able to answer questions
such as:

- How have prices moved across the neighbourhoods of Montréal?
- Which areas remain the most affordable relative to incomes?
- How has affordability changed over several years?
- What relationship is there between interest rates and prices, sales volumes,
  days on market and inventory?
- How much must a household earn today to buy a typical condo in different
  neighbourhoods?
- For a given monthly budget, which areas become accessible?
- How many square feet does the same budget buy from one neighbourhood to the
  next?
- How does the historical market of sales differ from the current market of
  listed properties?
- Are homes only getting dearer, or also getting smaller?

---

## 3. Geographic scope

**The Island of Montréal**, analysed at several levels when the data allows:

```text
Island of Montréal → municipality → borough → neighbourhood / sector
                   → census tract → dissemination area
```

Not every source has the same granularity. That difference is a real
analytical problem to solve, **not something to hide**.

## 4. Property types

Condo, single-family, plex. The condo is expected to carry the most detailed
analysis.

## 5. Condo granularity

When listing data is available, condos are segmented by objective variables —
`bedrooms`, `bathrooms`, `rooms`, `living_area_sqft`, `asking_price`,
`condo_fees`, `year_built`, `parking` — and by configuration: studio,
1 bedroom, 2 bedrooms, 3 bedrooms, 4+ bedrooms.

The Québec room-count classification (2½, 3½, 4½…) is **not** an analytical
variable. An approximate equivalence may be derived for display, documented as
a derived classification, never as official data.

## 6. Living area and price per square foot

`price_per_sqft = asking_price / living_area_sqft`, and for transactions
`sale_price / living_area_sqft`. The project must be able to tell apart a rise
in total price, a change in living area, and a real rise in price per unit of
area. Size bands are set after exploring the distribution, not before.

## 7. The four realities of the market

| Reality | Question | Typical data |
|---|---|---|
| Realised market | What actually happened? | sales, median prices, days on market, inventory |
| Listed market | What is offered to buyers today? | asking price, area, rooms, condo fees |
| Socio-economic context | Which households can carry these prices? | median income, population, households |
| Macroeconomic conditions | Under which financial conditions? | policy rate, mortgage rates, inflation |

An `asking_price` is never a `sale_price`.

---

## 8. Sources

**8.1 Bank of Canada** — policy rate, interest rates, mortgage series, through
the Valet API. Highly automatable.

**8.2 Statistics Canada** — median income, population, households, at the
census metropolitan area, census tract or dissemination area. **Census data is
not updated as often as the housing market; that gap must be handled
explicitly.**

**8.3 Montréal open data** — geography, boundaries, property assessment units.
**A municipal assessment must never be treated as a sale price.**

**8.4 APCIQ** — the history of the market: median prices, sales, listings,
days on market, by property category, quarterly. Initial historical target:
**2015 to present**.

> **Diverged.** The APCIQ quarterly archive starts in 2019 Q2; the project's
> history starts there. [`data-sources.md`](data-sources.md) section 2.1.

**8.5 CMHC** — optional, later: housing starts, rental market, supply.

---

## 18. Technologies excluded at the start

Kafka, Spark, Kubernetes, Airflow, Snowflake, MongoDB, Elasticsearch, MLflow —
not without a written justification. The volume and frequency of housing data
do not call for them. The project demonstrates sound architectural decisions,
not an accumulation of technology names.

## 22. Different granularities

| Source | Geography | Time |
|---|---|---|
| Bank of Canada | Canada | daily |
| APCIQ | sector / borough | quarterly |
| Statistics Canada | census tract | census year |
| Listings | property | daily / weekly |
| Montréal open data | property | current |

The project must not pretend that these sources share the same precision.

## 25. First-Time Buyer Affordability Score

A composite indicator may be built from mortgage burden, price-to-income,
required down payment, price per square foot and market liquidity. It must be
presented as **an analytical indicator built by this project, never as an
official standard**, with its formula documented and justified.

> **Not built in the MVP.** [`../powerbi/report-design.md`](../powerbi/report-design.md)
> records why.

## 26. Analytical questions

- **Market** — which areas appreciated most; where sales volumes changed most;
  where days on market lengthened; where inventory is highest.
- **Condo** — price per square foot by neighbourhood; where two-bedroom condos
  are most affordable; what area a given budget buys; whether listed homes are
  getting smaller.
- **Affordability** — how the price-to-income ratio evolved; which
  neighbourhoods remain accessible to a first-time buyer; what income a median
  property requires; whether lower rates offset higher prices.
- **Macroeconomics** — the relationship between rates and sales; whether rate
  changes lead market changes; which lags appear; whether relationships differ
  by property type.

## 27. Correlation and causation

`correlation != causation`. Correlation, lagged correlation, rolling
correlation, regression, time series and period comparisons are all in scope,
but conclusions speak of **association** or **relationship**, never of cause,
without a method designed to establish one.

## 28. Statistical analyses

Once the pipeline works: year-over-year and quarter-over-quarter growth,
rolling averages and correlations, lag analysis, distribution and outlier
analysis, regression. Possibly clustering and forecasting later. Machine
learning is **not** a priority of the MVP.

## 30. Power BI dashboard

Five pages were planned: **Market overview**, **Neighbourhood explorer** (a map
of Montréal), **Condo explorer**, **First-time buyer** (income, down payment and
budget as user parameters, with a verdict per area), and **Macro** (rates,
prices, sales, inventory, days on market).

> **Diverged.** Four pages were built. The condo explorer needs listing data,
> which is phase 2. [`architecture.md`](architecture.md) section 9.

## 31. The decision question, as an example

A user supplies an income, a down payment, a number of bedrooms, a minimum
area and a maximum monthly housing cost — the brief's example uses an income
of $95,000 and a down payment of $50,000 — and the model answers, area by area:
**accessible**, **borderline** or **difficult**. The aim is an exploratory
analytical tool, not certified financial advice.

---

## 32. The MVP

The MVP must work **without listing data**.

| | |
|---|---|
| Geography | Island of Montréal |
| History | 2015 to present — *diverged: 2019 Q2, see section 8.4* |
| Properties | condo, single-family, plex |
| Sources | APCIQ, Statistics Canada, Bank of Canada, Montréal open data |
| Metrics | median price, sales, listings / inventory, days on market, median income, population, interest rates, price-to-income, mortgage payment, income required, affordability |
| Stack | Python, PostgreSQL, PostGIS, dbt Core, n8n, Docker, Power BI |

## 33. Phase 2 — listings

Add a listings extraction platform, and build `fact_listing_snapshot` and
`fact_listing_event`: bedrooms, bathrooms, area, asking price, price per square
foot, condo fees, parking, year built.

## 34. Phase 3 — transactions

Investigate an authorised source of individual transactions. If one becomes
available, `fact_transactions` may be created. **Never a dependency of the
MVP.**

## 35. Repository organisation

One ingestion package per source, SQL migrations and bootstrap, and a dbt
project in four layers:

```text
raw → staging → intermediate → marts
```

## 36. Development rules

- **Simplicity** — no technology or abstraction without a real need.
- **Modularity** — one ingestion module per source.
- **Idempotence** — a pipeline run twice creates no duplicates.
- **External configuration** — secrets and parameters in `.env`, environment
  variables or configuration files. Never an API key, a password or a database
  credential in code.
- **Logging** — every important automated task records `pipeline_name`,
  `run_id`, `started_at`, `finished_at`, `rows_received`, `rows_loaded`,
  `status`, `error_message`.
- **Data quality** — not null, unique, accepted values, relationships, range
  checks, freshness.
- **Raw data** — the raw layer stays as close to the source as possible;
  business transformations happen in the layers after it.
- **Reproducibility** — the project starts from the repository with minimal
  configuration.

---

## 41. Non-negotiable principles

1. Never invent a missing figure.
2. Always distinguish **observed data**, **derived data** and **assumptions**.
3. Always distinguish **asking price**, **sale price** and **municipal
   assessment**.
4. A withdrawn listing is not automatically a sale.
5. A correlation must not be presented as a cause.
6. The main pipeline must keep working without the listings platform.
7. Sources must be replaceable as far as possible.
8. The public repository does not distribute raw listing data.
9. Technical complexity must be justified by a real need.
10. The project must remain maintainable by one person.

## 44. Definition of MVP success

The MVP succeeds when:

1. PostgreSQL runs in Docker;
2. PostGIS is active;
3. several different sources are ingested automatically;
4. pipelines can be rerun without creating duplicates;
5. dbt builds tested analytical tables;
6. the data can be analysed by neighbourhood and period;
7. affordability indicators are computed;
8. Power BI connects to the model;
9. at least one complete dashboard is available;
10. the architecture is documented;
11. the README lets a reader quickly understand the problem, the stack, the
    method and the results.

Scraping and individual listings are not a condition of MVP success.
