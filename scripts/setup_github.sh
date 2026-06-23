#!/usr/bin/env bash
# setup_github.sh — One-time setup: create GitHub repo, enable Pages, push code.
#
# Before running:
#   export GITHUB_USERNAME="your-username"
#   export GITHUB_TOKEN="your-personal-access-token"
#
# The token needs scopes: repo, workflow

set -euo pipefail

: "${GITHUB_USERNAME:?Set GITHUB_USERNAME env var first}"
: "${GITHUB_TOKEN:?Set GITHUB_TOKEN env var first}"

REPO="verse-of-the-day"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="https://api.github.com"

echo "▶  Creating GitHub repo: ${GITHUB_USERNAME}/${REPO}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API}/user/repos" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d "{
    \"name\": \"${REPO}\",
    \"description\": \"Daily Bible verse and devotional — published on GitHub Pages\",
    \"homepage\": \"https://${GITHUB_USERNAME}.github.io/${REPO}\",
    \"private\": false,
    \"auto_init\": false
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [[ "$HTTP_CODE" == "201" ]]; then
  echo "   ✓ Repository created"
elif [[ "$HTTP_CODE" == "422" ]]; then
  echo "   ⚠  Repository may already exist — continuing"
else
  echo "   ✗ Unexpected response (HTTP $HTTP_CODE): $BODY"
  exit 1
fi

# ── Git init & push ──────────────────────────────────────────────────────────
cd "$ROOT"

if [ ! -d ".git" ]; then
  echo "▶  Initialising git repository"
  git init
  git branch -M main
fi

# Set remote (replace if exists)
if git remote get-url origin &>/dev/null; then
  git remote set-url origin "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${REPO}.git"
else
  git remote add origin "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${REPO}.git"
fi

echo "▶  Staging all files"
git add -A
git commit -m "init: initial site structure and templates" 2>/dev/null || echo "   (nothing new to commit)"

echo "▶  Pushing to GitHub"
git push -u origin main
echo "   ✓ Pushed"

# ── Enable GitHub Pages ───────────────────────────────────────────────────────
echo "▶  Enabling GitHub Pages (branch: main, root: /)"
curl -s -o /dev/null -w "   HTTP %{http_code}\n" \
  -X POST "${API}/repos/${GITHUB_USERNAME}/${REPO}/pages" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d '{"source": {"branch": "main", "path": "/"}}'

# ── Add secrets for Actions ───────────────────────────────────────────────────
echo ""
echo "▶  Manual step required — add these two secrets in GitHub:"
echo "   https://github.com/${GITHUB_USERNAME}/${REPO}/settings/secrets/actions/new"
echo ""
echo "   Secret 1:  ANTHROPIC_API_KEY   →  your Anthropic API key"
echo "   Secret 2:  GH_TOKEN            →  your GitHub token (same one you used here)"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Site will be live at:"
echo "  https://${GITHUB_USERNAME}.github.io/${REPO}/"
echo ""
echo "  GitHub Actions (daily cron) at:"
echo "  https://github.com/${GITHUB_USERNAME}/${REPO}/actions"
echo "═══════════════════════════════════════════════════════════"
