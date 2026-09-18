# APCIQ Baromètre résidentiel — what is read, and what it is worth

Source: `Baromètre résidentiel MLS®`, Montréal edition, published quarterly by
the **Association professionnelle des courtiers immobiliers du Québec** from
the **Centris** system. One PDF per quarter, 65 pages, 2019 Q2 to the present.

**Source : APCIQ par le système Centris.**

---

## 1. Licence — read this before publishing anything

The same publisher says two different things, and this section is where the
project states which one it follows for what.

**The website terms** ([apciq.ca/conditions-dutilisation](https://apciq.ca/conditions-dutilisation/),
quoted in full in [`data-sources.md`](data-sources.md) section 2.2) forbid
commercial use without written consent, and require APCIQ to be credited.

**The PDF itself is stricter.** Page 65, verbatim:

> « Toute reproduction de l'information qui s'y retrouve, en tout ou en
> partie, directement ou indirectement, est strictement interdite sans
> l'autorisation préalable écrite du titulaire du droit d'auteur. »

### The policy, decided 2026-09-16

This is a non-commercial portfolio project. It **shows** the figures under the
website terms, and it **does not distribute** them:

| | |
|---|---|
| **Shown, credited** | Screenshots of the dashboard in the README, and the Power BI report published with *Publish to web*. Every page carries « Source : APCIQ par le système Centris ». Nothing built on these figures is sold or monetised. |
| **Not distributed** | No APCIQ figure in a tracked text file, an exported dataset or a sample. The 29 archived PDFs and the report's `.pbix` stay out of git. The repository ships the code that reads the source, never the source. |

The four screenshots are `docs/img/report-1-market.png` through
`report-4-rates.png`, taken on 2026-09-17. Section 7 of
`scripts/check-secrets.sh` lists them among the files it cannot look inside:
they carry APCIQ figures on purpose, and this paragraph is the decision that
warning asks for.

The second row is enforced, not promised: section 6 of
`scripts/check-secrets.sh` compares every tracked text file with the figures
actually loaded, and a price-to-income ratio in level counts as a price because
multiplying it by a published census income gives the price back
([`limitations.md`](limitations.md) section 4).

**What *Publish to web* really publishes.** A report published that way exposes
its whole semantic model, hidden columns included: every APCIQ figure the
report loaded becomes readable, not only the ones a visual displays. That is
known and accepted, not overlooked.

**The tension is stated, not hidden.** Page 65 asks for written permission for
any reproduction, and a published report is one. Written permission was
requested before the report was built; no answer had been received on
2026-09-16. If APCIQ objects, the published report is withdrawn and the
screenshots are replaced with versions in which every APCIQ figure is masked.
Nothing in the pipeline or the model depends on either.

**No APCIQ figure is in the repository's text.** The values transcribed by eye that
`tests/test_apciq_parse.py` checks the parser against live in
`data/apciq/oracle-read-by-eye.json`, beside the PDFs and outside git. Absent,
that test skips, exactly as the PDF tests already do on a fresh clone. What
makes a value an oracle is that a human read it off the page, not that it sits
in a tracked file.

**Nor is one in the history.** Those figures had been committed before
2026-08-23, and removing them from the working tree would not have removed
them from `git log -p`. The history was rewritten the same day: commits,
messages and order unchanged, with only the figures inside them replaced by a
marker naming the licence. Verified
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

### Months of inventory — defined on the site, not in the PDF

Not one of the five figures the parser reads, and **not printed in the
Baromètre**: it is derived here, from two columns that are. Its definition and
its thresholds come from the publisher's own glossary —
<https://apciq.ca/en/definitions-and-explanatory-notes>, read 2026-09-17:

> « The number of months needed to sell the entire inventory of properties for
> sale, calculated according to the pace of sales of the past 12 months. It is
> obtained by dividing the inventory **by the average number of sales in the
> past 12 months**. »

| Months of inventory | Market condition, as the publisher words it |
|---|---|
| **< 8** | « favours sellers (seller's market) » |
| **8 to 10** | « balanced, meaning that it does not favour buyers or sellers » |
| **> 10** | « favours buyers (buyer's market) » |

⚠️ **THE DENOMINATOR IS A TWELVE-MONTH AVERAGE, NOT THE QUARTER.** This was got
wrong first, on 2026-09-17, by dividing the quarter's listings by the quarter's
sales ÷ 3. Sales are strongly seasonal — measured on the island, 18 of 21
transitions into Q2 are rises averaging +21.5 %, 18 of 21 into Q3 are falls
averaging −16.2 % — so a quarterly denominator makes the ratio swing with the
calendar. Measured against the correct formula: **mean gap 0.17 to 0.34 months,
worst gap 3.48 on condominium and 5.14 on plex**, and **11 of 75 island slices
land in a different market condition**. The wrong version put plex above 10 and
would have shown a buyer's market that never happened.

**So it is computed from `marts.fact_market_trailing_12m`**, whose figures are
APCIQ's own twelve-month publications — which matters twice over, because
section 7 of `docs/market.md` records that summing four published quarters
exceeds the published twelve-month figure by about 0.5 %.

⚠️ **The thresholds are the publisher's, the arithmetic is ours.** APCIQ does
not print months of inventory per sector in the Baromètre, so no control total
covers it: it inherits whatever the inventory column is worth, including the
four editions section 7 declares defective. It is not shown on those quarters.

**What it shows on the island, over the whole archive** (29 quarters, three
types, APCIQ's formula and thresholds): **87 slices, zero in a buyer's market.**
Condominium is a seller's market on 28 of 29 quarters and balanced on exactly
one — **2026 Q2, the last of the archive**. Plex is balanced on two, single-
family on none.

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
