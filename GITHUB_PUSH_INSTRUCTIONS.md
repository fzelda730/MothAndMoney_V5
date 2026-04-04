# Moth and Money V4 — Pushing your next commits to GitHub

## Remote (already configured)

- **origin:** `https://github.com/fzelda730/MothandMoney_v4.git`
- **branch:** `main`

Check anytime:

```bash
cd "/path/to/MothAndMoney_V4"
git remote -v
git branch
```

## Everyday workflow (after you change files)

1. See what changed: `git status`
2. Stage files:
   - Everything: `git add .`
   - Or specific paths: `git add path/to/file`
3. Commit: `git commit -m "Short description of what you changed"`
4. Push: `git push`

Because `main` already tracks `origin/main`, you usually do **not** need `git push -u origin main` again—just `git push`.

## First-time setup on a new machine only

```bash
git clone https://github.com/fzelda730/MothandMoney_v4.git
cd MothandMoney_v4
```

## If `git push` fails with HTTP 400 / RPC failed

Your environment needed a larger HTTP buffer for HTTPS. Run once (global):

```bash
git config --global http.postBuffer 524288000
```

Optional (sometimes helps):

```bash
git config --global http.version HTTP/1.1
```

Then: `git push`

## HTTPS “password” = Personal Access Token

GitHub does not accept your normal login password for `git push` over HTTPS. When Git asks for a **password**, paste a **Personal Access Token** (classic) with **repo** scope:

**GitHub → Settings → Developer settings → Personal access tokens → Generate.**

## Before you push

- Do not commit secrets: `app/.env` must stay untracked (see `.gitignore`).

## Useful commands

| Command | Purpose |
|--------|---------|
| `git log -3 --oneline` | Last 3 commits |
| `git pull` | Bring down changes from GitHub (use before push if you work on multiple computers) |
