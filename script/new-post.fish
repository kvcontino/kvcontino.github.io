#!/usr/bin/env fish
#
# Start a new post.  Usage:
#     script/new-post.fish "Why the Erie Canal Skipped the North Country"
#
# Creates _posts/YYYY-MM-DD-slug.markdown with front matter filled in, then
# opens it.  The filename date is what Jekyll uses to place the post, so it has
# to match the `date:` field — this script keeps them in step, which is the one
# thing that is annoying to fix later.

if test (count $argv) -eq 0
    echo "usage: script/new-post.fish \"Post Title\""
    exit 1
end

set title $argv[1]
set today (date +%Y-%m-%d)
set stamp (date "+%Y-%m-%d %H:%M:%S %z")

# Slug: lowercase, spaces and punctuation to hyphens, collapse and trim them.
#   tr -cs 'a-z0-9' '-'  = replace every run of NON-alphanumeric with one hyphen
#      │  │                 -c complement the set, -s squeeze repeats
set slug (echo $title | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//')

set repo (dirname (status --current-filename))/..
set file $repo/_posts/$today-$slug.markdown

if test -e $file
    echo "already exists: $file"
    exit 1
end

printf '%s\n' \
    '---' \
    "title:  \"$title\"" \
    "date:   $stamp" \
    'layout: default' \
    'categories: notes' \
    "description: \"\"   # one line; shows on /posts/ and in search results" \
    '---' \
    '' \
    '' > $file

echo "created $file"
echo
echo "Reminders:"
echo "  · fill in description: — it is the blurb on /posts/"
echo "  · categories: sets the URL (/notes/YYYY/MM/DD/slug.html)"
echo "  · add  draft: true  to publish the page but keep it out of /feed.xml and /posts/"
echo "  · proper name on first mention:  <span class=\"sc\">Name</span>"
echo "  · preview:  bundle exec jekyll serve --host 127.0.0.1 --port 4000 --livereload"

# Open in whatever is around, preferring the editor you actually compose in.
if type -q obsidian
    echo
    echo "opening in Obsidian…"
    obsidian "obsidian://open?path=$file" 2>/dev/null &
else if set -q EDITOR
    $EDITOR $file
end
