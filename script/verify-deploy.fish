#!/usr/bin/env fish
# verify-deploy.fish — poll the Pages run to conclusion, then prove the change
# is actually SERVED.
#
# WHY
# ---
# A green `git push` is not a published site, and a green Actions run is not
# either. The two failure modes are different and both have happened here:
# the build can fail after a clean push, and the deploy can succeed while the
# CDN still serves the previous copy for a minute or two. See the memory note
# reference-pages-deploy-vs-build.
#
# This was done by hand on 2026-08-30 -- watch `gh run list`, then curl four
# URLs and grep one for a known string. That is a script.
#
# USAGE
#   script/verify-deploy.fish                       # run status + the site's front page
#   script/verify-deploy.fish /_resources/foo/      # ...and assert this path is 200
#   script/verify-deploy.fish /path/ "some text"    # ...and that it contains this string
#
# Exit 0 = deployed and serving. 1 = run failed, timed out, or the assertion
# did not hold.

set -l base "https://kvcontino.github.io"
set -l path $argv[1]
set -l needle $argv[2]

# --- 1. the run ------------------------------------------------------------
# `gh run list` is the source of truth for the build+deploy half. Poll rather
# than sleep-and-hope: a Pages run is usually 30-60s but has taken minutes.
echo "== waiting for the Pages run =="
set -l done 0
for i in (seq 1 40)
    set -l row (gh run list --limit 1 --json status,conclusion,displayTitle \
        -q '.[0] | .status + " " + (.conclusion // "-") + " " + .displayTitle' 2>/dev/null)
    if test -z "$row"
        echo "  could not read run status (gh not authenticated?)"; exit 1
    end
    echo "  $row"
    if string match -q 'completed*' -- $row
        if string match -q '*success*' -- $row
            set done 1
        else
            echo "  run did NOT succeed"; exit 1
        end
        break
    end
    sleep 15
end
if test $done -eq 0
    echo "  timed out after ~10 min"; exit 1
end

# --- 2. what is actually served -------------------------------------------
# The run being green says the artifact was published, not that the edge is
# handing it out yet. Retry briefly rather than declaring failure on the first
# stale response.
echo "== what the site actually serves =="
function _code -a url
    curl -s -o /dev/null -w '%{http_code}' --max-time 20 $url
end

set -l urls "$base/" "$base/_pages/presentations.html" "$base/feed.xml"
if test -n "$path"
    set urls $urls "$base$path"
end

set -l bad 0
for u in $urls
    set -l c (_code $u)
    printf '  %-58s %s\n' (string replace $base '' $u) $c
    if test "$c" != 200
        set bad 1
    end
end

# --- 3. the content assertion ---------------------------------------------
# The part a status code cannot tell you: is this the NEW copy? Without a
# needle, a cached old page returns 200 and looks like a successful deploy.
if test -n "$needle"
    echo "== asserting content =="
    set -l found 0
    for i in (seq 1 10)
        if curl -s --max-time 20 "$base$path" | string match -q "*$needle*"
            echo "  found: \"$needle\""; set found 1; break
        end
        echo "  not yet serving the new copy, retrying..."
        sleep 12
    end
    if test $found -eq 0
        echo "  NEVER APPEARED — the run was green but the edge is still on the old copy"
        set bad 1
    end
end

if test $bad -eq 0
    echo "== deployed and serving =="
    exit 0
else
    echo "== FINDINGS above =="
    exit 1
end
