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

1. Fine-grained PAT for this repo, stored as secret `TRAFFIC_PAT`. Permissions:
   - **Administration: Read** — Traffic API
   - **Contents: Write** — squash-merge onto `main`
   - **Pull requests: Write** — create and merge the snapshot PR  
   (`GITHUB_TOKEN` cannot create PRs unless the repo enables “Allow GitHub Actions to create and approve pull requests”, and it cannot bypass the `main` ruleset.)
2. Same page → Variables: `GOATCOUNTER_CODE`.
3. In GoatCounter: site settings → enable **Allow adding visitor counts on your website** (defaults to off; `/counter/TOTAL.json` returns 403 until this is on). See [visitor counter](https://www.goatcounter.com/help/visitor-counter).
4. Actions → **Traffic rollup** → Run workflow. It force-pushes `chore/traffic-rollup`, opens a PR, and squash-merges it. Then run **Deploy GitHub Pages** if the site footer script is not live yet.

`main` 要求走 PR。**Traffic rollup** 与 **Blog Sync** 都用 `TRAFFIC_PAT`（你的账号）开 PR 并 squash 合并，不依赖 Actions 那个「允许创建 PR」开关。若 PAT 仍只有 Administration: Read，开 PR / 合并会失败，请按上面补 Contents 与 Pull requests。

GoatCounter’s script ignores `localhost`, so `python3 -m http.server -d public` will not inflate production counts. Local `make sync` also skips the counter snippet unless `GOATCOUNTER_CODE` is in the environment.

## Follow-up workflow example

If you need a reference copy of the sync Action: `docs/blog-sync.yml.example`.
