"""Roll up GitHub repo traffic and GoatCounter site totals into data/traffic.json.

GitHub only retains 14 days of Insights. Daily counts are merged by date so
all-time *views* can accumulate. Unique visitors cannot be summed across days
without double-counting, so uniques_14d stays a rolling 14-day window.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

TRAFFIC_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'traffic.json')
API_VERSION = 'application/vnd.github+json'
USER_AGENT = 'hanalice-traffic-rollup'
CODE_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


def _utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _load_json(path, fallback):
    if not os.path.isfile(path):
        return json.loads(json.dumps(fallback))
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return json.loads(json.dumps(fallback))
    return data


def load_traffic(path=None):
    """Load persisted rollup; missing keys get empty defaults."""
    fallback = {
        'repo': {
            'total_count': 0,
            'count_14d': 0,
            'uniques_14d': 0,
            'days': {},
            'updated_at': None,
        },
        'site': {
            'count': 0,
            'count_unique': 0,
            'updated_at': None,
        },
    }
    data = _load_json(path or TRAFFIC_FILE, fallback)
    repo = data.get('repo') if isinstance(data.get('repo'), dict) else {}
    site = data.get('site') if isinstance(data.get('site'), dict) else {}
    days = repo.get('days') if isinstance(repo.get('days'), dict) else {}
    return {
        'repo': {
            'total_count': int(repo.get('total_count') or 0),
            'count_14d': int(repo.get('count_14d') or 0),
            'uniques_14d': int(repo.get('uniques_14d') or 0),
            'days': days,
            'updated_at': repo.get('updated_at'),
        },
        'site': {
            'count': int(site.get('count') or 0),
            'count_unique': int(site.get('count_unique') or 0),
            'updated_at': site.get('updated_at'),
        },
    }


def save_traffic(store, path=None):
    dest = path or TRAFFIC_FILE
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
        f.write('\n')


def goatcounter_code(environ=None):
    """Return GoatCounter site code from GOATCOUNTER_CODE (Actions variable)."""
    env = os.environ if environ is None else environ
    raw = (env.get('GOATCOUNTER_CODE') or '').strip()
    if not raw or not CODE_RE.match(raw):
        return ''
    return raw


def merge_repo_views(store, payload):
    """Merge a GitHub traffic/views payload into store by calendar day."""
    repo = store.setdefault('repo', {})
    days = repo.setdefault('days', {})
    for row in payload.get('views') or []:
        ts = str(row.get('timestamp') or '')[:10]
        if not ts:
            continue
        days[ts] = {
            'count': int(row.get('count') or 0),
            'uniques': int(row.get('uniques') or 0),
        }
    repo['days'] = days
    repo['total_count'] = sum(int(d.get('count') or 0) for d in days.values())
    repo['count_14d'] = int(payload.get('count') or 0)
    repo['uniques_14d'] = int(payload.get('uniques') or 0)
    repo['updated_at'] = _utc_now()
    return store


def parse_goatcounter_total(payload):
    """Parse GoatCounter /counter/TOTAL.json into ints."""

    def _as_int(value):
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        digits = re.sub(r'[^\d]', '', str(value))
        return int(digits) if digits else 0

    return {
        'count': _as_int(payload.get('count')),
        'count_unique': _as_int(payload.get('count_unique')),
    }


def _http_json(url, headers):
    req = urllib.request.Request(url, headers=headers, method='GET')
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=context) as resp:
        body = resp.read().decode('utf-8')
    return json.loads(body)


def fetch_github_views(repo, token):
    url = f'https://api.github.com/repos/{repo}/traffic/views'
    return _http_json(url, {
        'Accept': API_VERSION,
        'Authorization': f'Bearer {token}',
        'User-Agent': USER_AGENT,
        'X-GitHub-Api-Version': '2022-11-28',
    })


def fetch_goatcounter_total(code):
    url = f'https://{code}.goatcounter.com/counter/TOTAL.json'
    return _http_json(url, {'User-Agent': USER_AGENT, 'Accept': 'application/json'})


def run(environ=None, traffic_path=None):
    env = os.environ if environ is None else environ
    store = load_traffic(traffic_path)
    repo_name = (env.get('GITHUB_REPOSITORY') or 'hanalice/hanalice').strip()
    token = (env.get('TRAFFIC_PAT') or '').strip()
    errors = []

    if token:
        try:
            payload = fetch_github_views(repo_name, token)
            merge_repo_views(store, payload)
            print(
                f"Repo traffic: total_count={store['repo']['total_count']} "
                f"uniques_14d={store['repo']['uniques_14d']}"
            )
        except urllib.error.HTTPError as exc:
            errors.append(f'GitHub traffic API HTTP {exc.code}: {exc.reason}')
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f'GitHub traffic API failed: {exc}')
    else:
        print('TRAFFIC_PAT unset; skip GitHub repo traffic', file=sys.stderr)

    code = goatcounter_code(environ=env)
    if code:
        try:
            totals = parse_goatcounter_total(fetch_goatcounter_total(code))
            store['site']['count'] = totals['count']
            store['site']['count_unique'] = totals['count_unique']
            store['site']['updated_at'] = _utc_now()
            print(
                f"Site traffic: count={totals['count']} "
                f"count_unique={totals['count_unique']}"
            )
        except urllib.error.HTTPError as exc:
            errors.append(f'GoatCounter HTTP {exc.code}: {exc.reason}')
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f'GoatCounter failed: {exc}')
    else:
        print('GoatCounter code unset; skip site traffic', file=sys.stderr)

    save_traffic(store, traffic_path)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(run())
