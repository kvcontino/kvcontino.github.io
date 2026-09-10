#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["geopandas", "shapely", "pyproj", "numpy", "pyogrio"]
# ///
"""Rebuild the Albers composite behind the two maps on the SDUD/NADAC page.

    script/build-sdud-map.py [simplify-tolerance]     # default 1.0

Writes script/usmap.json; paste it into the `usmap-data` block of
`_resources/sdud-nadac/index.html`. That page is deliberately self-contained,
so the projection is resolved HERE and the browser gets path strings in a fixed
viewBox: no projection library, no topojson client, no CDN. Tolerance is in
viewBox px; 1.0 gives about 40KB for 52 outlines.

The right margin of the frame is reserved, not borrowed back afterwards --
seven states cannot hold a label inside their own outline at this scale and are
called out into it by the page.
"""
import sys, json, urllib.request
from pathlib import Path

# us-atlas is the Census cartographic boundary set, already topology-clean.
# Cached beside this script so a rebuild needs no network.
SRC_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json"
SRC = Path(__file__).with_name("states-10m.json")
OUT = Path(__file__).with_name("usmap.json")
if not SRC.exists():
    urllib.request.urlretrieve(SRC_URL, SRC)
import numpy as np
import geopandas as gpd
from shapely.affinity import scale as shp_scale, translate as shp_translate
from shapely.geometry import mapping, MultiPolygon, Point as ShPoint

W, H = 980.0, 620.0
CONUS_CRS = "EPSG:5070"
AK_CRS = "EPSG:3338"
HI_CRS = "+proj=aea +lat_1=19 +lat_2=22 +lat_0=20.5 +lon_0=-157 +datum=NAD83 +units=m +no_defs"
PR_CRS = "+proj=aea +lat_1=17.8 +lat_2=18.5 +lat_0=18.2 +lon_0=-66.4 +datum=NAD83 +units=m +no_defs"

FIPS = {
 "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE","11":"DC",
 "12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY",
 "22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT",
 "31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH",
 "40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD","47":"TN","48":"TX","49":"UT",
 "50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY","72":"PR",
}

g = gpd.read_file(SRC, layer="states").set_crs("EPSG:4326")
g["ab"] = g["id"].map(FIPS)
g = g[g["ab"].notna()].copy()

conus = g[~g["ab"].isin(["AK", "HI", "PR"])].to_crs(CONUS_CRS)
ak = g[g["ab"] == "AK"].to_crs(AK_CRS)
hi = g[g["ab"] == "HI"].to_crs(HI_CRS)
pr = g[g["ab"] == "PR"].to_crs(PR_CRS)

# Trim Alaska's Aleutian tail: kept whole it forces the inset so small that the
# mainland becomes a smear.
akg = ak.geometry.iloc[0]
parts = [p for p in (akg.geoms if akg.geom_type == "MultiPolygon" else [akg]) if p.bounds[0] > -2.4e6]
ak_geom = MultiPolygon(parts)

# CONUS is fitted to the LEFT of the frame; the right margin is reserved for the
# callout labels the Northeast cannot hold inline.
x0, y0, x1, y1 = conus.total_bounds
pad, RIGHT_MARGIN = 10, 132
k = min((W - RIGHT_MARGIN - 2 * pad) / (x1 - x0), (H * 0.845) / (y1 - y0))

def to_frame(geom, kk, ox, oy):
    """Projected metres -> frame px. y flips because SVG counts down."""
    return shp_translate(shp_scale(geom, xfact=kk, yfact=-kk, origin=(0, 0)), xoff=ox, yoff=oy)

def place(geom, kk, cx, cy):
    """Scale, then drop the block so its bbox centre lands on (cx, cy)."""
    gm = shp_scale(geom, xfact=kk, yfact=-kk, origin=(0, 0))
    bx0, by0, bx1, by1 = gm.bounds
    return shp_translate(gm, xoff=cx - (bx0 + bx1) / 2, yoff=cy - (by0 + by1) / 2)

blocks = [(r["ab"], to_frame(r.geometry, k, pad - x0 * k, pad + y1 * k)) for _, r in conus.iterrows()]
blocks.append(("AK", place(ak_geom, k * 0.38, 82, 552)))
blocks.append(("HI", place(hi.geometry.iloc[0], k * 1.0, 232, 574)))
blocks.append(("PR", place(pr.geometry.iloc[0], k * 1.3, 706, 582)))

def path_of(geom, prec=1):
    d = []
    gj = mapping(geom)
    polys = gj["coordinates"] if gj["type"] == "MultiPolygon" else [gj["coordinates"]]
    for poly in polys:
        for ring in poly:
            pts = [f"{round(x, prec)},{round(y, prec)}" for x, y in ring]
            out = [pts[0]]
            for p in pts[1:]:
                if p != out[-1]:
                    out.append(p)          # drop duplicates left by rounding
            if len(out) >= 4:
                d.append("M" + "L".join(out) + "Z")
    return "".join(d)

TOL = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
paths, anchors = {}, {}
for ab, geom in blocks:
    gm = geom.simplify(TOL, preserve_topology=True).buffer(0)
    paths[ab] = path_of(gm)
    big = max(gm.geoms, key=lambda p: p.area) if gm.geom_type == "MultiPolygon" else gm
    # Pole of inaccessibility by grid search, not the centroid: Michigan's
    # centroid lands in Lake Michigan and its representative point hugs an edge.
    b = big.bounds
    best, bestd = big.representative_point(), -1.0
    for gx in np.linspace(b[0], b[2], 48):
        for gy in np.linspace(b[1], b[3], 48):
            p = ShPoint(gx, gy)
            if big.contains(p):
                dd = p.distance(big.exterior)
                if dd > bestd:
                    best, bestd = p, dd
    anchors[ab] = [round(best.x, 1), round(best.y, 1)]

out = {"w": W, "h": H, "paths": paths, "anchors": anchors}
OUT.write_text(json.dumps(out, separators=(",", ":")))
print("states:", len(paths), "bytes:", OUT.stat().st_size, "tol:", TOL)
print("-> paste", OUT.name, "into the usmap-data block of "
      "_resources/sdud-nadac/index.html")
