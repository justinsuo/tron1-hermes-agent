#!/usr/bin/env bash
# Sync local state → repo → GitHub. Invoked by launchd every 10 minutes.
#
# Idempotent: if nothing changed, no commit is made and git push is a no-op.

set -euo pipefail

REPO="/Users/justinsuo/tron1-hermes-agent"
LOG="/tmp/tron1-autopush.log"

exec >> "$LOG" 2>&1

echo ""
echo "================= $(date) ================="

cd "$REPO"

# Make sure we're on main (or whatever tracking branch)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
echo "[auto_push] branch: $BRANCH"

# 1. Sync files
bash "${REPO}/scripts/sync_to_repo.sh"

# 2. Skip if nothing changed
if git diff --quiet && git diff --cached --quiet; then
  # Check untracked too
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "[auto_push] no changes — skipping commit"
    exit 0
  fi
fi

# 3. Commit with a tidy message
CHANGES=$(git status --short | wc -l | tr -d ' ')
TOTAL=$(python3 -c "import json; d=json.load(open('${REPO}/status/stats.json')); print(d['total'])" 2>/dev/null || echo "?")
RATE=$(python3 -c "import json; d=json.load(open('${REPO}/status/stats.json')); print(int(d['recent_rate_pct']))" 2>/dev/null || echo "?")

git add -A
git commit -m "auto: sync · ${TOTAL} total episodes · ${RATE}% recent · ${CHANGES} files" \
  --quiet || true

echo "[auto_push] commit: $(git log -1 --oneline)"

# 4. Push
git push origin "$BRANCH" --quiet
echo "[auto_push] pushed OK"
