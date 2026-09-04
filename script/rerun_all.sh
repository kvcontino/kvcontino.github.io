#!/usr/bin/env bash
# rerun_all.sh — the OneCare pipeline order, in one executable place.
#
# WHY THIS EXISTS
# ---------------
# The order spans TWO repositories and was documented in prose in two places
# and enforced by nothing. Prose drifts and cannot be run; this can. Getting it
# wrong is not loud -- the scripts each succeed on stale inputs and the essay
# quietly cites numbers from a previous spec.
#
# DEFAULT IS DRY RUN, on purpose. Executing this rewrites published results and
# figures under _resources/onecare/, which the live essay reads. Pass --run to
# actually execute.
#
# WHAT THE ORDER IS BUILT FROM -- measured 2026-09-03, not copied from the prose:
#   * mde.py does `from synth_medicare import OUTCOMES, EXCLUDE` -- a MODULE
#     import, so that dependency is hard, not conventional.
#   * aco_penetration.py writes data/aco_penetration_states.csv and
#     outputs/aco_penetration.json, which downstream steps read.
#   * The prose order named a step "backcast"; the file is
#     aco_penetration_backcast.py. A runner naming a script that does not exist
#     is worse than no runner.
#
#   rerun_all.sh              # print the order, run nothing
#   rerun_all.sh --run        # actually execute, stopping at the first failure
#   rerun_all.sh --list       # order plus the scripts deliberately NOT run
set -uo pipefail

SITE="$HOME/2_projects/kvcontino.github.io"
COMP="$HOME/2_projects/onecare_retrospective"
RUN=0; LIST=0
for a in "$@"; do
  case "$a" in
    --run) RUN=1 ;;
    --list) LIST=1 ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "rerun_all: unknown argument: $a" >&2; exit 64 ;;
  esac
done

# repo : working directory : script
STEPS=(
  "companion:$COMP:analysis/synth_medicare.py"
  "companion:$COMP:analysis/aco_penetration.py"
  "companion:$COMP:analysis/aco_penetration_backcast.py"
  "companion:$COMP:analysis/mde.py"
  "site:$SITE/_resources/onecare:analysis/build_results.py"
  "site:$SITE/_resources/onecare:analysis/ma_robustness.py"
  "site:$SITE/_resources/onecare:build_figures.py"
)

# NOT in the order, and honestly so. These exist in the companion repo but their
# place in the sequence was never established -- some are one-off pulls, some are
# plotting for notes rather than for the essay. Listing them is the point: a
# runner that silently covers 7 of 15 scripts implies the other 8 do not matter,
# and nobody has actually checked that.
UNORDERED=(
  cbp_county.py county_dose_response.py margins_extended.py
  plot_consolidation.py plot_pophealth.py plot_synth.py
  pophealth_pull.py scm_diagnostics.py
)

printf 'OneCare pipeline order (%s steps across two repos)\n\n' "${#STEPS[@]}"
i=0
for s in "${STEPS[@]}"; do
  i=$((i+1))
  repo="${s%%:*}"; rest="${s#*:}"; wd="${rest%%:*}"; script="${rest#*:}"
  status="ok"
  [ -f "$wd/$script" ] || status="MISSING"
  printf '  %d. [%-9s] %-38s %s\n' "$i" "$repo" "$script" "$status"
done

if (( LIST )); then
  printf '\nIn the companion repo but NOT in this order (place never established):\n'
  for u in "${UNORDERED[@]}"; do printf '     %s\n' "$u"; done
fi

if (( ! RUN )); then
  printf '\nDry run — nothing executed. Re-run with --run to execute.\n'
  printf 'That rewrites published results and figures the live essay reads.\n'
  exit 0
fi

# Refuse to run over a dirty tree: if a step fails halfway, `git diff` is the
# only record of what it managed to change, and pre-existing edits destroy that.
for r in "$SITE" "$COMP"; do
  if [ -d "$r/.git" ] && [ -n "$(git -C "$r" status --porcelain 2>/dev/null)" ]; then
    echo; echo "refusing to run: $r has uncommitted changes."
    echo "  A half-finished run is only diagnosable against a clean tree."
    exit 1
  fi
done

printf '\n'
i=0
for s in "${STEPS[@]}"; do
  i=$((i+1))
  rest="${s#*:}"; wd="${rest%%:*}"; script="${rest#*:}"
  printf '── %d/%d  %s\n' "$i" "${#STEPS[@]}" "$script"
  if [ ! -f "$wd/$script" ]; then
    echo "   MISSING — stopping."; exit 1
  fi
  if ! ( cd "$wd" && python3 "$script" ); then
    echo "   FAILED at step $i — stopping. Downstream steps would run on stale inputs."
    exit 1
  fi
done
printf '\nall %d steps completed\n' "${#STEPS[@]}"
