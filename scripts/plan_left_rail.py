"""Plan -- and optionally apply -- the left navigation rail of section 15.

    .venv/Scripts/python.exe scripts/plan_left_rail.py
    .venv/Scripts/python.exe scripts/plan_left_rail.py --write powerbi/mhi-Dashboard_v11.pbix
    .venv/Scripts/python.exe scripts/plan_left_rail.py --verify powerbi/mhi-Dashboard_v11.pbix

WHY THIS EXISTS

The page menu needs a 176 px column that no visual occupies, and on 2026-09-11
every one of the four pages was full to both edges: 20 visuals sat inside the
rail, 7 of them full width. Clearing it by hand means reading and retyping X and
Width on 56 visuals -- 112 numbers, each of which is silently wrong if mistyped,
on a report where the central finding of J4.2 is that nothing raises an error.

So the transformation is computed here, from the file, and can be applied to a
COPY of the file. It is the same arrangement as scripts/generate_erd.py: the
numbers are read out of the artefact rather than remembered, so re-running after
a layout change is what stops the plan going quietly stale.

THE RULE, AND WHY IT IS THE ONLY ONE A SCRIPT MAY APPLY

Every visual is compressed horizontally into the band [rail, canvas_width]:

    k        = (canvas_width - rail) / canvas_width
    new_left = rail + left * k
    new_right= rail + right * k

Y and Height are never touched. This preserves every proportion and every
gutter, cannot create a collision that did not already exist, and cannot push
anything off the canvas -- a visual flush at 1920 lands exactly on 1920. Any
other rule ("move only what intrudes") needs an eye on each page and is
therefore Desktop's job, not this script's.

WHAT IT DOES NOT DO

It does not draw the buttons. Section 15 of powerbi/report-design.md specifies
those, and they are four objects built once and pasted, not 56 numbers.

A visual that already lies ENTIRELY inside the rail is left alone, on both the
plan and the verification: by construction it is a menu object, and compressing
it would drag the menu into the band it exists to clear. That is what makes the
script safe to re-run after the menu is built -- and re-running it is the only
way the plan stays true to a layout that keeps changing.

⚠️ --write REZIPS A .pbix. Every entry is copied byte for byte, with its
original compression, except Report/Layout. Whether Power BI Desktop accepts a
rezipped file is Desktop's verdict and nobody else's -- the file carries a
SecurityBindings entry this script does not understand. That is why it refuses
to write over its input: v10 stays whole, and if v11 will not open, the printed
plan is the fallback and nothing was lost but the attempt.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

LAYOUT_ENTRY = "Report/Layout"
DEFAULT_RAIL = 176


# --------------------------------------------------------------------------
# Reading and writing the layout
# --------------------------------------------------------------------------

def read_layout(pbix: Path) -> dict:
    """The report layout, which a .pbix stores as UTF-16-LE JSON with no BOM."""
    with zipfile.ZipFile(pbix) as z:
        return json.loads(z.read(LAYOUT_ENTRY).decode("utf-16-le"))


def write_pbix(source: Path, target: Path, layout: dict) -> None:
    """Copy every entry of `source` into `target`, replacing only the layout.

    Compression is preserved per entry because the DataModel is stored
    uncompressed and re-deflating it would change a part of the file this
    script has no business touching.
    """
    if source.resolve() == target.resolve():
        raise SystemExit("refusing to write over the input file")
    payload = json.dumps(layout, ensure_ascii=False, separators=(",", ":")).encode("utf-16-le")
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w") as zout:
        for item in zin.infolist():
            data = payload if item.filename == LAYOUT_ENTRY else zin.read(item.filename)
            info = zipfile.ZipInfo(item.filename, date_time=item.date_time)
            info.compress_type = item.compress_type
            info.external_attr = item.external_attr
            info.internal_attr = item.internal_attr
            info.create_system = item.create_system
            zout.writestr(info, data)


# --------------------------------------------------------------------------
# The visuals, and what identifies one to a human in Desktop
# --------------------------------------------------------------------------

def _first_measure(node) -> str | None:
    if isinstance(node, dict):
        if "Measure" in node and isinstance(node["Measure"], dict):
            return node["Measure"].get("Property")
        if "Column" in node and isinstance(node["Column"], dict):
            return node["Column"].get("Property")
        for value in node.values():
            found = _first_measure(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _first_measure(value)
            if found:
                return found
    return None


def describe(config: dict) -> str:
    """A label the reader can match to something on screen.

    Deliberately not the container id: Desktop never shows it. A title, or
    failing that the first field the visual carries, is what a person can point
    at.
    """
    visual = config.get("singleVisual") or {}
    kind = visual.get("visualType", "?")
    titles = (visual.get("vcObjects") or {}).get("title")
    if titles:
        try:
            text = titles[0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
            if text:
                return f"{kind} -- “{text}”"
        except (KeyError, IndexError, TypeError):
            return f"{kind} -- <dynamic title>"
    field = _first_measure(visual.get("projections") or {}) or _first_measure(visual)
    return f"{kind} -- {field}" if field else kind


def geometry(container: dict) -> tuple[float, float, float, float]:
    config = json.loads(container["config"])
    position = (config.get("layouts") or [{}])[0].get("position", {})
    return (
        float(position.get("x", container.get("x", 0))),
        float(position.get("y", container.get("y", 0))),
        float(position.get("width", container.get("width", 0))),
        float(position.get("height", container.get("height", 0))),
    )


# --------------------------------------------------------------------------
# The transformation
# --------------------------------------------------------------------------

def planned(x: float, w: float, rail: int, canvas: float) -> tuple[int, int]:
    """New X and Width, computed on the EDGES so no rounding moves a right edge.

    Rounding X and Width independently would let a visual flush against another
    drift a pixel apart; rounding the two edges and subtracting cannot.
    """
    k = (canvas - rail) / canvas
    left = round(rail + x * k)
    right = round(rail + (x + w) * k)
    return left, right - left


def apply_to(container: dict, new_x: int, new_w: int) -> None:
    """Geometry lives in two places in a .pbix and both are authoritative."""
    container["x"] = new_x
    container["width"] = new_w
    config = json.loads(container["config"])
    layouts = config.get("layouts") or []
    if layouts:
        position = layouts[0].setdefault("position", {})
        position["x"] = new_x
        position["width"] = new_w
    container["config"] = json.dumps(config, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# Verification -- the half that makes the rewrite checkable
# --------------------------------------------------------------------------

def verify(layout: dict, rail: int) -> int:
    """The rail is empty, nothing hangs off the right edge, order is preserved."""
    failures = 0
    for section in layout["sections"]:
        canvas = float(section.get("width", 1920))
        for container in section["visualContainers"]:
            x, _, w, _ = geometry(container)
            label = describe(json.loads(container["config"]))
            if x + w <= rail + 0.5:
                continue  # lives entirely in the rail: it IS the menu
            if x < rail - 0.5:
                print(f"  FAIL  {section['displayName']}: {label} starts at x={x:.0f}, inside the rail")
                failures += 1
            if x + w > canvas + 0.5:
                print(f"  FAIL  {section['displayName']}: {label} ends at {x + w:.0f}, past {canvas:.0f}")
                failures += 1
    if failures == 0:
        print(f"  OK    the {rail} px rail is clear on every page and nothing overflows")
    return failures


def main() -> int:
    # Titles carry accents and guillemets; a cp1252 console turns them into
    # question marks, which reads as a data fault and is only a console fault.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pbix", type=Path, help="source report (default: the highest-numbered mhi-Dashboard_v*.pbix)")
    parser.add_argument("--rail", type=int, default=DEFAULT_RAIL, help=f"rail width in px (default {DEFAULT_RAIL})")
    parser.add_argument("--write", type=Path, metavar="OUT.pbix", help="write a transformed COPY, never the input")
    parser.add_argument("--verify", type=Path, metavar="PBIX", help="check a report against the rule and stop")
    args = parser.parse_args()

    if args.verify:
        print(f"VERIFY {args.verify.name}, rail {args.rail} px")
        return 1 if verify(read_layout(args.verify), args.rail) else 0

    source = args.pbix
    if source is None:
        candidates = sorted(Path("powerbi").glob("mhi-Dashboard_v*.pbix"))
        if not candidates:
            print("no powerbi/mhi-Dashboard_v*.pbix found", file=sys.stderr)
            return 2
        source = candidates[-1]

    layout = read_layout(source)
    print(f"SOURCE {source.name}, rail {args.rail} px")

    # ⚠️ RUN TWICE, COMPRESSED TWICE. Found on 2026-09-11 by re-running the
    # script on its own output: every visual was squeezed a second time, and
    # --verify still passed, because a doubly-compressed page has a clear rail
    # and nothing overflowing. Verification cannot see it; refusing to start can.
    intruding = sum(
        1
        for section in layout["sections"]
        for container in section["visualContainers"]
        for x, _, w, _ in [geometry(container)]
        if x < args.rail - 0.5 and x + w > args.rail + 0.5
    )
    if intruding == 0:
        print()
        print(f"NOTHING TO DO -- no visual crosses the {args.rail} px rail in this file.")
        print("It has already been through this transformation, or never needed it.")
        print("Running anyway would compress every visual a SECOND time, and --verify")
        print("would still pass. Pass --rail with a different width if that is what you meant.")
        return 0

    total = 0
    for section in layout["sections"]:
        canvas = float(section.get("width", 1920))
        k = (canvas - args.rail) / canvas
        rows = []
        for container in section["visualContainers"]:
            x, y, w, _ = geometry(container)
            if x + w <= args.rail + 0.5:
                # Already entirely inside the rail, so it is a menu object and
                # not page content. Compressing it would drag the menu into the
                # band it was built to clear, and re-running this script after
                # the menu exists would do it every time.
                continue
            new_x, new_w = planned(x, w, args.rail, canvas)
            rows.append((y, x, new_x, new_w, w, describe(json.loads(container["config"])), container))
        rows.sort(key=lambda r: (r[0], r[1]))

        print()
        print("=" * 78)
        print(f"PAGE {section['displayName']}  --  {len(rows)} visuals, horizontal factor {k:.5f}")
        print("-" * 78)
        print(f"  {'y':>5} {'X now':>6} {'-> X':>6} {'W now':>6} {'-> W':>6}   visual")
        for y, x, new_x, new_w, w, label, container in rows:
            moved = "" if (round(x) == new_x and round(w) == new_w) else " *"
            print(f"  {y:5.0f} {x:6.0f} {new_x:6d} {w:6.0f} {new_w:6d}{moved}  {label}")
            if args.write:
                apply_to(container, new_x, new_w)
            total += 1

    print()
    if args.write:
        write_pbix(source, args.write, layout)
        print(f"WROTE  {args.write}  ({total} visuals repositioned)")
        print()
        print(f"VERIFY {args.write.name}")
        failures = verify(read_layout(args.write), args.rail)
        print()
        print("⚠️  Structural verification only. Whether Desktop OPENS this file is")
        print("    Desktop's verdict: the .pbix carries a SecurityBindings entry this")
        print(f"    script copies without understanding. {source.name} is untouched.")
        return 1 if failures else 0

    print(f"{total} visuals would move. Nothing was written -- pass --write OUT.pbix to apply,")
    print("or type the two numbers per visual into Format visual > General > Properties.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
