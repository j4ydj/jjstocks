# Push to GitHub

## Step 1: Create GitHub Repo

1. Go to https://github.com/new
2. **Repository name:** `trading-bot`
3. **Description:** `Cloud-deployed trading signal generator with Telegram alerts`
4. Select **Public** (Railway free tier requires public repos)
5. **DO NOT** check "Add a README file"
6. **DO NOT** check "Add .gitignore"
7. **DO NOT** check "Choose a license"
8. Click **"Create repository"**

## Step 2: Push Your Code

After creating the repo, you'll see a page with instructions.

Copy and run these commands in your terminal:

```bash
cd /Users/home/stocks
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git branch -M main
git push -u origin main
```

**Replace `YOUR_USERNAME` with your actual GitHub username!**

## Step 3: Verify

After pushing, go to:
`https://github.com/YOUR_USERNAME/trading-bot`

You should see all your files there.

## Step 4: Deploy to Railway

Now that it's on GitHub, go to https://railway.app and deploy from there.

---

## Alternative: GitHub Desktop

If you prefer GUI:

1. Download GitHub Desktop: https://desktop.github.com
2. Sign in with your GitHub account
3. Add local repository: `/Users/home/stocks`
4. Click "Publish repository"
5. Make it **Public**
6. Click "Publish"

Done!
