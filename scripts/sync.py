import html
import os
import random
import re
import shutil
import sys
from datetime import datetime
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

POSTS_DIR = './posts'
TAGS_DIR = './tags'
README_TEMPLATE = './README.template.md'
README_OUTPUT = './README.md'
MASCOTS_DIR = './assets/mascots'
ASSETS_DIR = './assets'
PUBLIC_DIR = './public'
SITE_BASE = 'https://hanalice.github.io/hanalice'
BASE_PATH = '/hanalice'
SITE_TITLE = 'hanalice'
SITE_DESCRIPTION = 'Notes and posts by hanalice'
TOP_TAG_FILTERS = 12  # homepage filter chips: top N tags by post count
MAX_CARD_TAGS = 3  # index cards: show at most N chips, then +N


def parse_post(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    meta = {}
    lines = content.split('\n')
    body = content
    if lines and lines[0].strip() == '---':
        try:
            end = lines[1:].index('---') + 1
        except ValueError:
            print(f"Warning: unclosed frontmatter in {file_path}, skipping.")
            return None
        for line in lines[1:end]:
            if ':' in line:
                key, val = line.split(':', 1)
                meta[key.strip().lower()] = val.strip()
        body = '\n'.join(lines[end + 1 :])

    if 'title' not in meta:
        print(f"Warning: missing 'title' in {file_path}, skipping.")
        return None
    if 'date' not in meta:
        print(f"Warning: missing 'date' in {file_path}, skipping.")
        return None

    description = meta.get('description', '').strip()
    if not description:
        description = _first_paragraph_excerpt(body)

    basename = os.path.splitext(os.path.basename(file_path))[0]

    return {
        'title': meta['title'],
        'date': meta['date'],
        'tags': [t.strip() for t in meta.get('tags', '').split(',') if t.strip()],
        'path': file_path,
        'description': description,
        'body': body,
        'basename': basename,
    }


def _first_paragraph_excerpt(body, limit=160):
    """Take the first non-empty paragraph of prose (skip headings/code fences)."""
    text = body.strip()
    if not text:
        return SITE_DESCRIPTION
    # Drop fenced code blocks so we don't excerpt code.
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    paragraphs = re.split(r'\n\s*\n', text)
    for para in paragraphs:
        raw = para.strip()
        if not raw:
            continue
        # Skip ATX heading lines and hr markers; keep remaining prose in the block.
        lines = []
        for ln in raw.split('\n'):
            s = ln.strip()
            if not s:
                continue
            if re.match(r'^#+\s+', s):
                continue
            if re.match(r'^---+$', s) or re.match(r'^\*\*\*+$', s):
                continue
            lines.append(s)
        if not lines:
            continue
        cleaned = ' '.join(lines)
        cleaned = re.sub(r'[*_`>#\[\]\(\)!]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned and not cleaned.startswith('|'):
            if len(cleaned) > limit:
                return cleaned[: limit - 1].rstrip() + '…'
            return cleaned
    return SITE_DESCRIPTION



def generate_tag_pages(all_tags, posts):
    if not all_tags:
        print("No tags found; skipping tag page generation to preserve existing files.")
        return

    if not os.path.exists(TAGS_DIR):
        os.makedirs(TAGS_DIR)

    for f in os.listdir(TAGS_DIR):
        if f.endswith('.md'):
            os.remove(os.path.join(TAGS_DIR, f))

    for tag, count in all_tags.items():
        tag_posts = [p for p in posts if tag in p['tags']]
        tag_posts.sort(key=lambda x: x['date'], reverse=True)

        content = f"# Posts Tagged With: #{tag}\n\n"
        content += f"Total: {count} posts\n\n"
        content += "---\n\n"
        for p in tag_posts:
            rel_path = '../' + p['path'].removeprefix('./')
            content += f"- [{p['date']}] [{p['title']}]({rel_path})\n"

        content += "\n---\n[← Back to Home](../README.md)"

        tag_file = os.path.join(TAGS_DIR, f"{tag}.md")
        with open(tag_file, 'w', encoding='utf-8') as f:
            f.write(content)
    print(f"Generated {len(all_tags)} tag pages in {TAGS_DIR}")


def _inject_section(content, start_marker, end_marker, body):
    before, rest = content.split(start_marker, 1)
    _, after = rest.split(end_marker, 1)
    return before + start_marker + '\n' + body + '\n' + end_marker + after


def update_readme(posts, all_tags, daily_mascot=None):
    if not os.path.exists(README_TEMPLATE):
        sys.exit(f"Error: {README_TEMPLATE} not found.")

    with open(README_TEMPLATE, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    if posts:
        post_list_str = '\n'.join(
            [f"- [{p['date']}] [{p['title']}]({p['path']})" for p in posts[:10]]
        )
    else:
        post_list_str = "*暂时没有发布的博文，请在 /posts 目录下添加 Markdown 文件后自动同步。*"

    readme_content = _inject_section(
        readme_content,
        '<!-- BLOG-POST-LIST:START -->',
        '<!-- BLOG-POST-LIST:END -->',
        post_list_str,
    )

    if all_tags:
        tag_cloud_str = ' '.join(
            [f"[`#{tag}({count})`](./tags/{tag}.md)" for tag, count in sorted(all_tags.items())]
        )
    else:
        tag_cloud_str = "*暂无分类*"

    readme_content = _inject_section(
        readme_content,
        '<!-- TAG-CLOUD:START -->',
        '<!-- TAG-CLOUD:END -->',
        tag_cloud_str,
    )

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    readme_content = readme_content.replace('{{LAST_SYNC}}', now_str)

    fallback_mascot = os.path.join(MASCOTS_DIR, 'default_mascot.png')
    readme_content = readme_content.replace('{{DAILY_MASCOT}}', daily_mascot or fallback_mascot)

    with open(README_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"Successfully updated {README_OUTPUT}")


def rotate_mascot():
    if not os.path.exists(MASCOTS_DIR):
        print("Mascots directory not found.")
        return None

    mascots = [
        f for f in os.listdir(MASCOTS_DIR)
        if f.endswith(('.gif', '.png', '.jpg', '.webp'))
        and not f.startswith('daily.')
        and f != 'default_mascot.png'
    ]
    if not mascots:
        print("No mascots found in directory.")
        return None

    chosen = random.choice(mascots)
    ext = os.path.splitext(chosen)[1]
    daily_name = 'daily' + ext
    dst = os.path.join(MASCOTS_DIR, daily_name)

    for f in os.listdir(MASCOTS_DIR):
        if f.startswith('daily.') and f != daily_name:
            os.remove(os.path.join(MASCOTS_DIR, f))

    shutil.copy(os.path.join(MASCOTS_DIR, chosen), dst)
    print(f"Updated mascot to: {chosen}")
    return dst


# ── GitHub Pages static export ───────────────────────────────────────────────


def _markdown_to_html(text):
    try:
        import markdown
    except ImportError:
        return '<pre>' + html.escape(text) + '</pre>'

    extensions = []
    for ext in ('fenced_code', 'tables'):
        try:
            markdown.markdown('x', extensions=[ext])
            extensions.append(ext)
        except Exception:
            pass
    return markdown.markdown(text, extensions=extensions)


def _site_url(path=''):
    """Absolute site URL for path under the project (no leading slash needed)."""
    path = path.lstrip('/')
    if not path:
        return SITE_BASE + '/'
    return SITE_BASE.rstrip('/') + '/' + path


def _href(path):
    """Root-relative URL under BASE_PATH."""
    path = path.lstrip('/')
    if not path:
        return BASE_PATH + '/'
    return BASE_PATH.rstrip('/') + '/' + path


def _rewrite_relative_urls(fragment):
    """Prefix relative src/href so assets work under /hanalice/."""

    def repl(match):
        attr = match.group(1)
        quote = match.group(2)
        url = match.group(3)
        if not url or url.startswith(
            ('http://', 'https://', '//', '#', 'mailto:', 'data:', 'javascript:')
        ):
            return match.group(0)
        # Absolute-from-root paths: /assets/foo → /hanalice/assets/foo
        if url.startswith('/'):
            if url.startswith(BASE_PATH + '/') or url == BASE_PATH:
                return match.group(0)
            return f'{attr}={quote}{BASE_PATH}{url}{quote}'
        # Relative: resolve against site root (posts live under public/posts/)
        # ../assets/x → assets/x; ./foo → foo; assets/x stays
        cleaned = url
        while cleaned.startswith('../'):
            cleaned = cleaned[3:]
        if cleaned.startswith('./'):
            cleaned = cleaned[2:]
        return f'{attr}={quote}{_href(cleaned)}{quote}'

    return re.sub(
        r'''\b(src|href)=(["'])([^"']+)\2''',
        repl,
        fragment,
        flags=re.IGNORECASE,
    )


def _rewrite_post_md_links_in_markdown(text):
    """Rewrite markdown links to posts/*.md → .html before HTML conversion."""

    def repl(match):
        url = match.group(1)
        m = re.match(r'^([^?#]*)(.*)$', url)
        path, rest = m.group(1), m.group(2)
        if re.search(r'(?:^|/)posts/[^/]+\.md$', path, flags=re.IGNORECASE):
            path = re.sub(r'\.md$', '.html', path, flags=re.IGNORECASE)
            return f']({path}{rest})'
        return match.group(0)

    return re.sub(r'\]\(([^)]+)\)', repl, text)


def _rewrite_post_md_links(fragment):
    """Rewrite hrefs that point at posts/*.md to .html for GitHub Pages."""

    def repl(match):
        attr = match.group(1)
        quote = match.group(2)
        url = match.group(3)
        if not url:
            return match.group(0)
        m = re.match(r'^([^?#]*)(.*)$', url)
        path, rest = m.group(1), m.group(2)
        # posts/foo.md, ./posts/foo.md, ../posts/foo.md, /posts/foo.md, /hanalice/posts/foo.md
        if re.search(r'(?:^|/)posts/[^/]+\.md$', path, flags=re.IGNORECASE):
            path = re.sub(r'\.md$', '.html', path, flags=re.IGNORECASE)
            return f'{attr}={quote}{path}{rest}{quote}'
        return match.group(0)

    return re.sub(
        r'''\b(href)=(["'])([^"']+)\2''',
        repl,
        fragment,
        flags=re.IGNORECASE,
    )


def _tag_filename(tag):
    """Filesystem name for a tag page; matches tags/<Tag>.md naming."""
    return f'{tag}.html'


def _tag_href(tag):
    """Root-relative href for a tag page (URL-encode the tag segment)."""
    return _href(f'tags/{quote(tag, safe="-_.")}.html')


def _nav_html(active=None):
    home = html.escape(_href(''))
    posts = html.escape(_href(''))
    tags = html.escape(_href('tags/'))
    github = 'https://github.com/hanalice/hanalice'

    def cls(name):
        return ' class="active"' if active == name else ''

    return (
        '<header class="site-header">\n'
        '  <nav class="site-nav" aria-label="Primary">\n'
        f'    <a class="site-title" href="{home}">{html.escape(SITE_TITLE)}</a>\n'
        '    <ul class="nav-links">\n'
        f'      <li><a href="{posts}"{cls("posts")}>Posts</a></li>\n'
        f'      <li><a href="{tags}"{cls("tags")}>Tags</a></li>\n'
        f'      <li><a href="{github}" rel="noopener noreferrer" target="_blank">GitHub</a></li>\n'
        '    </ul>\n'
        '  </nav>\n'
        '</header>'
    )


def _page_shell(
    title,
    description,
    canonical,
    body_html,
    extra_head='',
    og_type='website',
    active=None,
    extra_body_end='',
):
    esc_title = html.escape(title)
    esc_desc = html.escape(description)
    esc_canon = html.escape(canonical)
    og_type = html.escape(og_type)
    css_href = html.escape(_href('assets/site.css'))
    home_href = html.escape(_href(''))
    tags_href = html.escape(_href('tags/'))
    parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{esc_title}</title>',
        f'<meta name="description" content="{esc_desc}">',
        f'<link rel="canonical" href="{esc_canon}">',
        f'<meta property="og:title" content="{esc_title}">',
        f'<meta property="og:description" content="{esc_desc}">',
        f'<meta property="og:url" content="{esc_canon}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:site_name" content="{html.escape(SITE_TITLE)}">',
        f'<link rel="stylesheet" href="{css_href}">',
        extra_head,
        '</head>',
        '<body>',
        _nav_html(active=active),
        '<main class="site-main">',
        body_html,
        '</main>',
        '<footer class="site-footer">',
        f'  <p><a href="{home_href}">Home</a> &middot; <a href="{tags_href}">Tags</a> &middot; <a href="https://github.com/hanalice/hanalice">GitHub</a></p>',
        '</footer>',
        extra_body_end,
        '</body>',
        '</html>',
        '',
    ]
    return '\n'.join(parts)


_SITE_CSS = '/* Apple-inspired theme for GitHub Pages */\n:root {\n  --bg: #f5f5f7;\n  --fg: #1d1d1f;\n  --muted: #86868b;\n  --border: rgba(0, 0, 0, 0.08);\n  --link: #0066cc;\n  --link-hover: #0077ed;\n  --code-bg: #e8e8ed;\n  --chip-bg: #e8e8ed;\n  --chip-active: #1d1d1f;\n  --chip-active-fg: #f5f5f7;\n  --card: #ffffff;\n  --max: 980px;\n  --measure: 65ch;\n  --radius: 12px;\n  --radius-sm: 9800px;\n}\n* { box-sizing: border-box; }\nhtml { -webkit-text-size-adjust: 100%; }\nbody {\n  margin: 0;\n  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;\n  font-size: 17px;\n  line-height: 1.47059;\n  letter-spacing: -0.022em;\n  color: var(--fg);\n  background: var(--bg);\n  min-height: 100vh;\n}\na {\n  color: var(--link);\n  text-decoration: none;\n}\na:hover { color: var(--link-hover); text-decoration: underline; }\n.site-header {\n  position: sticky;\n  top: 0;\n  z-index: 50;\n  backdrop-filter: saturate(180%) blur(20px);\n  -webkit-backdrop-filter: saturate(180%) blur(20px);\n  background: rgba(245, 245, 247, 0.72);\n  border-bottom: 1px solid var(--border);\n}\n.site-nav {\n  max-width: var(--max);\n  margin: 0 auto;\n  padding: 0.85rem 1.5rem;\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  gap: 1rem;\n}\n.site-title {\n  font-weight: 600;\n  font-size: 1.05rem;\n  letter-spacing: -0.03em;\n  color: var(--fg);\n  text-decoration: none;\n}\n.site-title:hover { color: var(--fg); text-decoration: none; opacity: 0.8; }\n.nav-links {\n  list-style: none;\n  margin: 0;\n  padding: 0;\n  display: flex;\n  align-items: center;\n  gap: 1.25rem;\n  font-size: 0.9rem;\n}\n.nav-links a {\n  color: var(--muted);\n  text-decoration: none;\n  font-weight: 400;\n}\n.nav-links a:hover,\n.nav-links a.active {\n  color: var(--fg);\n  text-decoration: none;\n}\n.site-main {\n  max-width: var(--max);\n  margin: 0 auto;\n  padding: 2.5rem 1.5rem 3.5rem;\n}\n.site-footer {\n  max-width: var(--max);\n  margin: 0 auto;\n  padding: 1.5rem 1.5rem 2.5rem;\n  border-top: 1px solid var(--border);\n  color: var(--muted);\n  font-size: 0.85rem;\n}\n.site-footer a { color: var(--muted); }\n.site-footer a:hover { color: var(--fg); }\n.page-title {\n  margin: 0 0 0.35rem;\n  font-size: clamp(2rem, 4.5vw, 2.75rem);\n  font-weight: 700;\n  letter-spacing: -0.045em;\n  line-height: 1.1;\n}\n.page-sub {\n  margin: 0 0 2rem;\n  color: var(--muted);\n  font-size: 1.05rem;\n}\n.tag-filters {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 0.5rem;\n  margin: 0 0 1.75rem;\n  padding: 0 0 1.5rem;\n  border-bottom: 1px solid var(--border);\n}\n.tag-chip {\n  display: inline-flex;\n  align-items: center;\n  gap: 0.25rem;\n  padding: 0.35rem 0.85rem;\n  border-radius: var(--radius-sm);\n  border: none;\n  background: var(--chip-bg);\n  color: var(--fg);\n  font: inherit;\n  font-size: 0.8rem;\n  font-weight: 500;\n  letter-spacing: -0.01em;\n  cursor: pointer;\n  text-decoration: none;\n  transition: background 0.15s ease, color 0.15s ease;\n}\na.tag-chip:hover { text-decoration: none; color: var(--fg); background: #dcdce0; }\nbutton.tag-chip:hover { background: #dcdce0; }\n.tag-chip.active,\n.tag-chip[aria-pressed="true"] {\n  background: var(--chip-active);\n  color: var(--chip-active-fg);\n}\n.tag-chip .count {\n  color: inherit;\n  opacity: 0.65;\n  font-variant-numeric: tabular-nums;\n}\n.post-list {\n  list-style: none;\n  padding: 0;\n  margin: 0;\n  display: flex;\n  flex-direction: column;\n  gap: 0.75rem;\n}\n.post-list > li {\n  background: var(--card);\n  border: 1px solid var(--border);\n  border-radius: var(--radius);\n  padding: 1.1rem 1.25rem;\n  transition: box-shadow 0.15s ease, border-color 0.15s ease;\n}\n.post-list > li:hover {\n  border-color: rgba(0, 0, 0, 0.12);\n  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);\n}\n.post-list > li.hidden { display: none; }\n.post-row {\n  display: flex;\n  flex-wrap: wrap;\n  align-items: baseline;\n  gap: 0.35rem 0.85rem;\n}\n.post-list .date {\n  color: var(--muted);\n  font-size: 0.85rem;\n  font-variant-numeric: tabular-nums;\n  min-width: 6.5rem;\n}\n.post-list .post-title {\n  flex: 1 1 12rem;\n  font-weight: 600;\n  font-size: 1.05rem;\n  letter-spacing: -0.02em;\n  color: var(--fg);\n  text-decoration: none;\n}\n.post-list .post-title:hover { color: var(--link); text-decoration: none; }\n.post-list .post-tags {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 0.35rem;\n  width: 100%;\n  margin-top: 0.55rem;\n}\n.post-list .post-tags .tag-chip {\n  font-size: 0.72rem;\n  padding: 0.22rem 0.65rem;\n}\n.post-list .post-tags .tag-more {\n  font-size: 0.72rem;\n  color: var(--muted);\n  padding: 0.22rem 0.35rem;\n  text-decoration: none;\n  align-self: center;\n}\na.tag-more:hover { color: var(--fg); text-decoration: none; }\na.tag-chip-more { font-weight: 600; }\n.empty-filter {\n  display: none;\n  color: var(--muted);\n  padding: 1.5rem 0;\n}\n.empty-filter.visible { display: block; }\narticle {\n  max-width: var(--measure);\n}\narticle h1.page-title,\narticle > h1 {\n  margin-top: 0;\n  font-size: clamp(1.75rem, 3.5vw, 2.35rem);\n  font-weight: 700;\n  letter-spacing: -0.04em;\n  line-height: 1.15;\n}\n.post-meta {\n  color: var(--muted);\n  font-size: 0.95rem;\n  margin: 0.5rem 0 1.75rem;\n  display: flex;\n  flex-wrap: wrap;\n  align-items: center;\n  gap: 0.5rem 0.75rem;\n}\n.post-meta .tags,\n.tags {\n  list-style: none;\n  margin: 0;\n  padding: 0;\n  display: flex;\n  flex-wrap: wrap;\n  gap: 0.35rem;\n}\n.tags li { display: inline; }\n.prose {\n  max-width: var(--measure);\n  line-height: 1.65;\n}\n.prose h2, .prose h3 {\n  letter-spacing: -0.03em;\n  margin-top: 2rem;\n}\n.prose p { margin: 0.9rem 0; }\npre, code {\n  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;\n  font-size: 0.88em;\n}\ncode {\n  background: var(--code-bg);\n  padding: 0.12em 0.4em;\n  border-radius: 6px;\n}\npre {\n  background: var(--code-bg);\n  padding: 1.1rem 1.2rem;\n  overflow-x: auto;\n  border-radius: 10px;\n  border: 1px solid var(--border);\n}\npre code { background: none; padding: 0; }\ntable { border-collapse: collapse; width: 100%; margin: 1rem 0; }\nth, td { border: 1px solid var(--border); padding: 0.45rem 0.65rem; text-align: left; }\nimg { max-width: 100%; height: auto; border-radius: 8px; }\n.back { margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }\n.tag-cloud {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 0.55rem;\n  margin: 0;\n  padding: 0;\n  list-style: none;\n}\n'


def _write_site_css():
    css_dir = os.path.join(PUBLIC_DIR, 'assets')
    os.makedirs(css_dir, exist_ok=True)
    path = os.path.join(css_dir, 'site.css')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(_SITE_CSS)
    return path


def _copy_assets():
    """Copy repo assets/ into public/assets/ (merge; keep site.css)."""
    if not os.path.isdir(ASSETS_DIR):
        return
    dest = os.path.join(PUBLIC_DIR, 'assets')
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(ASSETS_DIR):
        src = os.path.join(ASSETS_DIR, name)
        dst = os.path.join(dest, name)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
    print(f"Copied {ASSETS_DIR} → {dest}")


def _post_tag_chips_html(tags, max_visible=None, overflow_href=None):
    """Render tag chips; optionally cap visible chips and show +N overflow."""
    tags = list(tags)
    visible = tags if max_visible is None else tags[:max_visible]
    parts = []
    for t in visible:
        label = html.escape(t)
        href = html.escape(_tag_href(t))
        parts.append(f'<a class="tag-chip" href="{href}" data-tag="{label}">#{label}</a>')
    if max_visible is not None and len(tags) > max_visible:
        n = len(tags) - max_visible
        label = f'+{n}'
        if overflow_href:
            oh = html.escape(overflow_href)
            parts.append(f'<a class="tag-more" href="{oh}">{label}</a>')
        else:
            parts.append(f'<span class="tag-more">{label}</span>')
    return ''.join(parts)



_FILTER_SCRIPT = "<script>\n(function () {\n  var chips = document.querySelectorAll('.tag-filters [data-filter]');\n  var items = document.querySelectorAll('.post-list > li[data-tags]');\n  var empty = document.getElementById('filter-empty');\n  function setFilter(tag) {\n    var shown = 0;\n    items.forEach(function (li) {\n      var tags = (li.getAttribute('data-tags') || '').split(/\\s+/).filter(Boolean);\n      var match = !tag || tag === 'all' || tags.indexOf(tag) !== -1;\n      li.classList.toggle('hidden', !match);\n      if (match) shown++;\n    });\n    chips.forEach(function (c) {\n      var active = c.getAttribute('data-filter') === (tag || 'all');\n      c.classList.toggle('active', active);\n      c.setAttribute('aria-pressed', active ? 'true' : 'false');\n    });\n    if (empty) empty.classList.toggle('visible', shown === 0);\n  }\n  chips.forEach(function (chip) {\n    chip.addEventListener('click', function () {\n      setFilter(chip.getAttribute('data-filter') || 'all');\n    });\n  });\n})();\n</script>"


def _filter_script():
    return _FILTER_SCRIPT


def _render_index(posts, all_tags):
    filter_chips = [
        '<button type="button" class="tag-chip active" data-filter="all" aria-pressed="true">All</button>'
    ]
    # Top N by post count (name as tiebreaker); remaining tags live on /tags/
    top_tags = sorted(
        all_tags.items(), key=lambda x: (-x[1], x[0].lower())
    )[:TOP_TAG_FILTERS]
    for tag, count in top_tags:
        esc = html.escape(tag)
        filter_chips.append(
            f'<button type="button" class="tag-chip" data-filter="{esc}" aria-pressed="false">'
            f'{esc} <span class="count">({count})</span></button>'
        )
    more_href = html.escape(_href('tags/'))
    filter_chips.append(
        f'<a class="tag-chip tag-chip-more" href="{more_href}">更多</a>'
    )
    filters = (
        '<div class="tag-filters" role="group" aria-label="Filter by tag">\n'
        + '\n'.join(filter_chips)
        + '\n</div>'
    )

    items = []
    for p in posts:
        href = html.escape(_href(f"posts/{p['basename']}.html"))
        title = html.escape(p['title'])
        date = html.escape(p['date'])
        data_tags = html.escape(' '.join(p['tags']))
        chips = _post_tag_chips_html(
            p['tags'],
            max_visible=MAX_CARD_TAGS,
            overflow_href=_href(f"posts/{p['basename']}.html"),
        )
        tags_row = f'<div class="post-tags">{chips}</div>' if chips else ''
        items.append(
            f'<li data-tags="{data_tags}">'
            f'<div class="post-row">'
            f'<span class="date">{date}</span>'
            f'<a class="post-title" href="{href}">{title}</a>'
            f'{tags_row}'
            f'</div></li>'
        )
    if items:
        listing = (
            '<ul class="post-list">\n'
            + '\n'.join(items)
            + '\n</ul>\n'
            '<p id="filter-empty" class="empty-filter">No posts match this tag.</p>'
        )
    else:
        listing = '<p>No posts yet.</p>'
    body = (
        f'<h1 class="page-title">Posts</h1>\n'
        f'<p class="page-sub">{html.escape(SITE_DESCRIPTION)}</p>\n'
        f'{filters}\n{listing}'
    )
    return _page_shell(
        title=SITE_TITLE,
        description=SITE_DESCRIPTION,
        canonical=_site_url(''),
        body_html=body,
        active='posts',
        extra_body_end=_filter_script() if items else '',
    )



def _render_post(post):
    body = _rewrite_post_md_links_in_markdown(post['body'])
    content_html = _rewrite_post_md_links(
        _rewrite_relative_urls(_markdown_to_html(body))
    )
    tags_html = ''
    if post['tags']:
        tags_html = f'<div class="tags">{_post_tag_chips_html(post["tags"])}</div>'
    body = (
        f'<article>\n'
        f'<h1 class="page-title">{html.escape(post["title"])}</h1>\n'
        f'<div class="post-meta"><time datetime="{html.escape(post["date"])}">'
        f'{html.escape(post["date"])}</time>{tags_html}</div>\n'
        f'<div class="prose">\n{content_html}\n</div>\n'
        f'<p class="back"><a href="{html.escape(_href(""))}">&larr; Back to posts</a></p>\n'
        f'</article>'
    )
    return _page_shell(
        title=f'{post["title"]} · {SITE_TITLE}',
        description=post['description'] or SITE_DESCRIPTION,
        canonical=_site_url(f'posts/{post["basename"]}.html'),
        body_html=body,
        og_type='article',
        active='posts',
    )


def _render_tags_index(all_tags):
    items = []
    for tag, count in sorted(all_tags.items(), key=lambda x: x[0].lower()):
        href = html.escape(_tag_href(tag))
        esc = html.escape(tag)
        items.append(
            f'<li><a class="tag-chip" href="{href}">#{esc} '
            f'<span class="count">({count})</span></a></li>'
        )
    if items:
        cloud = '<ul class="tag-cloud">\n' + '\n'.join(items) + '\n</ul>'
    else:
        cloud = '<p>No tags yet.</p>'
    body = (
        f'<h1 class="page-title">Tags</h1>\n'
        f'<p class="page-sub">Browse posts by category</p>\n'
        f'{cloud}'
    )
    return _page_shell(
        title=f'Tags · {SITE_TITLE}',
        description=f'Tag index — {SITE_DESCRIPTION}',
        canonical=_site_url('tags/'),
        body_html=body,
        active='tags',
    )


def _render_tag_page(tag, posts_for_tag, count):
    items = []
    for p in posts_for_tag:
        href = html.escape(_href(f"posts/{p['basename']}.html"))
        title = html.escape(p['title'])
        date = html.escape(p['date'])
        chips = _post_tag_chips_html(p['tags'])
        tags_row = f'<div class="post-tags">{chips}</div>' if chips else ''
        items.append(
            f'<li>'
            f'<div class="post-row">'
            f'<span class="date">{date}</span>'
            f'<a class="post-title" href="{href}">{title}</a>'
            f'{tags_row}'
            f'</div></li>'
        )
    listing = (
        '<ul class="post-list">\n' + '\n'.join(items) + '\n</ul>'
        if items
        else '<p>No posts.</p>'
    )
    esc_tag = html.escape(tag)
    plural = 's' if count != 1 else ''
    body = (
        f'<h1 class="page-title">#{esc_tag}</h1>\n'
        f'<p class="page-sub">{count} post{plural} &middot; '
        f'<a href="{html.escape(_href("tags/"))}">All tags</a></p>\n'
        f'{listing}'
    )
    return _page_shell(
        title=f'#{tag} · {SITE_TITLE}',
        description=f'Posts tagged #{tag}',
        canonical=_site_url(f'tags/{quote(tag, safe="-_.")}.html'),
        body_html=body,
        active='tags',
    )


def _write_sitemap(posts, all_tags):
    urls = [_site_url(''), _site_url('tags/')]
    for p in posts:
        urls.append(_site_url(f'posts/{p["basename"]}.html'))
    for tag in sorted(all_tags.keys()):
        urls.append(_site_url(f'tags/{quote(tag, safe="-_.")}.html'))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        lines.append('  <url>')
        lines.append(f'    <loc>{xml_escape(u)}</loc>')
        lines.append('  </url>')
    lines.append('</urlset>')
    lines.append('')
    path = os.path.join(PUBLIC_DIR, 'sitemap.xml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path


def _write_robots():
    sitemap = _site_url('sitemap.xml')
    content = (
        'User-agent: *\n'
        'Allow: /\n'
        '\n'
        f'Sitemap: {sitemap}\n'
    )
    path = os.path.join(PUBLIC_DIR, 'robots.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def export_static_site(posts, all_tags=None):
    """Build a minimal static site under public/ for GitHub Pages."""
    if all_tags is None:
        all_tags = {}
        for p in posts:
            for tag in p['tags']:
                all_tags[tag] = all_tags.get(tag, 0) + 1

    if os.path.isdir(PUBLIC_DIR):
        shutil.rmtree(PUBLIC_DIR)
    os.makedirs(os.path.join(PUBLIC_DIR, 'posts'), exist_ok=True)
    os.makedirs(os.path.join(PUBLIC_DIR, 'tags'), exist_ok=True)

    _write_site_css()
    _copy_assets()

    index_path = os.path.join(PUBLIC_DIR, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(_render_index(posts, all_tags))

    for p in posts:
        out = os.path.join(PUBLIC_DIR, 'posts', f"{p['basename']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(_render_post(p))

    tags_index = os.path.join(PUBLIC_DIR, 'tags', 'index.html')
    with open(tags_index, 'w', encoding='utf-8') as f:
        f.write(_render_tags_index(all_tags))

    for tag, count in all_tags.items():
        tag_posts = [p for p in posts if tag in p['tags']]
        tag_posts.sort(key=lambda x: x['date'], reverse=True)
        out = os.path.join(PUBLIC_DIR, 'tags', _tag_filename(tag))
        with open(out, 'w', encoding='utf-8') as f:
            f.write(_render_tag_page(tag, tag_posts, count))

    _write_sitemap(posts, all_tags)
    _write_robots()
    print(
        f"Exported static site to {PUBLIC_DIR}/ "
        f"({len(posts)} posts, {len(all_tags)} tags)"
    )


if __name__ == '__main__':
    all_posts = []
    if os.path.exists(POSTS_DIR):
        for f in os.listdir(POSTS_DIR):
            if f.endswith('.md'):
                post = parse_post(os.path.join(POSTS_DIR, f))
                if post is not None:
                    all_posts.append(post)

    all_posts.sort(key=lambda x: x['date'], reverse=True)

    all_tags = {}
    for p in all_posts:
        for tag in p['tags']:
            all_tags[tag] = all_tags.get(tag, 0) + 1

    generate_tag_pages(all_tags, all_posts)
    daily_mascot = rotate_mascot()
    update_readme(all_posts, all_tags, daily_mascot)
    export_static_site(all_posts, all_tags)
