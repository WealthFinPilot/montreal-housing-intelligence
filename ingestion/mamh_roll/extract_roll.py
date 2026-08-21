"""
Extract the Quebec property assessment roll (MAMH) for the Island of Montreal.

Why this script exists
----------------------
The Montreal municipality file alone is ~795 MB of XML. Loading it with
`ElementTree.parse()` would build the whole document tree in memory first --
several GB -- and the process would die. So we stream instead.

The streaming idea, in three sentences:
  1. `iterparse` hands us each element as soon as the parser finishes reading it,
     instead of waiting for the end of the file.
  2. We pull out the handful of fields we care about, write one CSV row, and then
     `.clear()` the element -- which frees its memory immediately.
  3. We never hold more than one assessment unit in memory at a time, so a 795 MB
     file costs roughly the same RAM as a 795 KB one.

We also stream straight from the HTTP response, so the 795 MB is never written to
disk at all. Bytes arrive from the network, pass through the parser, and leave as
CSV rows.

Source
------
Rôles d'évaluation foncière du Québec -- Ministère des Affaires municipales et de
l'Habitation, published on Données Québec under CC-BY 4.0.
Field codes below are taken from the MAMH's own
"Guide sur les données du rôle d'évaluation foncière en format ouvert".

Usage
-----
    python extract_roll.py --out roll_2026_island.csv
    python extract_roll.py --out test.csv --limit 5000     # quick smoke test
    python extract_roll.py --out all.csv --residential-only false
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROLL_YEAR = 2026
INDEX_URL = f"https://donneesouvertes.affmunqc.net/role/indexRole{ROLL_YEAR}.csv"
ROLL_URL = "https://donneesouvertes.affmunqc.net/role/RL{code}_{year}.xml"

# The 16 municipalities that make up the Island of Montreal: Ville de Montreal
# plus the 15 "villes liées". Codes come from the MAMH index, matched against the
# city's own limites-administratives-agglomeration boundary file.
ISLAND = {
    "66023": "Montréal",
    "66007": "Montréal-Est",
    "66032": "Westmount",
    "66047": "Montréal-Ouest",
    "66058": "Côte-Saint-Luc",
    "66062": "Hampstead",
    "66072": "Mont-Royal",
    "66087": "Dorval",
    "66092": "L'Île-Dorval",
    "66097": "Pointe-Claire",
    "66102": "Kirkland",
    "66107": "Beaconsfield",
    "66112": "Baie-D'Urfé",
    "66117": "Sainte-Anne-de-Bellevue",
    "66127": "Senneville",
    "66142": "Dollard-des-Ormeaux",
}

# XML tag -> output column. Every code is quoted from the MAMH guide, never guessed.
FIELDS = [
    ("RL0102A", "borough_code"),          # Numéro d'arrondissement
    ("RL0105A", "use_code"),              # Utilisation prédominante
    ("RL0107A", "neighbourhood_unit"),    # Numéro d'unité de voisinage
    ("RL0301A", "frontage_m"),            # Mesure frontale
    ("RL0302A", "lot_area_m2"),           # Superficie
    ("RL0306A", "storeys"),               # Nombre d'étages
    ("RL0307A", "year_built"),            # Année de construction
    ("RL0307B", "year_built_flag"),       # Réelle ou estimée
    ("RL0308A", "floor_area_m2"),         # Aire d'étages
    ("RL0309A", "physical_link"),         # Lien physique
    ("RL0310A", "construction_type"),     # Genre de construction
    ("RL0311A", "dwelling_count"),        # Nombre de logements
    ("RL0401A", "market_ref_date"),       # Date de référence du marché
    ("RL0402A", "land_value"),            # Valeur du terrain
    ("RL0403A", "building_value"),        # Valeur du bâtiment
    ("RL0404A", "total_value"),           # Valeur de l'immeuble
    ("RL0405A", "prev_total_value"),      # Valeur de l'immeuble au rôle antérieur
]

MATRICULE_PARTS = ["RL0104A", "RL0104B", "RL0104C", "RL0104D"]

COLUMNS = (
    ["municipality_code", "municipality_name", "matricule"]
    + [col for _, col in FIELDS]
)

# In the roll, "utilisation prédominante" codes in the 1000-1999 band are
# residential. Everything else is commercial, industrial, institutional, vacant land...
RESIDENTIAL_MIN, RESIDENTIAL_MAX = 1000, 1999

USER_AGENT = "montreal-housing-intelligence/0.1 (data pipeline; contact via repo)"


def peak_memory_mb():
    """Peak working set of this process, in MB.

    This exists to make the streaming claim checkable rather than asserted: after
    chewing through ~800 MB of XML the number should stay small, in the tens of MB.
    Windows-specific, best effort -- returns None elsewhere.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return counters.PeakWorkingSetSize / 1_048_576 if ok else None
    except Exception:
        return None


def open_roll_stream(code: str, year: int = ROLL_YEAR):
    """Open the municipality's roll as a streaming file-like object.

    We do NOT download the file first. urlopen returns an object that yields bytes
    as they arrive, and iterparse reads from it incrementally.
    """
    url = ROLL_URL.format(code=code, year=year)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return url, urllib.request.urlopen(request, timeout=120)


def text_of(unit: ET.Element, tag: str) -> str:
    """Return the text of a direct-ish descendant tag, or '' when absent.

    Absence is normal and meaningful here: a vacant lot has no year built, and a
    non-residential unit has no dwelling count. We record the blank rather than
    inventing a value.
    """
    found = unit.find(f".//{tag}")
    return (found.text or "").strip() if found is not None else ""


def is_residential(use_code: str) -> bool:
    try:
        return RESIDENTIAL_MIN <= int(use_code) <= RESIDENTIAL_MAX
    except (TypeError, ValueError):
        return False


def extract_municipality(code, name, writer, residential_only=True, limit=None):
    """Stream one municipality's roll and write matching units to the CSV.

    Returns (units_seen, units_written).
    """
    url, stream = open_roll_stream(code)
    seen = written = 0
    started = time.time()

    # events=("start", "end") so we can grab the root element on the first event.
    # We need that handle: clearing the record itself is not enough, because the
    # root keeps a reference to every child it has already parsed. Without
    # root.clear() the memory still grows, just more slowly -- this is the classic
    # iterparse mistake.
    context = ET.iterparse(stream, events=("start", "end"))
    _, root = next(context)

    try:
        for event, elem in context:
            if event != "end" or elem.tag != "RLUEx":
                continue

            seen += 1
            use_code = text_of(elem, "RL0105A")

            if not residential_only or is_residential(use_code):
                matricule = "".join(text_of(elem, part) for part in MATRICULE_PARTS)
                row = [code, name, matricule] + [text_of(elem, tag) for tag, _ in FIELDS]
                writer.writerow(row)
                written += 1

            # Free this record, then detach it from the root. Both are required.
            elem.clear()
            root.clear()

            if seen % 50_000 == 0:
                rate = seen / max(time.time() - started, 0.001)
                print(f"    {seen:>7,} unités lues, {written:>7,} retenues "
                      f"({rate:,.0f}/s)", file=sys.stderr)

            if limit and seen >= limit:
                break
    finally:
        stream.close()

    elapsed = time.time() - started
    print(f"  {name:<26} {seen:>7,} lues | {written:>7,} retenues | {elapsed:6.1f}s "
          f"| {url}", file=sys.stderr)
    return seen, written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="output CSV path")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N units per municipality (smoke test)")
    parser.add_argument("--residential-only", default="true",
                        help="true (default) keeps use codes 1000-1999 only")
    parser.add_argument("--only", default=None,
                        help="comma-separated municipality codes, e.g. 66032,66062")
    args = parser.parse_args()

    residential_only = str(args.residential_only).lower() not in ("false", "0", "no")
    targets = dict(ISLAND)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        targets = {k: v for k, v in ISLAND.items() if k in wanted}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    totals = {"seen": 0, "written": 0}
    per_municipality = {}

    print(f"Rôle {ROLL_YEAR} — {len(targets)} municipalités de l'île | "
          f"résidentiel seulement : {residential_only}", file=sys.stderr)

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for code, name in sorted(targets.items(), key=lambda kv: kv[1]):
            try:
                seen, written = extract_municipality(
                    code, name, writer, residential_only, args.limit
                )
            except Exception as exc:  # a municipality failing must not kill the run
                print(f"  {name:<26} ÉCHEC : {exc}", file=sys.stderr)
                per_municipality[name] = {"error": str(exc)}
                continue
            totals["seen"] += seen
            totals["written"] += written
            per_municipality[name] = {"seen": seen, "written": written}

    size_mb = args.out.stat().st_size / 1_048_576
    print(f"\nTotal : {totals['seen']:,} unités lues, {totals['written']:,} retenues",
          file=sys.stderr)
    print(f"Sortie : {args.out} ({size_mb:.1f} Mo)", file=sys.stderr)
    peak = peak_memory_mb()
    if peak:
        print(f"Memoire maximale du processus : {peak:.0f} Mo", file=sys.stderr)

    # A run log, so a rerun can be compared against the last one.
    log = args.out.with_suffix(".run.json")
    log.write_text(json.dumps({
        "roll_year": ROLL_YEAR,
        "residential_only": residential_only,
        "totals": totals,
        "per_municipality": per_municipality,
        "output_mb": round(size_mb, 1),
        "peak_memory_mb": round(peak) if peak else None,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
