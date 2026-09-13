"""The icons that have to be FILES: three slicer icons and a quote mark.

    python scripts/generate_slicer_icons.py
    python scripts/generate_slicer_icons.py --preview out.html

WHY THIS IS NOT A DAX MEASURE, unlike the thirteen card icons of
report-design.md 14.8: a measure whose data category is Image URL renders in the
CALLOUT of a card visual. A slicer has no callout, so an icon beside a slicer is
a canvas image and needs a real file on disk. That is the whole difference, and
it is why these three are versioned in powerbi/icons/ while the other thirteen
live in a document.

⚠️ A canvas image is STATIC. It does not follow the slicer selection: the two
people beside the household-profile slicer stay two people when the reader picks
"one person". It names what the slicer filters, not what is selected.

One set of coordinates drives both outputs, so the SVG kept as source and the
PNG pasted into Desktop cannot drift apart. Geometry is in the same 24x24 grid,
1.6 stroke, round caps and #B4C8DA as the card icons, so the report keeps one
hand throughout.

⚠️ A torso is NOT a half circle -- that reads as an archway. It is a flattened
half-ellipse with two short uprights, found by looking at the first attempt
rather than by reasoning about it. Hence the contact sheet: --preview renders
each icon at 72 px AND at the size it will really be used.

⚠️ THE QUOTE MARK IS FILLED, and that breaks the 1.6 outline the other
sixteen share. It is not a preference: the same mark drawn as an outline reads
as the digits '66' at 24 px -- looked at, on 2026-09-12, before choosing. A
quotation mark is a typographic sign, not a pictogram, and it is set solid
wherever a pull quote is set.

Output: powerbi/icons/{house,person-one,person-two,quote-mark}.{png,svg}
"""
import io
import math
import os
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

COLOUR = "#B4C8DA"
BOX = 24.0          # the design grid, same as the card icons
STROKE = 1.6
SS = 16             # supersampling factor before the final resize
OUT_PX = 128
DEST = "powerbi/icons"

# --- shapes, in the 24x24 grid -------------------------------------------
# poly : a run of points, drawn as one stroked path
# circ : cx, cy, r
# arc  : cx, cy, r, start_deg, end_deg   (0 deg = east, counter-clockwise)

def bust(cx, base_y, half_w, rise, drop=1.6, steps=22):
    """The torso of a figure icon: two short uprights joined by a FLATTENED
    half-ellipse. A true half-circle reads as an archway, not as shoulders --
    measured by eye on the first attempt, 2026-09-12."""
    pts = [(cx - half_w, base_y + drop), (cx - half_w, base_y)]
    for i in range(steps + 1):
        t = math.pi - math.pi * i / steps
        pts.append((cx + half_w * math.cos(t), base_y - rise * math.sin(t)))
    pts.append((cx + half_w, base_y + drop))
    return pts


COMMA = [(-3.4, 0.9, -5.7, 3.6, -5.7, 6.9),
         (0.0, 2.4, 1.6, 4.1, 3.8, 4.1),
         (2.0, 0.0, 3.5, -1.5, 3.5, -3.5),
         (0.0, -1.9, -1.4, -3.3, -3.2, -3.3),
         (-0.3, 0.0, -0.6, 0.0, -0.9, 0.1),
         (0.5, -1.4, 1.7, -2.5, 3.3, -3.1)]


def comma(shift):
    """One comma of the quotation mark: a disc with a rising horn, as relative
    cubic segments. The SVG writes these curves and the PNG samples them, so the
    file on disk and the DAX measure of report-design.md 14.8 cannot drift."""
    return ((10.2 + shift, 6.4), COMMA)


def flatten(start, segs, steps=26):
    """Walk a relative cubic path into a dense polygon, for the raster side."""
    pts, (cx, cy) = [start], start
    for d1x, d1y, d2x, d2y, dx, dy in segs:
        p0, p1 = (cx, cy), (cx + d1x, cy + d1y)
        p2, p3 = (cx + d2x, cy + d2y), (cx + dx, cy + dy)
        for i in range(1, steps + 1):
            t = i / steps
            u = 1 - t
            pts.append(
                (u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
                 u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]))
        cx, cy = p3
    return pts


ICONS = {
    "house": {
        "label": "Property type",
        "parts": [
            ("poly", [(2.6, 10.0), (12.0, 2.8), (21.4, 10.0)]),
            ("poly", [(4.9, 8.6), (4.9, 20.6), (19.1, 20.6), (19.1, 8.6)]),
            ("poly", [(9.7, 20.6), (9.7, 14.4), (14.3, 14.4), (14.3, 20.6)]),
        ],
    },
    "person-one": {
        "label": "One person",
        "parts": [
            ("circ", (12.0, 7.6, 3.9)),
            ("poly", bust(12.0, 19.6, 7.3, 5.0)),
        ],
    },
    "person-two": {
        "label": "Two people - a couple",
        "parts": [
            ("circ", (6.7, 8.6, 3.0)),
            ("poly", bust(6.7, 20.0, 4.1, 4.2, drop=1.2)),
            ("circ", (17.3, 8.6, 3.0)),
            ("poly", bust(17.3, 20.0, 4.1, 4.2, drop=1.2)),
        ],
    },
    "quote-mark": {
        "label": "Opening quotation mark",
        "parts": [("fill", comma(0.0)), ("fill", comma(9.5))],
    },
}


# --- SVG ------------------------------------------------------------------
def arc_path(cx, cy, r, a0, a1):
    """SVG arc. Angles in degrees, 0 = east, counter-clockwise, screen y down."""
    def pt(a):
        t = math.radians(a)
        return cx + r * math.cos(t), cy - r * math.sin(t)
    x0, y0 = pt(a0)
    x1, y1 = pt(a1)
    large = 1 if abs(a1 - a0) > 180 else 0
    # counter-clockwise in maths = sweep 0 with y pointing down
    return "M%s %sA%s %s 0 %d 0 %s %s" % (_n(x0), _n(y0), _n(r), _n(r), large,
                                          _n(x1), _n(y1))


def _n(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def to_svg(parts):
    body = []
    for kind, spec in parts:
        if kind == "poly":
            d = "M" + " L".join("%s %s" % (_n(x), _n(y)) for x, y in spec)
            body.append("<path d='%s'/>" % d)
        elif kind == "circ":
            cx, cy, r = spec
            body.append("<circle cx='%s' cy='%s' r='%s'/>" % (_n(cx), _n(cy), _n(r)))
        elif kind == "arc":
            body.append("<path d='%s'/>" % arc_path(*spec))
        elif kind == "fill":
            (sx, sy), segs = spec
            d = "M%s %sc" % (_n(sx), _n(sy)) + " ".join(
                " ".join(_n(v) for v in seg) for seg in segs) + "z"
            body.append("<path d='%s' fill='%s' stroke='none'/>" % (d, COLOUR))
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' "
            "viewBox='0 0 24 24' fill='none' stroke='%s' stroke-width='%s' "
            "stroke-linecap='round' stroke-linejoin='round'>%s</svg>"
            % (COLOUR, STROKE, "".join(body)))


# --- PNG ------------------------------------------------------------------
def to_png(parts, path):
    size = int(BOX * SS)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(1, int(round(STROKE * SS)))
    rgb = tuple(int(COLOUR[i:i + 2], 16) for i in (1, 3, 5)) + (255,)

    def cap(x, y):
        r = w / 2.0
        d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=rgb)

    for kind, spec in parts:
        if kind == "poly":
            pts = [(x * SS, y * SS) for x, y in spec]
            d.line(pts, fill=rgb, width=w, joint="curve")
            cap(*spec[0])
            cap(*spec[-1])
        elif kind == "circ":
            cx, cy, r = spec
            d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
                      outline=rgb, width=w)
        elif kind == "arc":
            cx, cy, r, a0, a1 = spec
            # PIL arcs run clockwise from 3 o'clock with y down; our angles are
            # counter-clockwise, so mirror them.
            d.arc([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
                  start=-a1, end=-a0, fill=rgb, width=w)
            for a in (a0, a1):
                t = math.radians(a)
                cap(cx + r * math.cos(t), cy - r * math.sin(t))
        elif kind == "fill":
            start, segs = spec
            d.polygon([(x * SS, y * SS) for x, y in flatten(start, segs)],
                      fill=rgb)

    img = img.resize((OUT_PX, OUT_PX), Image.LANCZOS)
    img.save(path)
    return img


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Draw the icons that are files.")
    ap.add_argument("--preview", metavar="HTML",
                    help="also write a contact sheet there, to judge the "
                         "drawings at the size they will really be used")
    args = ap.parse_args()

    os.makedirs(DEST, exist_ok=True)
    cells = []
    for name, spec in ICONS.items():
        svg = to_svg(spec["parts"])
        ET.fromstring(svg)                      # never ship an unparsed drawing
        io.open("%s/%s.svg" % (DEST, name), "w", encoding="utf-8").write(svg)
        to_png(spec["parts"], "%s/%s.png" % (DEST, name))
        big = svg.replace("width='24' height='24'", "width='72' height='72'")
        cells.append(
            "<figure><div class='sw'>%s</div><div class='b'>%s</div>"
            "<div class='p'><img src='%s/%s.png' width='40' height='40' alt=''>"
            "<img src='%s/%s.png' width='28' height='28' alt=''></div>"
            "<figcaption>%s<br><span class='t'>%s</span></figcaption></figure>"
            % (big, svg, DEST, name, DEST, name, spec["label"], name))
        print("%-12s svg + png ok" % name)

    html = """<!doctype html><meta charset="utf-8"><title>Icones de segment</title>
<style>
 body{background:#0E1A25;color:#F2F6FA;font:14px system-ui,'Segoe UI',sans-serif;margin:0;padding:28px 32px 44px}
 h1{font-size:18px;margin:0 0 5px}
 p.n{color:#C2D0DE;font-size:12.5px;margin:0 0 22px;max-width:86ch;line-height:1.5}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:14px}
 figure{margin:0;background:#1C2F41;border-radius:8px;padding:18px 12px 14px;text-align:center}
 .sw{height:80px;display:flex;align-items:center;justify-content:center}
 .b{height:30px;display:flex;align-items:center;justify-content:center}
 .p{height:48px;display:flex;align-items:center;justify-content:center;gap:14px;
    border-top:1px solid #2B4760;margin-top:8px;padding-top:8px}
 figcaption{margin-top:8px;font-size:11.5px;color:#C2D0DE;line-height:1.4}
 .t{font-size:10px;letter-spacing:.05em;color:#8FA3B5}
</style>
<h1>Les icones qui sont des fichiers</h1>
<p class="n">Ligne du haut : le <b>SVG</b> a 72&nbsp;px puis a 24&nbsp;px.
Sous le trait : le <b>PNG</b> a 40 et 28&nbsp;px, c'est-a-dire ce que Power BI affichera
reellement. Meme grille 24&times;24 et meme trait 1,6 que les treize icones de carte,
en <b>#B4C8DA</b>. Le guillemet est la seule forme <b>pleine</b> : au trait,
il se lit &laquo;&nbsp;66&nbsp;&raquo;.</p>
<div class="grid">%s</div>
""" % "".join(cells)
    if args.preview:
        io.open(args.preview, "w", encoding="utf-8").write(html)
        print("\ncontact sheet:", args.preview)
    else:
        print("\n(no contact sheet; pass --preview out.html for one)")


if __name__ == "__main__":
    main()
