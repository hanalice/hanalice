# GitHub Pages (static site from `public/`)

`scripts/sync.py` exports a minimal static site to `public/` after updating README and tags.

## Enable Pages

1. Open the repo **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Branch: **main**, folder: **/public**.
4. Save. After the next push (or workflow run), the site is served at:

   **https://hanalice.github.io/hanalice/**

Asset and post links use base path `/hanalice`, so they work on project pages.

## Search Console

1. After the site is live, add the property in [Google Search Console](https://search.google.com/search-console).
2. Submit the sitemap URL:

   `https://hanalice.github.io/hanalice/sitemap.xml`

`public/robots.txt` already points crawlers at that sitemap.

## Local preview

```bash
pip install -r requirements.txt
make sync
# open public/index.html, or: python3 -m http.server -d public 8000
# then visit http://127.0.0.1:8000/ (note: BASE_PATH is /hanalice on GitHub)
```

## Follow-up: update `blog-sync.yml`

The PAT used to open this PR lacked the `workflow` scope, so `.github/workflows/blog-sync.yml` was **not** updated in the same push. After merge (or on this PR in the GitHub UI), replace that workflow so it:

1. `pip install -r requirements.txt` before `python scripts/sync.py`
2. `git add README.md tags/ public/ assets/mascots/`
3. Also triggers on `scripts/sync.py`, `requirements.txt`, `public/**`

Reference copy lives in the PR discussion / `docs` if needed; full file is in the Pages implementation notes from the agent.

Until that lands, the committed `public/` still serves Pages; regenerating after new posts requires a local `make sync` + push, or the updated Action.
