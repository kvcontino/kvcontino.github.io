#!/usr/bin/env python3
"""
Regenerate nny-population.json — the baked data bundle for
nny-population-map.html (North Country & Adirondack, 15 NY counties).

WHY THIS EXISTS
---------------
See build-vermont-population.py for the full story. Short version: the Census
API now requires a key (keyless requests 302 to a "Missing Key" HTML page that
breaks the browser's JSON.parse), and a public page can't safely embed a key.
So we pre-fetch server-side with a private key and commit the result; the page
then loads a static file and needs no key.

Census pulls are statewide (state:36); the page filters to the 15 counties
client-side by GEOID, so we bake them as-is. Boundaries come pre-filtered to the
15 counties by the NYS service WHERE clause.

USAGE
-----
    python3 build-nny-population.py

Requires a valid Census API key at ~/.census_api_key (mode 600).
Get one free at https://api.census.gov/data/key_signup.html.
"""

import json
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
import urllib.error
from datetime import date
from pathlib import Path

STATE_FIPS = "36"          # New York
ACS_YEAR   = "2024"        # latest ACS 5-year vintage (2020–2024)
OUT_PATH   = Path(__file__).with_name("nny-population.json")
KEY_PATH   = Path.home() / ".census_api_key"

# Boundary simplification. The raw NYS Adirondack polygons are ~7 MB (huge vertex
# counts). At this map's render size (~500 px) that detail is invisible, so we
# simplify with mapshaper before baking. Visvalingam weighting + keep-shapes stops
# any town from collapsing; -clean repairs self-intersections; shared borders are
# simplified together (topology-aware) so no slivers open between towns.
# 6% retention takes the boundary layer from ~7.5 MB to ~250 KB (~30x).
# Requires Node/npx (mapshaper is fetched on first run). Tune SIMPLIFY_RETAIN up
# for more fidelity, down for smaller files.
SIMPLIFY_RETAIN = "6%"
COORD_PRECISION = "0.0005"   # snap coords to ~50 m; trims decimal noise

# 15 counties: state 36 + 3-digit county FIPS. Clinton, Essex, Franklin, Fulton,
# Hamilton, Herkimer, Jefferson, Lewis, Madison, Oneida, Oswego, St. Lawrence,
# Saratoga, Warren, Washington.
COUNTY_PREFIXES = ['36019', '36031', '36033', '36035', '36041', '36043', '36045',
                   '36049', '36053', '36065', '36075', '36089', '36091', '36113', '36115']

# NYS ITS Civil Boundaries, layer 6 (Cities/Towns). Filter by FIPS_CODE prefix so
# the response stays under the service's 1000-record cap and needs no pagination.
_where = ' OR '.join(f"FIPS_CODE LIKE '{p}%'" for p in COUNTY_PREFIXES)
BOUNDS_URL = (
    "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Civil_Boundaries/"
    "FeatureServer/6/query?where=" + urllib.parse.quote(_where) +
    "&outFields=NAME,FIPS_CODE,COUNTY,MUNI_TYPE"
    "&returnGeometry=true&geometryPrecision=4&outSR=4326&resultRecordCount=1000&f=geojson"
)


# 3-digit county FIPS for the 15 counties (drop the state '36' prefix).
COUNTY_FIPS_3 = {p[2:] for p in COUNTY_PREFIXES}


def trim_to_counties(rows):
    """Keep only census rows whose county falls in our 15 counties, plus the header.

    The page filters boundaries to these counties and looks census data up by
    GEOID, so statewide rows outside them are never read — dropping them is
    functionally transparent and cuts each array ~70%.
    """
    header = rows[0]
    ci = header.index("county")
    return [header] + [r for r in rows[1:] if r[ci] in COUNTY_FIPS_3]


def census_url(dataset, variables, key):
    """County-subdivision query for the whole state (page filters client-side)."""
    return (
        f"https://api.census.gov/data/{dataset}"
        f"?get={variables}&for=county+subdivision:*&in=state:{STATE_FIPS}"
        f"&key={key}"
    )


def get_json(url, what):
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            final = r.geturl()
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.exit(f"[{what}] HTTP {e.code} fetching {url}")
    if "missing_key" in final or "invalid_key" in final:
        sys.exit(f"[{what}] redirected to {final} — check ~/.census_api_key")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        sys.exit(f"[{what}] response was not JSON (got: {body[:120]!r})")


def simplify_bounds(geojson):
    """Simplify the boundary GeoJSON with mapshaper, returning the reduced dict.

    Round-trips through temp files: mapshaper reads/writes GeoJSON on disk.
    """
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.geojson"
        dst = Path(td) / "out.geojson"
        src.write_text(json.dumps(geojson))
        cmd = [
            "npx", "-y", "mapshaper", str(src),
            "-simplify", SIMPLIFY_RETAIN, "keep-shapes",
            "-clean",
            "-o", f"precision={COORD_PRECISION}", str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            sys.exit("npx/mapshaper not found — install Node.js to simplify boundaries")
        except subprocess.CalledProcessError as e:
            sys.exit(f"mapshaper failed:\n{e.stderr}")
        out = json.loads(dst.read_text())
    n_in = len(geojson.get("features", []))
    n_out = len(out.get("features", []))
    if n_out != n_in:
        sys.exit(f"simplify dropped features ({n_in} -> {n_out}); lower SIMPLIFY_RETAIN too aggressive")
    return out


def main():
    if not KEY_PATH.exists():
        sys.exit(
            f"Census API key not found at {KEY_PATH}. "
            "Get one free at https://api.census.gov/data/key_signup.html"
        )
    key = KEY_PATH.read_text().strip()

    print("Fetching town/city boundaries (NYS ITS Civil Boundaries)…")
    bounds = get_json(BOUNDS_URL, "bounds")
    if bounds.get("exceededTransferLimit"):
        sys.exit("[bounds] response was truncated (exceededTransferLimit) — needs pagination")

    print(f"Simplifying boundaries with mapshaper (retain {SIMPLIFY_RETAIN})…")
    bounds = simplify_bounds(bounds)

    print("Fetching 2000 Decennial Census SF1…")
    p00 = get_json(census_url("2000/dec/sf1", "P001001,NAME", key), "p00")

    print("Fetching 2020 Decennial Census PL 94-171…")
    p20 = get_json(census_url("2020/dec/pl", "P1_001N,NAME", key), "p20")

    print(f"Fetching ACS 5-Year Estimates ({ACS_YEAR})…")
    acs = get_json(census_url(f"{ACS_YEAR}/acs/acs5", "B01003_001E,NAME", key), "acs")

    # Drop statewide rows outside our 15 counties (page never reads them).
    p00, p20, acs = trim_to_counties(p00), trim_to_counties(p20), trim_to_counties(acs)

    bundle = {
        "generated": date.today().isoformat(),
        "note": "Regenerate with build-nny-population.py. Do not hand-edit.",
        "sources": {
            "bounds": f"NYS ITS GIS Program Office, Civil Boundaries (15 counties); simplified with mapshaper (retain {SIMPLIFY_RETAIN})",
            "p00": "2000 Decennial Census SF1 (P001001), 15 counties",
            "p20": "2020 Decennial Census PL 94-171 (P1_001N), 15 counties",
            "acs": f"ACS 5-Year Estimates {ACS_YEAR} (B01003_001E), 15 counties",
        },
        "bounds": bounds,
        "p00": p00,
        "p20": p20,
        "acs": acs,
    }

    OUT_PATH.write_text(json.dumps(bundle, separators=(",", ":")))
    kb = OUT_PATH.stat().st_size / 1024
    print(
        f"Wrote {OUT_PATH.name}: {len(bounds['features'])} boundary polygons, "
        f"{len(p00) - 1}/{len(p20) - 1}/{len(acs) - 1} census rows, {kb:.0f} KB"
    )


if __name__ == "__main__":
    main()
