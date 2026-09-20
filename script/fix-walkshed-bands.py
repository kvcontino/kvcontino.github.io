#!/usr/bin/env -S uv run --quiet --with pillow --script
"""
Halve the walkshed overlays from 12 x 5-minute bands to 6 x 10-minute.

WHY. Measured on the painted result, all 11 adjacent band pairs sat at OKLab
delta-E 3.24-4.84, under the ~6 floor where steps stop being separable, and 11
of 12 steps were under 3:1 against the map ground. Two causes:

  * alpha was applied TWICE -- baked 165/255 = 0.647 in the PNG, then
    {opacity: 0.65} again on the Leaflet layer, for an effective 0.4206;
  * 12 bands is more than a viridis ramp can separate at any usable alpha.

Dropping the double alpha alone is not enough: at 0.647 the 12 bands still
measure min delta-E 4.67, every pair under the floor. Six bands at 0.647
measures min delta-E 9.77.

HOW, without the renderer. The overlays encode band identity as colour -- each
PNG holds exactly the 12 viridis values at alpha 165 and nothing else -- so the
bands can be merged by remapping pixels, with no access to the travel-time
rasters. Band i collapses into i // 2.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "_resources/nova-walksheds/map/overlays"
VIRIDIS = [(68,1,84),(72,33,114),(66,61,132),(56,87,140),(45,111,142),(36,133,141),
           (30,154,137),(42,176,126),(81,196,104),(134,212,73),(194,223,34),(253,231,36)]
ALPHA = 165
# representative of each merged pair: the upper of the two, so the ramp stays
# monotonic and the darkest step is not the one nearest the ground
REMAP = {(*VIRIDIS[i], ALPHA): (*VIRIDIS[2 * (i // 2) + 1], ALPHA) for i in range(12)}

def main():
    files = sorted(ROOT.rglob("*.png"))
    changed = 0
    for f in files:
        im = Image.open(f).convert("RGBA")
        px = list(im.getdata())
        seen = {p for p in px if p[3] > 0}
        unknown = seen - set(REMAP)
        if unknown:
            raise SystemExit(f"{f.name}: unexpected colours {sorted(unknown)[:3]} -- "
                             "the overlays are not the 12 known band values; stopping "
                             "rather than remapping something this does not understand")
        out = [REMAP.get(p, p) if p[3] > 0 else p for p in px]
        if out != px:
            im.putdata(out); im.save(f, optimize=True); changed += 1
    print(f"{changed} of {len(files)} overlays remapped to 6 bands")

if __name__ == "__main__":
    main()
