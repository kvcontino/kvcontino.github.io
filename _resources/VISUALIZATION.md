# Visualization standards

How figures on this site are built. Written 2026-09-19, from the rebuild of the
SDUD/NADAC spread scale. It covers the part that kept being re-derived per page:
**a diverging scale on a black ground.**

`_resources/README.md` is the policy for what belongs in this directory. This is
the policy for how the figures in it look.

## The problem a dark ground creates

On a dark ground you can have at most **two** of these three:

- **(a) neutral recedes** — "no deviation" is dark, so it sinks into the page
- **(b) magnitude reads as heavier** — the convention every light-background
  scale has taught every reader
- **(c) extremes stay legible** — the ends do not approach the ground

(a)+(c) is the obvious choice and it fails (b), which is why a reader who works
mostly with light-background scales will say the dark steps "don't read as less
variation." They are right: something in the scale is contradicting the ramp.

## What actually contradicts it

Magnitude riding on **lightness alone**, with chroma left to whatever each hue's
gamut allows. The published SDUD scale did this. Measured in OKLCH its arms were
matched on lightness (0.499 / 0.618 / 0.740 both sides) and not on chroma:

    cool arm   C 0.101  0.126  0.150   (rising outward)
    warm arm   C 0.194  0.188  0.152   (falling outward)

Two consequences, neither caught by a contrast or colour-vision check:

1. Near zero the warm side was nearly **twice** as saturated as the cool side,
   so +1% shouted and −1% whispered on symmetric data.
2. The gradients ran in **opposite directions**, so saturation meant "further
   from neutral" on one side and "closer" on the other.

The steps flanking the neutral therefore came out dark **but saturated**, and
saturation reads as *strong*. The eye was reading a real signal pointing the
wrong way.

## The rule

**Leave the neutral in both channels at once.** Lightness and chroma both rise
away from the midpoint, so a small deviation is a barely tinted grey and a large
one is vivid. "Close to neutral" then looks close to the neutral in
colourfulness as well as lightness.

Construct both arms from the same in-gamut ceiling — take the *smaller* of the
two hues' maximum chroma at each lightness — so the arms are symmetric by
construction rather than by whatever each hue could reach.

`scripts/color_candidates.py` in the `sdud_nadac` project generates these;
`color_compare*.py` render candidates against real data.

## Two alternatives, both rejected on measurement

**Chroma-only at flat lightness** (grey centre, vivid ends, every step well
clear of the ground). Excellent at a glance. Adjacent steps fall to
**ΔE 3.8** — below the threshold where steps can be told apart. A handsome
figure nobody can decode.

**Light centre, dark extremes** (convention-matched). Best measurements of the
three, and correct for a *one-sided* distribution — on the state map only one
state fell in the neutral bin. It is wrong for a *centred* one: the drug grid
has 43% of cells at zero, and a light centre turned it into a glowing slab with
the least interesting value as the loudest thing on the page.

**So the choice is distribution-dependent, not fixed.** Check where the data
actually sits before picking the centre's lightness.

## The shared ceiling peaks — you cannot always have both

Matching chroma across arms and making it rise outward are not always jointly
satisfiable, and the binding constraint is the gamut, not taste. For blue (hue
256) against orange (hue 52) the **shared** in-gamut chroma ceiling peaks near
**L 0.68 at C 0.166** and falls away on both sides — to 0.127 by L 0.749.

So a five-step arm reaching L 0.75 *cannot* keep chroma both matched and rising:
the outermost step is forced back down, which is the defect you were fixing.
Compress the lightness ladder to where the ceiling still rises instead. On the
metro-age-structure diverging ramp that meant ending at L 0.680 rather than
0.749, costing the outermost step 7.79:1 contrast against black versus 7.20:1 —
a real but small price for chroma that reads monotonically.

Compute the ceiling before choosing the ladder, not after.

## Breaks are a separate decision from the palette

The same scale carried both SDUD figures with different breaks, and the state
map's were wrong: at ±2/6/10, **90.4% of states landed in three warm bins and
1.9% at the midpoint** — a zero-anchored diverging ramp on data whose median was
+6.4%. The map could not separate +3% from +50%, and no palette would have
fixed that.

Where the data is lopsided, let the **step count** go asymmetric rather than
moving the neutral off zero. The state map runs 2 cool + 4 warm because 47
states sit above cost and five below; zero stays the neutral step, and the
outermost step of each arm keeps the same lightness so neither extreme looks
louder.

## Always measure

Before shipping any ramp:

- **adjacent ΔE** in OKLab ×100 between neighbouring steps — under ~6 they are
  not separable; these ramps run 9.4 (grid) and 8.3 (map) at minimum
- **contrast against the ground** for every step (the neutral is allowed to sit
  low — that is its job)
- **the share of data landing in each bin** — an empty midpoint or a saturated
  end bin means the breaks are wrong, not the colours

Render the candidates against the real data and look at them. The validator
scores colour, not whether the figure can be read.
