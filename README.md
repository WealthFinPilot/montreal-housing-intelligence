# Montreal Housing Intelligence

Analytics platform on the residential real-estate market of the **Island of
Montreal**: heterogeneous public sources brought into one PostgreSQL/PostGIS
model, transformed and tested with dbt, consumed in Power BI.

The question it exists to answer is not "what does a condo cost in Montreal"
but **"where can a first-time buyer still buy, on what income, and how has that
changed?"**

> **Status: milestone J2 complete.** One source, the Bank of Canada, goes end to
> end -- ingestion, raw layer, dbt staging layer with tests, Power BI visual.
> The point of J2 was to cross the whole stack once, on the simplest source,
> before widening. The market, geography and affordability layers are next.

---

## Architecture

```
Bank of Canada Valet API
         |
         |  ingestion/bank_of_canada    Python, idempotent, logged
         v
   raw.boc_observation                  values stored exactly as received
   raw.pipeline_run                     one row per run, with its counts
         |
         |  dbt                         typing, cleaning, tests
         v
   staging.stg_bank_of_canada__interest_rates
         |
         |  SSH tunnel, Import mode
         v
      Power BI
```

Everything runs in Docker on a small VPS, except Power BI. The database listens
on the server loopback only and is reached through an SSH tunnel: it is not
exposed to the internet at any point.

---

## Reproduce it

Nothing below needs anything from the author: no access to the server, no
credentials, no data file. Total time from a fresh clone: about ten minutes.

### What you need

* Docker
* Python 3.12 or later (built and tested on 3.14.6)
* Git Bash, or any POSIX shell. On Windows, the scripts are written for Git Bash.

### 1. Clone and configure

```bash
git clone <this repository>
cd montreal-housing-intelligence
cp .env.example .env
```

Open `.env` and set two things:

```
POSTGRES_PASSWORD=<a long random string>
MHI_DB_PORT=5432
```

Generate the password with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`MHI_DB_PORT=5432` says "the database runs on this machine". Leave it commented
out only if you are using the SSH tunnel layout described further down.

`.env` is git-ignored and must never be committed. `bash scripts/check-secrets.sh`
verifies that, and more, before every commit.

### 2. Start the database  *(acceptance criterion 1)*

```bash
docker compose up -d
docker compose ps
```

Wait for the container to report `healthy`. That is the whole setup: a clone, a
`.env` and one command. The schemas `raw`, `staging` and `marts`, the two raw
tables and the PostGIS extension are created on first start by the scripts in
`sql/bootstrap/`, which run once and never again.

The port mapping is `127.0.0.1:5432`, not `5432`. The database is bound to the
loopback interface and is unreachable from outside the machine. That single
prefix is the security model; do not remove it.

### 3. Install the Python environment

```bash
bash scripts/setup-venv.sh
```

Creates `.venv` and installs the exact versions recorded in
`requirements.lock.txt`. Nothing to activate afterwards: every script in this
repository calls the interpreter inside `.venv` directly.

### 4. Run the ingestion, twice  *(acceptance criterion 2)*

```bash
.venv/Scripts/python.exe -m ingestion.bank_of_canada.run
.venv/Scripts/python.exe -m ingestion.bank_of_canada.run
```

First run:

```
received    : 3629 observations
loaded      : 3629 inserted, 0 updated
```

Second run:

```
received    : 3629 observations
loaded      : 0 inserted, 0 updated
```

The count grows over time as the Bank of Canada publishes new dates; 3629 is
the figure for 2015-01-01 to 2026-08-20. What matters is the second line:
**nothing is inserted and nothing is updated on a repeat run.**

That number is not kept by the script. It comes from the database, which reports
for every row whether it was created or modified. Idempotence itself comes from
the primary key `(series_id, observation_date)` declared on the table: a time
series has one value per date, that fact is stated in the database, so a buggy
script *cannot* create a duplicate.

### 5. Build and test the staging layer  *(acceptance criterion 3)*

```bash
bash scripts/dbt.sh run
bash scripts/dbt.sh test
```

Expect `PASS=11 WARN=0 ERROR=0`.

Then prove the tests are worth something:

```bash
bash scripts/prove-quality-gate.sh
```

This corrupts one value in the raw layer, requires `dbt test` to fail and names
the test that caught it, then repairs the row by re-running the ingestion
pipeline and requires the tests to pass again. The output ends with:

```
=== 3. dbt test must now FAIL ===
   dbt test failed, as required:
      8 of 11 FAIL 1 not_null_stg_bank_of_canada__interest_rates_rate_percent
=== 4. Repairing by re-running the ingestion pipeline ===
   loaded      : 0 inserted, 1 updated
=== 5. dbt test must PASS again ===
   Done. PASS=11 WARN=0 ERROR=0
PROVEN: the quality gate catches a corrupted value, and the pipeline repairs it.
```

Step 4 is not cleanup. It proves the revision path: the pipeline noticed the
stored value no longer matched the source and corrected exactly one row -- the
same mechanism that will pick up a genuine Bank of Canada revision.

The Python test suite runs separately:

```bash
.venv/Scripts/python.exe -m pytest
```

21 tests, of which 9 run against the real tables inside a transaction that is
always rolled back. The suite leaves nothing behind.

### 6. Connect Power BI  *(acceptance criterion 4)*

See **[`powerbi/README.md`](powerbi/README.md)** for the full walkthrough,
including the settings that are not obvious. In short: PostgreSQL connector,
server `localhost:5432` (or `localhost:15432` through the tunnel), database
`mhi`, **Import** mode, **Encrypt connection unchecked**, authentication kind
**Database**, then load `staging.stg_bank_of_canada__interest_rates`.

---

## The layout this project actually runs

The steps above put the database on your own machine. The project itself runs it
on a small VPS that already hosts unrelated production services, which changes
two things.

The container publishes on the **server** loopback, so the database is
unreachable from anywhere -- deliberately, because that host has no firewall and
what protects it is that nothing listens on a public interface. A client on the
laptop reaches it through an SSH tunnel:

```bash
bash scripts/tunnel-start.sh     # 127.0.0.1:15432 here -> 127.0.0.1:5432 there
bash scripts/tunnel-status.sh
bash scripts/tunnel-stop.sh
```

`tunnel-start.sh` does not stop at "the port is open". It sends the first
message of the PostgreSQL protocol and checks the reply, because a tunnel can
happily forward to nowhere.

In that layout, leave `MHI_DB_PORT` at its default of 15432 and fill in
`VPS_HOST`, `VPS_USER` and `VPS_SSH_KEY` in `.env`.

`bash scripts/check-vps.sh` reports the state of the server without modifying
anything on it.

---

## What the database holds today

| Series | Label as published by the source | Frequency | Rows |
|---|---|---|---|
| `V39079` | Target for the overnight rate (business daily) | business daily | 3022 |
| `V80691335` | Conventional mortgage: 5-year | weekly | 607 |

2015-01-01 to 2026-08-20. Policy rate between 0.25 % and 5.00 %, posted
mortgage rate between 4.64 % and 7.04 %.

`V39079` is the policy rate. `V122514`, which carries the similar-looking name
"Overnight rate", is the rate observed in the market -- a different number, and
a mistake that would be invisible on a chart.

---

## Design decisions worth explaining

**Values land in the raw layer as text, not as numbers.** Casting at ingestion
time means either crashing on an unexpected format or silently producing a zero.
Storing the text and casting in dbt means collection never breaks and a format
change surfaces as a failing test naming the exact rows.

**A missing value never becomes a row.** Asking Valet for several series at once
returns one row per date, and a series that published nothing that day is simply
absent from that row. An absent key produces no observation: not a zero, not a
null, not the previous value carried forward.

**An unchanged row is not rewritten.** The upsert updates only rows whose value
actually changed, so `updated_at` keeps meaning "the Bank revised this figure"
rather than "the pipeline ran again".

**The 5-year mortgage rate is a posted rate.** It is what banks advertise, not
what a borrower contracts -- discounts of one to two points are ordinary. The
column `is_posted_rate` marks it. Any affordability figure derived from it is an
assumption, not an observation.

**Two temporal grains share one table.** Daily and weekly series sit side by
side, labelled by the `frequency` column. They must never be averaged together
without saying so, and never summed at all: a rate does not add up.

---

## Sources

Seven datasets, each verified against a real HTTP request with its status code
and test date. See **[`docs/data-sources.md`](docs/data-sources.md)** for the
full matrix: variables actually observed, geographic and temporal grain, licence
quoted with its URL, and automation difficulty.

Bank of Canada data is reproduced under the terms at
<https://www.bankofcanada.ca/terms/>. The Bank of Canada is not responsible for
any use made of this data here.

---

## Historical perimeter

**2019 Q2 onward** for market history, not 2015. The APCIQ quarterly archive
does not go back further (29 consecutive quarters verified on 2026-08-21). A
documented limitation, not an omission -- see `docs/data-sources.md` section 2.1.
Bank of Canada series are not affected and start in 2015 here.

---

## Analytical ground rules

Enforced in the code and the models, not merely stated:

* `asking_price` != `sale_price` != municipal assessment.
* A withdrawn listing is **not** a sale.
* Observed data, derived data and assumption are always distinguished.
* "Association", never "cause".
* Sources have different grains. That is exposed, never hidden behind an
  implicit join.
* A missing value is never invented or silently interpolated.

---

## Limitations

* Revisions overwrite: only the latest value of an observation is kept, with no
  history of previous publications. This project analyses the market, it does
  not audit the Bank of Canada.
* Only two series are ingested so far. The pipeline takes a list, so widening is
  a change to `ingestion/bank_of_canada/series.py` plus the matching labels in
  the dbt model -- and the `accepted_values` test fails until both are updated.
* Power BI runs in Import mode with manual republication. No gateway, no
  scheduled refresh, on purpose: the analytical grain is quarterly.
* The Data Source Matrix has been verified, but only this one source has been
  built. Nothing here yet answers the affordability question in the title.

---

## Repository layout

```
docs/           Data Source Matrix, original brief
ingestion/      One module per source
src/            Shared plumbing (database connection)
tests/          Python test suite
dbt/            staging -> intermediate -> marts, with its tests
sql/bootstrap/  Schemas and tables, run once at database creation
scripts/        Tunnel, environment, secret scan, quality-gate proof
sample_data/    Small real extracts, so the matrix can be checked offline
powerbi/        Report file and connection guide
```

---

## Licence and attribution

The code in this repository belongs to its author. **The data does not**: each
source keeps its own licence, quoted with its URL in `docs/data-sources.md`.
APCIQ figures in particular are usable for non-commercial purposes with
attribution and are **not** redistributed here.
