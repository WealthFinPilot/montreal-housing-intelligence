#!/usr/bin/env python
"""Measure whether a categorical palette is actually distinguishable.

    .venv/Scripts/python.exe scripts/validate_palette.py
    .venv/Scripts/python.exe scripts/validate_palette.py --palette page3-verdict
    .venv/Scripts/python.exe scripts/validate_palette.py --palette page3-verdict \
        --add "#8A8F94=Below the legal minimum"

WHY THIS EXISTS

Two colours can look different side by side on one screen and collapse into
each other on another, in a projector, or for a reader with red-green colour
blindness. "It looks fine" is not a measurement, and this repository does not
accept one anywhere else either.

So this computes CIEDE2000 -- the perceptual distance the CIE published in
2001, where 1.0 is roughly the smallest difference a trained eye can see under
ideal conditions -- between every pair of a palette, and then does it again on
each colour simulated through the three kinds of dichromacy. A pair that stays
above the threshold in all four views is safe; a pair that falls below it in
any one of them is named, with the view that broke it.

WHAT IT IS NOT FOR

⚠️ A CONTINUOUS RAMP MUST NOT BE TESTED ALL-PAIRS. Two neighbouring steps of a
gradient are meant to resemble each other -- that is what makes it a gradient.
Running this over a ramp produces a page of true and useless complaints. Test
only what has to be CATEGORICALLY distinct: the verdict colours of page 3, or
the off-ramp states of page 2 against the ends of its ramp.

Noted 2026-09-09: the palette of 2026-09-02 had been validated from a
throwaway script that was never committed. This is that check, made permanent
and in the language the rest of scripts/ is written in.
"""

from __future__ import annotations

import argparse
import math
import sys

# The palettes this report actually uses. A palette here is a list of
# (hex, name) pairs, and the name is what the reader sees in a tooltip or a
# table -- so two entries with the same name would be a design fault before
# they are a colour one.
PALETTES: dict[str, list[tuple[str, str]]] = {
    # Page 3, after the typed down payment added a fifth class on 2026-09-09.
    # "No published price" is an absence of data and "below the legal minimum"
    # is a verdict: painting them alike would say "we do not know" where the
    # model says "you cannot".
    #
    # ⚠️ Out of reach moved from #C7CCD1 to #A6ADB4 in the same pass, and not
    # for symmetry. The first run of this script measured the palette it had
    # inherited and found #C7CCD1 and #E8EAEC at CIEDE2000 7.0 in deuteranopia
    # -- two greys separated by lightness alone, which is the axis dichromacy
    # leaves intact but which a light grey on a light background spends almost
    # entirely. That pair had been accepted by eye on 2026-08-30.
    "page3-verdict": [
        ("#17527A", "Within reach"),
        ("#5B9BC4", "Borderline"),
        ("#A6ADB4", "Out of reach"),
        ("#7A5C4B", "Below the legal minimum"),
        ("#E8EAEC", "No published price"),
    ],
    # The quarter-over-quarter badges of pages 1 and 2, added 2026-09-10.
    #
    # ⚠️ THIS PALETTE IS FOR THE DARK THEME AND FAILS ON A LIGHT ONE. The
    # report runs "Montreal Immobilier - Executive PropTech Dark", canvas
    # #0E1A25, visual background #192A3A. #B8E0C5 on white is 1.45:1.
    #
    # Red and green collapse onto one axis in protanopia and deuteranopia, so
    # the only separator left is lightness -- and on a dark background every
    # usable colour is already light, which spends most of that range before
    # the palette starts. Four obvious candidates were measured and all four
    # failed: the theme's own good/bad/neutral at 2.2 (tritanopia), Fluent
    # green/red at 4.2 (deuteranopia), Okabe-Ito teal/vermilion at 6.6, and the
    # theme's good/bad with a grey neutral at 8.5. A search over the passing
    # combinations returned this triple as the least drifted from a canonical
    # green (hue 140) and red (hue 4). Worst pair 24.0.
    #
    # The colour is never the only carrier: every badge starts with an arrow.
    "page1-badge": [
        ("#B8E0C5", "Favourable to a first-time buyer"),
        ("#FA584C", "Unfavourable"),
        ("#8FA3B5", "Flat, and the denominator badge"),
    ],
    # Page 2, the states that sit OFF the diverging ramp, against the two ends
    # of the ramp itself. The ramp's own interior steps are deliberately absent.
    "page2-off-ramp": [
        ("#0d366b", "Ramp end -- deepest within reach"),
        ("#6b0f0e", "Ramp end -- deepest shortfall"),
        ("#EDEDED", "Out of the current selection"),
        ("#9E9E9E", "No published price or no 2020 income"),
        ("#6B3FA0", "Shared between two sectors"),
    ],
}

# Below this, two colours are treated as the same by a reader who is not
# comparing them deliberately. 10 is the working floor this project uses for
# CATEGORICAL colours; the CIE does not publish a categorical threshold, so
# this is a stated convention, not a standard.
DEFAULT_THRESHOLD = 10.0


# --------------------------------------------------------------------------
# sRGB -> CIE Lab
# --------------------------------------------------------------------------

def hex_to_rgb(value: str) -> tuple[float, float, float]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"{value!r} is not a six-digit hex colour")
    return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _linearise(channel: float) -> float:
    """Undo the sRGB transfer function. Skipping this is the usual reason a
    hand-rolled colour distance disagrees with every published tool."""
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_xyz(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_linearise(c) for c in rgb)
    return (
        r * 0.4124564 + g * 0.3575761 + b * 0.1804375,
        r * 0.2126729 + g * 0.7151522 + b * 0.0721750,
        r * 0.0193339 + g * 0.1191920 + b * 0.9503041,
    )


# D65, the white point sRGB is defined against.
_WHITE = (0.95047, 1.00000, 1.08883)


def xyz_to_lab(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = (f(c / w) for c, w in zip(xyz, _WHITE))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def hex_to_lab(value: str) -> tuple[float, float, float]:
    return xyz_to_lab(rgb_to_xyz(hex_to_rgb(value)))


def relative_luminance(value: str) -> float:
    return rgb_to_xyz(hex_to_rgb(value))[1]


# --------------------------------------------------------------------------
# CIEDE2000
# --------------------------------------------------------------------------

def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """The CIE 2000 colour difference. Long, and there is no short version:
    every one of these terms corrects a place where CIE76 disagreed with the
    eye -- the blue region, low chroma, and the lightness of dark colours."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7))) if c_bar > 0 else 0.0

    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)

    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cp_bar ** 7 / (cp_bar ** 7 + 25 ** 7)) if cp_bar > 0 else 0.0
    sl = 1 + (0.015 * (lp_bar - 50) ** 2) / math.sqrt(20 + (lp_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -rc * math.sin(math.radians(2 * d_theta))

    return math.sqrt(
        (dlp / sl) ** 2
        + (dcp / sc) ** 2
        + (dHp / sh) ** 2
        + rt * (dcp / sc) * (dHp / sh)
    )


# --------------------------------------------------------------------------
# Dichromacy, Vienot / Brettel / Mollon 1999
# --------------------------------------------------------------------------

# Each matrix maps LMS cone response to what the corresponding dichromat sees.
_LMS_FROM_LINEAR_RGB = (
    (17.8824, 43.5161, 4.11935),
    (3.45565, 27.1554, 3.86714),
    (0.0299566, 0.184309, 1.46709),
)
_LINEAR_RGB_FROM_LMS = (
    (0.0809444479, -0.130504409, 0.116721066),
    (-0.0102485335, 0.0540193266, -0.113614708),
    (-0.000365296938, -0.00412161469, 0.693511405),
)
_SIMULATION = {
    "protanopia": ((0.0, 2.02344, -2.52581), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "deuteranopia": ((1.0, 0.0, 0.0), (0.494207, 0.0, 1.24827), (0.0, 0.0, 1.0)),
    "tritanopia": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-0.395913, 0.801109, 0.0)),
}


def _apply(matrix, vector):
    return tuple(sum(m * v for m, v in zip(row, vector)) for row in matrix)


def simulate(value: str, kind: str) -> str:
    """What `value` looks like to a dichromat of this kind, back as hex."""
    linear = tuple(_linearise(c) for c in hex_to_rgb(value))
    lms = _apply(_LMS_FROM_LINEAR_RGB, linear)
    seen = _apply(_SIMULATION[kind], lms)
    back = _apply(_LINEAR_RGB_FROM_LMS, seen)

    def delinearise(channel: float) -> int:
        channel = min(max(channel, 0.0), 1.0)
        srgb = 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055
        return round(min(max(srgb, 0.0), 1.0) * 255)

    return "#{:02X}{:02X}{:02X}".format(*(delinearise(c) for c in back))


# --------------------------------------------------------------------------

VIEWS = ["normal", "protanopia", "deuteranopia", "tritanopia"]


def check(palette: list[tuple[str, str]], threshold: float) -> int:
    print(f"\n{len(palette)} colours, {len(palette) * (len(palette) - 1) // 2} pairs, "
          f"threshold {threshold:.1f}\n")

    print("  colour   luminance  name")
    print("  " + "-" * 62)
    for value, name in palette:
        print(f"  {value}  {relative_luminance(value):9.3f}  {name}")

    failures: list[tuple[float, str, str, str]] = []
    print("\n  minimum CIEDE2000 over the four views")
    print("  " + "-" * 62)
    for i, (hex_a, name_a) in enumerate(palette):
        for hex_b, name_b in palette[i + 1:]:
            per_view = {}
            for view in VIEWS:
                a = hex_a if view == "normal" else simulate(hex_a, view)
                b = hex_b if view == "normal" else simulate(hex_b, view)
                per_view[view] = ciede2000(hex_to_lab(a), hex_to_lab(b))
            worst_view = min(per_view, key=lambda v: per_view[v])
            worst = per_view[worst_view]
            mark = "  OK" if worst >= threshold else "  <<< TOO CLOSE"
            print(f"  {worst:6.1f}  ({worst_view:<12}) {name_a} / {name_b}{mark}")
            if worst < threshold:
                failures.append((worst, name_a, name_b, worst_view))

    print()
    if failures:
        print(f"  {len(failures)} pair(s) below {threshold:.1f}. A reader cannot be asked "
              f"to tell these apart:")
        for worst, name_a, name_b, view in sorted(failures):
            print(f"    {name_a} / {name_b} -- {worst:.1f} in {view}")
        return 1

    print("  Every pair stays above the threshold in normal vision and in all "
          "three dichromacies.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", default="page3-verdict", choices=sorted(PALETTES))
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        metavar="HEX=NAME",
        help="a candidate colour to test against the palette before adopting it",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    palette = list(PALETTES[args.palette])
    for entry in args.add:
        if "=" not in entry:
            print(f"--add expects HEX=NAME, got {entry!r}", file=sys.stderr)
            return 2
        value, name = entry.split("=", 1)
        palette.append((value.strip(), name.strip()))

    print(f"PALETTE {args.palette}" + (f" + {len(args.add)} candidate(s)" if args.add else ""))
    return check(palette, args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
