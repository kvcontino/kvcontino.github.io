#!/usr/bin/env python3
"""
Regenerate vermont-population.json — the baked data bundle for
vermont-population-map.html.

WHY THIS EXISTS
---------------
The map used to fetch the U.S. Census API live from the browser on every page
load. In 2026 the Census API began requiring an API key for these dataset
queries: keyless requests get 302-redirected to a "Missing Key" HTML page,
which the browser's fetch() follows, so JSON.parse() chokes on <html> and the
map never renders. Embedding a key in a public GitHub Pages page would publish
it, so instead we pre-fetch the data here (server-side, with a private key) and
commit the result. The page then loads a static file and needs no key.

The population figures change at most once a year (new ACS 5-year vintage), so a
committed snapshot is the right granularity. Boundaries essentially never change.

USAGE
-----
    python3 build-vermont-population.py

Requires a valid Census API key at ~/.census_api_key (40-char lowercase hex,
mode 600). Get one free at https://api.census.gov/data/key_signup.html.

To retarget another state, change STATE_FIPS (Vermont = 50) and, if you want a
new ACS vintage, bump ACS_YEAR.
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

STATE_FIPS = "50"          # Vermont
ACS_YEAR   = "2024"        # latest ACS 5-year vintage (2020–2024)
OUT_PATH   = Path(__file__).with_name("vermont-population.json")
KEY_PATH   = Path.home() / ".census_api_key"

# VCGI town polygons (keyless; geometryPrecision=4 keeps the file ~1 MB)
BOUNDS_URL = (
    "https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/"
    "FS_VCGI_OPENDATA_Boundary_BNDHASH_poly_towns_SP_v1/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&returnGeometry=true"
    "&geometryPrecision=4&outSR=4326&f=geojson"
)


def census_url(dataset, variables, key):
    """Build a county-subdivision (town) query for the target state."""
    return (
        f"https://api.census.gov/data/{dataset}"
        f"?get={variables}&for=county+subdivision:*&in=state:{STATE_FIPS}"
        f"&key={key}"
    )


def get_json(url, what):
    """Fetch and parse JSON, failing loudly if the response isn't JSON.

    urlopen does NOT follow the Census 302 into an opaque state the way a
    browser fetch does — but if a key problem sends us to missing_key.html we
    still want a clear error rather than a cryptic JSONDecodeError, so we check.
    """
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
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


def main():
    if not KEY_PATH.exists():
        sys.exit(
            f"Census API key not found at {KEY_PATH}. "
            "Get one free at https://api.census.gov/data/key_signup.html"
        )
    key = KEY_PATH.read_text().strip()

    print("Fetching town boundaries (VCGI)…")
    bounds = get_json(BOUNDS_URL, "bounds")

    print("Fetching 2000 Decennial Census SF1…")
    p00 = get_json(census_url("2000/dec/sf1", "P001001,NAME", key), "p00")

    print("Fetching 2020 Decennial Census PL 94-171…")
    p20 = get_json(census_url("2020/dec/pl", "P1_001N,NAME", key), "p20")

    print(f"Fetching ACS 5-Year Estimates ({ACS_YEAR})…")
    acs = get_json(census_url(f"{ACS_YEAR}/acs/acs5", "B01003_001E,NAME", key), "acs")

    bundle = {
        "generated": date.today().isoformat(),
        "note": "Regenerate with build-vermont-population.py. Do not hand-edit.",
        "sources": {
            "bounds": "VCGI / Vermont Open Geodata Portal (town polygons)",
            "p00": "2000 Decennial Census SF1 (P001001)",
            "p20": "2020 Decennial Census PL 94-171 (P1_001N)",
            "acs": f"ACS 5-Year Estimates {ACS_YEAR} (B01003_001E)",
        },
        "bounds": bounds,
        "p00": p00,
        "p20": p20,
        "acs": acs,
    }

    # Compact separators keep the committed file small; the geometry dominates.
    OUT_PATH.write_text(json.dumps(bundle, separators=(",", ":")))
    kb = OUT_PATH.stat().st_size / 1024
    print(
        f"Wrote {OUT_PATH.name}: {len(bounds['features'])} town polygons, "
        f"{len(p00) - 1}/{len(p20) - 1}/{len(acs) - 1} census rows, {kb:.0f} KB"
    )


if __name__ == "__main__":
    main()
