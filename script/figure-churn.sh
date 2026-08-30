#!/usr/bin/env bash
# figure-churn.sh — separate real figure changes from matplotlib's noise.
#
# THE PROBLEM
# -----------
# Re-running build_figures.py rewrites every SVG whether or not the data moved.
# Two things change on every single run, neither of them content:
#
#   * <dc:date> — a wall-clock timestamp in the RDF metadata block;
#   * id="p<hex>" — clip-path ids, randomly generated per run, along with every
#     clip-path="url(#p<hex>)" that references them.
#
# So `git status` shows nine dirty figures after a run that changed one, and
# the only way to find the real one is a grep that was hand-typed four or five
# times in a single session. That grep is this script.
#
# It also makes "revert the content-identical figures" a one-liner, which is
# the actual thing you want afterwards: a commit whose diff is nine timestamp
# churns and one real change is a commit nobody can review.
#
# WHAT IT DOES NOT DO, and why that matters
# -----------------------------------------
# This compares SVG SOURCE. Matplotlib saves figure TEXT as glyph outlines
# (<use xlink:href="#SortsMillGoudy-Regular-32"/>), not as characters, so a
# caption whose words changed shows up here as changed path data — good — but
# you cannot grep these files for the caption text to check it, and a caption
# staleness check therefore needs rendering, not this. Do not extend this
# script to try; see the staging note on caption staleness.
#
# USAGE
#   script/figure-churn.sh                 # report on all changed SVGs
#   script/figure-churn.sh --revert        # also `git checkout` the noise-only ones
#   script/figure-churn.sh --paths a.svg…  # restrict to specific files
#
# Exit 0 = no real changes (or none found), 1 = at least one real change.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

REVERT=0
PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --revert) REVERT=1 ;;
    --paths)  shift; while [ $# -gt 0 ]; do PATHS+=("$1"); shift; done; break ;;
    *) echo "unknown flag: $1" >&2
       echo "usage: figure-churn.sh [--revert] [--paths FILE...]" >&2; exit 64 ;;
  esac
  shift
done

note() { printf '  %s\n' "$1"; }
section() { printf '\n=== %s ===\n' "$1"; }

# Normalise away the two per-run identifiers. Kept as one function so the
# working tree and the committed blob are always canonicalised identically --
# two slightly different sed pipelines would report phantom changes forever.
canon() {
  sed -e '/<dc:date>/d' \
      -e 's/id="p[0-9a-f]\{6,\}"/id="pCANON"/g' \
      -e 's/url(#p[0-9a-f]\{6,\})/url(#pCANON)/g' \
      -e 's/xlink:href="#p[0-9a-f]\{6,\}"/xlink:href="#pCANON"/g'
}

if [ "${#PATHS[@]}" -gt 0 ]; then
  changed=("${PATHS[@]}")
else
  # Only tracked, modified SVGs. An untracked new figure has nothing to diff
  # against and is reported separately rather than counted as churn.
  mapfile -t changed < <(git diff --name-only --diff-filter=M -- '*.svg')
fi

section "changed SVGs"
if [ "${#changed[@]}" -eq 0 ]; then
  note "none — nothing to sort"
  # Still worth surfacing brand-new figures, which git diff never lists.
  mapfile -t untracked < <(git ls-files --others --exclude-standard -- '*.svg')
  if [ "${#untracked[@]}" -gt 0 ]; then
    section "untracked (new figures, not churn)"
    for f in "${untracked[@]}"; do note "NEW    $f"; done
  fi
  exit 0
fi
note "${#changed[@]} modified"

real=(); noise=(); unreadable=()
for f in "${changed[@]}"; do
  if ! git show "HEAD:$f" >/dev/null 2>&1; then
    unreadable+=("$f"); continue
  fi
  a=$(git show "HEAD:$f" | canon | cksum)
  b=$(canon < "$f" | cksum)
  if [ "$a" = "$b" ]; then noise+=("$f"); else real+=("$f"); fi
done

section "verdict"
for f in "${real[@]}";  do note "CHANGED  $f"; done
for f in "${noise[@]}"; do note "noise    $f  (timestamp + clip-path ids only)"; done
for f in "${unreadable[@]}"; do note "?        $f  (no committed version to compare)"; done

if [ "$REVERT" = 1 ] && [ "${#noise[@]}" -gt 0 ]; then
  section "reverting ${#noise[@]} noise-only figure(s)"
  git checkout -- "${noise[@]}" && for f in "${noise[@]}"; do note "reverted $f"; done
fi

printf '\n'
if [ "${#real[@]}" -gt 0 ]; then
  note "${#real[@]} figure(s) really changed, ${#noise[@]} were churn."
  [ "$REVERT" = 1 ] || note "Re-run with --revert to drop the churn before committing."
  exit 1
fi
note "No figure changed. All ${#noise[@]} are regeneration noise."
exit 0
