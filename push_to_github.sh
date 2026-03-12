#!/bin/bash
# PUSH TO GITHUB
# ==============

set -e

echo "🚀 Push Trading Bot to GitHub"
echo "============================="
echo ""

# Get GitHub username
if [ -z "$1" ]; then
    echo "Usage: ./push_to_github.sh YOUR_GITHUB_USERNAME"
    echo ""
    echo "Your GitHub username is in your profile URL:"
    echo "  https://github.com/YOUR_USERNAME"
    echo ""
    echo "Example: ./push_to_github.sh johnsmith"
    exit 1
fi

USERNAME=$1
REPO_URL="https://github.com/$USERNAME/trading-bot"

echo "GitHub Username: $USERNAME"
echo "Repo URL will be: $REPO_URL"
echo ""

# Check if repo exists
echo "Checking if repo exists..."
if curl -s -o /dev/null -w "%{http_code}" "$REPO_URL" | grep -q "200"; then
    echo "✓ Repo exists on GitHub"
else
    echo "⚠ Repo not found on GitHub yet"
    echo ""
    echo "You need to create it first:"
    echo "1. Go to https://github.com/new"
    echo "2. Name: trading-bot"
    echo "3. Make it PUBLIC"
    echo "4. Click Create repository"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Add remote and push
echo ""
echo "Pushing code to GitHub..."
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git branch -M main
git push -u origin main

echo ""
echo "✅ SUCCESS!"
echo ""
echo "Your code is now at:"
echo "  $REPO_URL"
echo ""
echo "Next: Deploy to Railway"
echo "  1. Go to https://railway.app"
echo "  2. Sign up with GitHub"
echo "  3. New Project → Deploy from GitHub repo"
echo "  4. Select 'trading-bot'"
