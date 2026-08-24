# APCIQ Baromètre résidentiel — what is read, and what it is worth

Source: `Baromètre résidentiel MLS®`, Montréal edition, published quarterly by
the **Association professionnelle des courtiers immobiliers du Québec** from
the **Centris** system. One PDF per quarter, 65 pages, 2019 Q2 to the present.

**Source : APCIQ par le système Centris.**

---

## 1. Licence — read this before publishing anything

The licence printed inside the PDF is stricter than the one on the website.
Page 65, verbatim:

> « Toute reproduction de l'information qui s'y retrouve, en tout ou en
> partie, directement ou indirectement, est strictement interdite sans
> l'autorisation préalable écrite du titulaire du droit d'auteur. »

Consequences, all of them binding:

- **No APCIQ figure may enter a Power BI report published to the web.** A
  published report exposes its whole semantic model, hidden columns included.
  The same rule the project already applies to listings.
- No APCIQ figure belongs in a versioned file, an exported dataset, or a
  screenshot in a README.
- The archived PDFs in `data/apciq/` are not versioned and never will be.

**No APCIQ figure is in the repository.** The values transcribed by eye that
`tests/test_apciq_parse.py` checks the parser against live in
`data/apciq/oracle-read-by-eye.json`, beside the PDFs and outside git. Absent,
that test skips, exactly as the PDF tests already do on a fresh clone. What
makes a value an oracle is that a human read it off the page, not that it sits
in a tracked file.

**Nor is one in the history.** Those figures had been committed before
2026-08-23, and removing them from the working tree would not have removed
them from `git log -p`. The history was rewritten the same day, the way the
author e-mail was: 22 commits, their messages and their order unchanged, with
only the figures inside them replaced by a marker naming the licence. Verified
by sweeping every blob of every commit, not by inspecting the tip.

---

## 2. What the archive contains

| | |
|---|---|
| URL pattern | `https://com.apciq.ca/sam/pdf/bar/{YYYY}/{YYYYQQ}-bar-mtl.pdf` |
| Range | 2019 Q2 → present. 2019 Q1 returns 404; the archive does not go further back |
| Editions on disk | 29 as of 2026-08-23, about 200 MB |
| Page size | 1008 × 612 pt through 2025 Q2, then 3825 × 2340 pt |
| Authentication | none |
| `HEAD` | returns 302 for everything, including URLs that do not exist. Probing costs a GET |

The `-fr` suffix seen on some URLs is an alias: 2025 Q3 and 2025 Q4 answer
under both names with byte-identical files. One URL pattern is enough.

---

## 3. What is read

Each of the 19 island pages — the island itself, then its 18 APCIQ sectors —
carries three tables. **Tableau 2**, « Statistiques Centris détaillées par
catégories de propriétés », is the one ingested:

```
3 property categories   Unifamiliale · Copropriété · Plex (2 à 5 logements)
× 5 metrics             sales · active listings · median price
                        · average price · average days on market
× 3 periods             the quarter · the trailing 12 months · a 5-year change
× 19 areas              the island and its 18 sectors
= 855 figures per edition
```

### What is deliberately not read

- **Tableau 1** (« Sommaire de l'activité Centris ») is the only place new
  listings and sales volume appear — but for the total residential market
  only, a grain that cannot enter `fact_market`, whose rows are quarter ×
  geography × property type. **Two of its figures are read for control only**
  (see §5) and never ingested. Half-doing it would be worse than the gap.
- **Tableau 3** (market conditions by price band) is left for later.
- **Sectors 19 and above** are Laval and the two shores. Off the island.

---

## 4. What the figures mean — from page 65, verbatim

| Metric | Definition as printed | What follows from it |
|---|---|---|
| Variation rates | « les taux de variation sont calculés par rapport au même trimestre de l'année précédente » | Year over year. **Never** quarter over quarter |
| Median price | « Valeur médiane des ventes effectuées au cours de la période visée » | A **sale** price. Not an asking price, not a municipal assessment |
| Active listings | « Nombre d'inscriptions dont le statut est en vigueur le dernier jour du mois. Les données trimestrielles et annuelles correspondent à la moyenne des données mensuelles » | An average of month-end counts. Adds up across geographies, **never across time** |
| Sales | « La date de vente est celle de l'acceptation de la promesse d'achat » | Not the notarised date |
| Days on market | « Nombre moyen de jours entre la date de signature du contrat de courtage et la date de vente » | |

And the warning APCIQ prints on the same page, worth repeating wherever these
figures are shown:

> « les prix moyens et médians [...] ne reflètent pas nécessairement la valeur
> moyenne ou médiane de l'ensemble des propriétés d'un Secteur. [...] Il faut
> donc interpréter ces statistiques avec prudence, en particulier lorsque le
> nombre de transactions est faible. »

### Three ways a cell can be empty, and they are not the same

| Printed | Means | Kept as |
|---|---|---|
| `123 456 $` | a figure | the text, cast downstream |
| `**` | « Nombre de transactions insuffisant pour produire une statistique fiable » — **withheld**, the market exists | `is_withheld_by_source` |
| `-` | nothing to report. L'Île-des-Sœurs has no plex at all | `is_nothing_to_report`; **zero on a count row only** |
| nothing at all | nothing was printed. Seen only on 2019-era days-on-market cells | `NULL` |

Reading the dash as zero is an interpretation. It is **verified** by the
control totals, not assumed: with the dash read as zero the three categories
of every page add up to the sales total printed beside them, on all 551 pages
of the archive. Were the dash hiding a figure, the sums would run short
wherever one appears. A dash on a **price** row is never zero — it means there
was nothing to price.

---

## 5. Why there is no table in this PDF, and how it is read anyway

The Baromètre is a Power BI export: no table structure, no ruling lines, only
text boxes at absolute positions. `extract_text()` interleaves the columns
into an unreadable stream. **Position is the only thing that says what a
number means** — and three things about that position are not stable. Each
broke a version of the parser:

1. **The page size tripled** in 2025 Q3. Every coordinate in `parse.py` is
   therefore a fraction of the page, never a point measurement.
2. **The columns move from one edition to the next _and from one page to the
   next_.** Power BI sizes each table to its own content: the 2021 Q4 island
   page puts its first column at 0.581 of the width, its Villeray page at
   0.542. Fixed column bands, however carefully measured, are the wrong tool —
   three measurement campaigns produced three sets of bands, all wrong
   somewhere. **The parser calibrates on each page.**
3. **A cell can be typeset up to 0.003 of a page above or below its own
   label.** Grouping by vertical proximity therefore drops cells silently. The
   label anchors the row instead.

Cells are **attributed to the nearest column anchor, never cut out by
boundaries**. A boundary drops whatever falls between two bands, without
saying so; attribution places everything, and refuses loudly what it cannot
place.

Also worth knowing: the sector title separator is not stable either. Every
edition writes `Secteur 3 : Lachine/Lasalle` except 2025 Q3, which writes
`Secteur 3 - Lachine/Lasalle` — and changes its mind halfway, keeping the
colon for its own sectors 1 and 2.

---

## 6. The controls — and why they are stored rather than asserted

**47 controls run on every edition**, and their verdicts are loaded into
`raw.apciq_control_total` alongside the figures, in the same transaction.

| Control | Question it answers | Tolerance |
|---|---|---|
| `page_table1_vs_table2` | *Did we read this page correctly?* Tableau 1's total for the area against the sum of Tableau 2's three categories — two figures printed a few centimetres apart, read with the same column anchors | 0 on sales, 2 on listings |
| `sectors_vs_island` | *Is the source coherent from one page to the next?* The 18 sector pages against the island page, category by category | 0 on sales, 9 on listings |

Tolerances are **derived, not chosen**. A sum of counts has nothing to round,
so sales must match exactly. Active listings are averages rounded once per
published figure: three against one page total cannot drift past 2, eighteen
against one island total cannot drift past 9. Loose enough to be honest, tight
enough to be a control — a column read one place over would be out by hundreds.

**Two controls, not one.** An earlier version had only the sector-versus-island
check on sales. It balanced while the parser was silently dropping cells that
sat a fraction below their label: it validates the columns, not the rows.

### What stops the load, and what does not

- **Cannot read** → the edition is refused, nothing is written. Missing areas,
  missing rows, calibration failure, a cell too far from every column, and
  **Tableau 1 and Tableau 2 disagreeing on sales for the same page**. Loading
  half a positional parse is worse than loading nothing, because the result
  looks complete.
- **Read correctly, but the source does not add up** → loaded, with the failed
  control beside it. Refusing those editions would destroy sound figures and
  the only evidence of the defect at the same time.

The line between the two is drawn by an asymmetry: when sales reconcile to the
unit on a page and listings do not, the columns are demonstrably right, so the
contradiction belongs to the publisher.

---

## 7. Where the source contradicts itself (verified 2026-08-23, 29 editions)

**25 editions pass all 47 controls. 83 controls out of 1 363 fail, on four
editions. They are not of the same order.**

> The figures behind the percentages below are not reproduced here — §1
> applies to this file too. They are in `raw.apciq_control_total`, one row per
> reconciliation, published total and computed total side by side.

### 2021 Q4, 2022 Q1, 2022 Q2 — active listings do not reconcile anywhere

The Villeray page of 2021 Q4 is the clearest case. Same page, same export,
same column anchors, same code:

| | Tableau 1 vs sum of Tableau 2's three categories |
|---|---|
| Sales | match **to the unit** ✅ |
| Active listings | the categories fall **22 % short** of the printed total ❌ |

The same shortfall appears on all 19 pages, and across pages: the 18 sectors
reach **54 %** of the island page on single-family active listings, while
their sales reach exactly **100 %**.

**These three quarters have no usable active-listing figures at any
geography.** Their sales, prices and days on market are sound and reconcile
exactly. This matters more than it looks: those are the tightest-inventory
quarters of the whole series.

### 2023 Q4 — a small cross-page excess

Every page agrees with itself, 19 out of 19. The sectors merely exceed the
island by **0.3 %** on quarterly sales and **4.3 %** on active listings. A
different order of magnitude and a different verdict — usable as is, provided
the discrepancy is stated.

### How this is kept visible

The seed `apciq_known_publisher_defect` declares those eight edition ×
control × metric pairs, and
`assert_apciq_controls_hold_or_are_accounted_for` fails **in both
directions**: on a control failure nobody has declared, and on a declaration
that no longer matches anything. The second direction is the one that matters
— an exemption nobody re-examines is how a workaround becomes permanent.

**Nothing downstream may present active listings for 2021 Q4, 2022 Q1 or
2022 Q2 without saying so.** That rule belongs in the marts, where it is
testable. `stg_apciq__control_totals` is what makes it possible to write.

---

## 8. Geography

APCIQ cuts the island into **18 numbered sectors**, defined on page 6 of every
edition. Numbering and composition are identical in 2019 Q2, 2022 Q4 and
2026 Q2 — no historisation needed.

Two traps, both recorded in `docs/geography.md`:

- **A sector name is not a geography.** Sector 9 is called « Centre » and
  contains Hampstead, Mont-Royal, Outremont and Westmount.
- **APCIQ cuts two boroughs in half.** CDN–NDG between sectors 7 and 8, Verdun
  between 4 and 10. **There is no APCIQ median price for the borough of
  CDN–NDG**, and `marts.bridge_apciq_sector_geography` makes that ambiguity
  visible with two rows rather than producing one convenient wrong number.

Sector 4 does **not** overlap sector 10: the 18 sectors sum exactly to the
island on quarterly sales, on all three categories, on every edition that
reconciles. A double count would exceed it.

---

## 9. Practical notes

```bash
python -m ingestion.apciq.run                 # every quarter since 2019 Q2
python -m ingestion.apciq.run --dry-run       # fetch, read, control, write nothing
python -m ingestion.apciq.run --only 2026Q2   # one edition
python -m ingestion.apciq.run --force         # re-download what is cached
```

- Reading a 2026-format edition costs about **30 seconds**: roughly 1 470
  vector objects per page for the charts, all parsed by pdfminer on the way to
  the text. Older editions take 5. The reader stops at page 26, as soon as all
  19 areas are in hand.
- PDFs are archived on first fetch and read from disk afterwards. The series
  survives the source reorganising.
- A gap **inside** the series is refused; a missing quarter at the **end** is
  normal — APCIQ publishes a few weeks after a quarter closes.
