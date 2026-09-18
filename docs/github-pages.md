# GitHub Pages (static site from `public/`)

`scripts/sync.py` exports a minimal static site to `public/` after updating README and tags.
`public/` is generated locally and in CI; it is **not** committed (see `.gitignore`).
Deployment uses **GitHub Actions** (`.github/workflows/pages.yml`): the workflow runs `sync.py`, then uploads `public/` as a Pages artifact. Do not use “Deploy from a branch”.

> GitHub’s branch deploy folder picker only offers `/` (root) and `/docs` — **not** `/public`.

## Enable Pages (one-time, UI)

1. Open the repo **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Re-run workflow **Deploy GitHub Pages** (Actions tab → workflow → Run workflow), or push a change that rebuilds the site (`posts/`, `scripts/sync.py`, `assets/`).
4. Site: **https://hanalice.github.io/hanalice/**
5. Optional: submit `https://hanalice.github.io/hanalice/sitemap.xml` in [Google Search Console](https://search.google.com/search-console).

`public/robots.txt` already points crawlers at that sitemap.

## Local preview

```bash
pip install -r requirements.txt
make sync
# open public/index.html, or:
python3 -m http.server -d public 8000
```

Note: on GitHub the site is served under base path `/hanalice`.

## Visitor counts (repo + Pages)

Two different metrics:

| Surface | Metric | Source |
|---|---|---|
| GitHub README | Repo views + Site views | `data/traffic.json` (daily Action) |
| Pages footer | Site views only | GoatCounter live `TOTAL.json` |

**GoatCounter site code** is the subdomain prefix (`https://<code>.goatcounter.com`). Store it only as repository Actions variable `GOATCOUNTER_CODE` (Settings → Secrets and variables → Actions → Variables). Do not commit it. After setting the variable, re-run **Deploy GitHub Pages**.

One-time GitHub setup:

1. PAT that can read this repository’s traffic ([Traffic API](https://docs.github.com/en/rest/metrics/traffic): classic `repo` scope, or fine-grained **Administration: Read**).
2. Repo **Settings → Secrets and variables → Actions**: secret `TRAFFIC_PAT` (the PAT above).
3. Same page → Variables: `GOATCOUNTER_CODE`.
4. Push these workflow changes, then Actions → **Traffic rollup** → Run workflow, and **Deploy GitHub Pages** → Run workflow.

GoatCounter’s script ignores `localhost`, so `python3 -m http.server -d public` will not inflate production counts. Local `make sync` also skips the counter snippet unless `GOATCOUNTER_CODE` is in the environment.

## Follow-up workflow example

If you need a reference copy of the sync Action: `docs/blog-sync.yml.example`.
