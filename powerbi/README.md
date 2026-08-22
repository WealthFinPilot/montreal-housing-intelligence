# Power BI connection

## Before opening Power BI Desktop

The database is unreachable until the tunnel is open. From the repository root:

```bash
bash scripts/tunnel-start.sh
```

It prints `OK: PostgreSQL answered at 127.0.0.1:15432` when the far end is
really a PostgreSQL server, not just an open port.

## Connection settings

| Field | Value |
|---|---|
| Connector | PostgreSQL database |
| Server | `localhost:15432` |
| Database | `mhi` |
| Data Connectivity mode | **Import** |
| Authentication kind | **Database** (not Windows) |
| User name | value of `POSTGRES_USER` in `.env` |
| Password | value of `POSTGRES_PASSWORD` in `.env` |
| Encrypt connection | **unchecked** |

Then pick `staging` -> `stg_bank_of_canada__interest_rates` in the Navigator.

## The three settings that are not obvious

**Encrypt connection must be unchecked.** Power BI ticks it by default and the
container does not offer TLS, so the connection fails with a message about the
server not supporting SSL. That is not a weakness here: the traffic already
travels inside the SSH tunnel, which is encrypted end to end. Ticking the box
would ask for a second, redundant layer that the server was deliberately not
configured to provide.

**Import, not DirectQuery.** Decided on 2026-08-21 and verified in Microsoft
documentation: *Publish to web* is incompatible with DirectQuery, so Import is
mandatory for a publicly shared portfolio report anyway. Import also means no
gateway, no Pro licence, and no database exposed to the internet. The data is
quarterly at the analytical grain; freshness is not the constraint here.

**Port 15432, not 5432.** 15432 is the local end of the SSH tunnel. The database
itself listens on 5432 on the server loopback and is unreachable from here.

## What to build for milestone J2

Acceptance criterion 4 asks for one visual showing the policy rate since 2015,
read from PostgreSQL rather than from a CSV.

* Line chart
* X axis: `observation_date` (continuous, not categorical)
* Y axis: `rate_percent`
* Legend: `series_label`

Two series with different rhythms share this table: the policy rate publishes
every business day, the posted mortgage rate once a week. The `frequency`
column says which is which. Never average them together without saying so, and
never let a visual imply the weekly series was observed daily.

`is_posted_rate` marks the mortgage rate as a rate banks ADVERTISE, not one a
borrower contracts. Same distinction as asking price versus sale price.

## Governance warning for the public report

A report published with *Publish to web* exposes the entire semantic model,
including columns no visual displays. Whatever ends up in a `.pbix` intended
for publication must be safe to read in full. Listing tables must never enter
such a file (section 11 of the original brief).

## Refreshing later

Import mode means the data in the report is a copy taken at load time. To
refresh: open the tunnel, open the report, Refresh, republish from Desktop.
There is no scheduled refresh and no gateway by design.

## The .pbix file in this repository

`mhi_interest_rates.pbix` is committed so a reader can open the report without
rebuilding it. Two things to know before ever committing another one.

**A .pbix carries its whole data model, compressed.** Everything loaded in
Import mode is inside the file, including columns no visual displays. Whoever
opens it sees all of it.

**A secret scanner cannot look inside it.** Verified on 2026-08-22: extracting
the archive and searching for a string it certainly contains found nothing,
because the data model is stored compressed. `scripts/check-secrets.sh` now
reports every file it could not read rather than passing over it in silence, but
reporting is all it can do.

So the rule is a decision, not a check: **a .pbix that has ever loaded listing
data must never be committed.** This one holds Bank of Canada interest rates,
which are public. Power BI keeps data source credentials in the local Windows
credential store rather than in the file, so no password travels with it -- that
is a documented product behaviour, not something this repository can verify.
