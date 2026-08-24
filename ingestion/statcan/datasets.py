"""The Statistics Canada datasets this project ingests, and how to reach them.

Every value below came from a response received on 2026-08-24. Nothing here is
recalled from memory -- see docs/data-sources.md rows 2, 10 and 11.

THE ACCESS PATTERN THAT IS NOT A LINK
-------------------------------------
Two of these three files sit behind an HTML form, not a URL. Posting the form
returns 302 with a Location header naming the real file:

    POST .../boundary-limites/index2021-eng.cfm?Year=21
         year=21&lang=_e&type=b&bound=ct_&format=a&getgeo=Continue
      -> 302, Location carries loc=/.../files-fichiers/lct_000b21a_e.zip

The file path is therefore RESOLVED AT RUN TIME, the way the CKAN resource
URLs are in ingestion/montreal_open_data/datasets.py, and for the same reason:
a path that is correct today is a guess tomorrow. The expected filename below
is checked against what comes back, so a silent substitution fails loudly
instead of loading the wrong geography.

TWO LICENCES, NOT ONE
---------------------
The income table and the attribute file are Statistics Canada content. The
boundary file declares its own licence inside its metadata, and it is a
different one. Both permit redistribution, so unlike APCIQ these figures may
live in a versioned file and in a published report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WWW12 = "https://www12.statcan.gc.ca"
WDS = "https://www150.statcan.gc.ca/t1/wds/rest"


# --------------------------------------------------------------------------
# The perimeter, as codes rather than as names
# --------------------------------------------------------------------------

# Census division 2466 is exactly the Island of Montréal: 16 census
# subdivisions, matching the 16 municipalities of the agglomeration one for
# one, none missing and none extra. Measured on 2026-08-24 over all 13 844
# blocks -- docs/data-sources.md section 2.9.
#
# This is what replaces the spatial join the matrix used to call for.
ISLAND_CD_UID = "2466"
ISLAND_MUNICIPALITY_COUNT = 16

# The census metropolitan area the Island sits in. Wider than the Island: it
# also holds Laval, Longueuil and both shores. Kept whole in the raw layer so
# "the Island against the rest of its CMA" stays available; staging narrows it.
MONTREAL_CMA_UID = "462"

# DGUID prefixes observed in the income file. `S0503` prefixes the CMA itself,
# `S0507` prefixes its census tracts. Read off the data, not off a spec.
CMA_DGUID = f"2021S0503{MONTREAL_CMA_UID}"
CT_DGUID_PREFIX = f"2021S0507{MONTREAL_CMA_UID}"

# Coordinate reference system of the boundary file, proven rather than
# assumed. The attribute file publishes the same representative point twice,
# in Lambert and in latitude/longitude; reprojecting one through EPSG:3347
# lands on the other within 5 cm on every point tested. The project has
# already paid once for a NAD83 lookalike that loaded cleanly and produced
# empty spatial joins -- docs/geography.md section 6.
BOUNDARY_SRID = 3347

# What the source prints instead of leaving a cell empty. Verbatim from the
# symbol legend inside 98100058_MetaData.csv. Three different assertions:
# only the first one means "the number beside this is the value".
SYMBOL_MEANINGS = {
    "": "value published",
    "x": "suppressed to meet the confidentiality requirements of the Statistics Act",
    "...": "not applicable",
}


# --------------------------------------------------------------------------
# Licences
# --------------------------------------------------------------------------

STATCAN_LICENCE = "Statistics Canada Open Licence"
STATCAN_LICENCE_URL = "https://www.statcan.gc.ca/en/reference/licence"

OGL_LICENCE = "Open Government Licence - Canada"
OGL_LICENCE_URL = "https://open.canada.ca/en/open-government-licence-canada"

ATTRIBUTION = (
    "Source: Statistics Canada, 2021 Census of Population. "
    "Reproduced and distributed on an as-is basis with the permission of "
    "Statistics Canada."
)


@dataclass(frozen=True)
class Dataset:
    """One downloadable file, and everything needed to fetch the right one."""

    key: str                  # what this project calls it, and the pipeline name
    title: str
    purpose: str
    licence: str
    licence_url: str

    # How to reach it. Either a form to post, or a WDS endpoint to ask.
    form_url: str | None = None
    form_fields: dict[str, str] = field(default_factory=dict)
    wds_url: str | None = None

    # The basename the resolved URL must end with. A mismatch aborts the run:
    # a boundary file for the wrong geography loads without any error and is
    # only noticed much later.
    expected_filename: str | None = None

    # Logged, and asserted by dbt. Not enforced here -- census geography does
    # change between releases, and the pipeline should report that rather than
    # refuse to run.
    expected_rows: int | None = None


GEOGRAPHIC_ATTRIBUTE = Dataset(
    key="statcan_geographic_attribute",
    title="2021 Census Geographic Attribute File (92-151-X)",
    purpose=(
        "One row per dissemination block, carrying every coarser geographic "
        "code on the same row. This is the file that removed the need for a "
        "spatial join: it states the municipality of every census tract "
        "outright, and its population counts are the weights that will split "
        "a tract between two APCIQ sectors in J3.4."
    ),
    licence=STATCAN_LICENCE,
    licence_url=STATCAN_LICENCE_URL,
    form_url=f"{WWW12}/census-recensement/2021/geo/aip-pia/attribute-attribs/index2021-eng.cfm?Year=2021",
    form_fields={"year": "21", "lang": "_e", "getgeo": "Continue"},
    expected_filename="2021_92-151_X.zip",
    expected_rows=13_844,   # Island blocks, of 498 786 nationally
)

INCOME = Dataset(
    key="statcan_income_statistics",
    title="Table 98100058 -- household income statistics by household type",
    purpose=(
        "Median household income by census tract. NOT one row per tract: the "
        "cube crosses 7 household sizes with 11 household types, so every "
        "geography carries exactly 77 rows. Feeds fact_affordability in J4."
    ),
    licence=STATCAN_LICENCE,
    licence_url=STATCAN_LICENCE_URL,
    wds_url=f"{WDS}/getFullTableDownloadCSV/98100058/en",
    expected_filename="98100058.csv",
    expected_rows=77_385,   # 1 005 geographies x 77, for CMA 462
)

CENSUS_TRACT_BOUNDARIES = Dataset(
    key="statcan_census_tract_boundaries",
    title="2021 cartographic boundary file -- census tracts (lct_000b21a)",
    purpose=(
        "Census tract polygons. Not needed to delimit the Island -- the "
        "attribute file does that with published codes -- but needed for the "
        "Power BI map, and for the eventual tract-to-APCIQ-sector join, which "
        "is a genuine spatial problem because no published attribute carries "
        "boroughs or APCIQ sectors."
    ),
    licence=OGL_LICENCE,
    licence_url=OGL_LICENCE_URL,
    form_url=f"{WWW12}/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?Year=21",
    # type=b selects the cartographic file (clipped to the coastline) over the
    # digital one; bound=ct_ selects census tracts; format=a selects shapefile.
    form_fields={
        "year": "21",
        "lang": "_e",
        "type": "b",
        "bound": "ct_",
        "format": "a",
        "getgeo": "Continue",
    },
    expected_filename="lct_000b21a_e.zip",
    expected_rows=541,      # Island tracts, of 6 247 nationally
)

# Ordered. The boundary step reads its perimeter from the attribute table, so
# it cannot run first -- see run.py.
DATASETS: tuple[Dataset, ...] = (
    GEOGRAPHIC_ATTRIBUTE,
    INCOME,
    CENSUS_TRACT_BOUNDARIES,
)

BY_KEY = {dataset.key: dataset for dataset in DATASETS}
