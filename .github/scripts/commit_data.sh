#!/usr/bin/env bash
# Commit the current directory (a checkout of the data branch) and push it.
# Usage: commit_data.sh MESSAGE_FILE
#
# The hourly job is the only writer apart from the monthly squash, which shares its
# concurrency group. A push can still be refused when a run overlaps a manual one, so it
# rebases onto the data branch and retries.
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit"
  exit 0
fi
git commit -q -F "$1"

for attempt in 1 2 3; do
  if git push -q origin HEAD:data; then
    exit 0
  fi
  echo "Push rejected (attempt $attempt); rebasing onto the latest data branch"
  git pull -q --rebase origin data
done
echo "Push to data failed after 3 attempts" >&2
exit 1
