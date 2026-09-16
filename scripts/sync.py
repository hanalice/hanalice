import html
import os
import random
import re
import shutil
import sys
from datetime import datetime
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
        cleaned = re.sub(r'^#+\s*', '', para.strip())
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


def _page_shell(title, description, canonical, body_html, extra_head='', og_type='website'):
    esc_title = html.escape(title)
    esc_desc = html.escape(description)
    esc_canon = html.escape(canonical)
    og_type = html.escape(og_type)
    css_href = html.escape(_href('assets/site.css'))
    home_href = html.escape(_href(''))
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc_title}</title>
<meta name="description" content="{esc_desc}">
<link rel="canonical" href="{esc_canon}">
<meta property="og:title" content="{esc_title}">
<meta property="og:description" content="{esc_desc}">
<meta property="og:url" content="{esc_canon}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{html.escape(SITE_TITLE)}">
<link rel="stylesheet" href="{css_href}">
{extra_head}
</head>
<body>
<header class="site-header">
  <a class="site-title" href="{home_href}">{html.escape(SITE_TITLE)}</a>
</header>
<main class="site-main">
{body_html}
</main>
<footer class="site-footer">
  <p><a href="{home_href}">Home</a> · <a href="https://github.com/hanalice/hanalice">GitHub</a></p>
</footer>
</body>
</html>
'''


def _write_site_css():
    css_dir = os.path.join(PUBLIC_DIR, 'assets')
    os.makedirs(css_dir, exist_ok=True)
    css = '''/* Minimal readable theme for GitHub Pages */
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  --muted: #666;
  --border: #e5e5e5;
  --link: #0969da;
  --code-bg: #f0f0f0;
  --max: 44rem;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #8b949e;
    --border: #30363d;
    --link: #58a6ff;
    --code-bg: #161b22;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.65;
  color: var(--fg);
  background: var(--bg);
}
.site-header, .site-main, .site-footer {
  max-width: var(--max);
  margin: 0 auto;
  padding: 1rem 1.25rem;
}
.site-header {
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
}
.site-title {
  font-weight: 700;
  font-size: 1.15rem;
  text-decoration: none;
  color: var(--fg);
}
.site-footer {
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.9rem;
}
a { color: var(--link); }
.post-list { list-style: none; padding: 0; margin: 0; }
.post-list li {
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
}
.post-list .date {
  display: inline-block;
  min-width: 6.5rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  margin-right: 0.5rem;
}
.post-meta { color: var(--muted); font-size: 0.9rem; margin: 0.25rem 0 1.25rem; }
.tags { margin: 0; padding: 0; list-style: none; display: inline; }
.tags li { display: inline; }
.tags li:not(:last-child)::after { content: ", "; }
article h1 { margin-top: 0; line-height: 1.3; }
pre, code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
}
code { background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px; }
pre {
  background: var(--code-bg);
  padding: 1rem;
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--border);
}
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid var(--border); padding: 0.4rem 0.6rem; text-align: left; }
img { max-width: 100%; height: auto; }
.back { margin-top: 2rem; }
'''
    path = os.path.join(css_dir, 'site.css')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(css)
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


def _render_index(posts):
    items = []
    for p in posts:
        href = html.escape(_href(f"posts/{p['basename']}.html"))
        title = html.escape(p['title'])
        date = html.escape(p['date'])
        items.append(
            f'<li><span class="date">{date}</span> '
            f'<a href="{href}">{title}</a></li>'
        )
    if items:
        listing = '<ul class="post-list">\n' + '\n'.join(items) + '\n</ul>'
    else:
        listing = '<p>No posts yet.</p>'
    body = f'<h1>Posts</h1>\n{listing}'
    return _page_shell(
        title=SITE_TITLE,
        description=SITE_DESCRIPTION,
        canonical=_site_url(''),
        body_html=body,
    )


def _render_post(post):
    content_html = _rewrite_relative_urls(_markdown_to_html(post['body']))
    tags_html = ''
    if post['tags']:
        tag_items = ''.join(f'<li>#{html.escape(t)}</li>' for t in post['tags'])
        tags_html = f' · <ul class="tags">{tag_items}</ul>'
    body = (
        f'<article>\n'
        f'<h1>{html.escape(post["title"])}</h1>\n'
        f'<p class="post-meta"><time datetime="{html.escape(post["date"])}">'
        f'{html.escape(post["date"])}</time>{tags_html}</p>\n'
        f'{content_html}\n'
        f'<p class="back"><a href="{html.escape(_href(""))}">← Back to posts</a></p>\n'
        f'</article>'
    )
    return _page_shell(
        title=f'{post["title"]} · {SITE_TITLE}',
        description=post['description'] or SITE_DESCRIPTION,
        canonical=_site_url(f'posts/{post["basename"]}.html'),
        body_html=body,
        og_type='article',
    )


def _write_sitemap(posts):
    urls = [_site_url('')]
    for p in posts:
        urls.append(_site_url(f'posts/{p["basename"]}.html'))
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
    content = f'''User-agent: *
Allow: /

Sitemap: {sitemap}
'''
    path = os.path.join(PUBLIC_DIR, 'robots.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def export_static_site(posts):
    """Build a minimal static site under public/ for GitHub Pages."""
    if os.path.isdir(PUBLIC_DIR):
        # Clear previous generated HTML/sitemap but keep structure simple: wipe & rebuild
        shutil.rmtree(PUBLIC_DIR)
    os.makedirs(os.path.join(PUBLIC_DIR, 'posts'), exist_ok=True)

    _write_site_css()
    _copy_assets()

    index_path = os.path.join(PUBLIC_DIR, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(_render_index(posts))

    for p in posts:
        out = os.path.join(PUBLIC_DIR, 'posts', f"{p['basename']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(_render_post(p))

    _write_sitemap(posts)
    _write_robots()
    print(f"Exported static site to {PUBLIC_DIR}/ ({len(posts)} posts)")


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
    export_static_site(all_posts)
