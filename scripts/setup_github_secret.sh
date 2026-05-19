#!/usr/bin/env bash
# One-time: store CRON secret for GitHub Actions backup scheduler.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v gh >/dev/null; then
  echo "Install gh: brew install gh && gh auth login"
  exit 1
fi
if [[ ! -f .railway_cron_secret ]]; then
  echo "Missing .railway_cron_secret — copy CRON_SECRET from Railway Variables"
  exit 1
fi
gh secret set RAILWAY_CRON_SECRET < .railway_cron_secret --repo j4ydj/jjstocks
echo "Set RAILWAY_CRON_SECRET on j4ydj/jjstocks"
