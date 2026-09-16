import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import sync


def _write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


# ── Bug 5: malformed posts skipped with warning, not silently defaulted ─────

class TestParsePost(unittest.TestCase):

    def _post(self, text, tmpdir):
        path = os.path.join(tmpdir, 'post.md')
        _write(path, text)
        return path

    def test_valid_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("---\ntitle: Hello\ndate: 2026-01-01\ntags: Git, Docker\n---\nBody", d)
            result = sync.parse_post(p)
            self.assertEqual(result['title'], 'Hello')
            self.assertEqual(result['date'], '2026-01-01')
            self.assertEqual(result['tags'], ['Git', 'Docker'])

    def test_missing_title_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("---\ndate: 2026-01-01\n---\nBody", d)
            self.assertIsNone(sync.parse_post(p))

    def test_missing_date_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("---\ntitle: Hello\n---\nBody", d)
            self.assertIsNone(sync.parse_post(p))

    def test_unclosed_frontmatter_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("---\ntitle: Hello\ndate: 2026-01-01\nno closing fence", d)
            self.assertIsNone(sync.parse_post(p))

    def test_no_frontmatter_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("Just content, no frontmatter", d)
            self.assertIsNone(sync.parse_post(p))

    def test_colon_in_value_not_split(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._post("---\ntitle: Hello: World\ndate: 2026-01-01\n---\nBody", d)
            result = sync.parse_post(p)
            self.assertEqual(result['title'], 'Hello: World')


# ── Bug 2: re.sub replacement vulnerable to regex metacharacters ─────────────

class TestInjectSection(unittest.TestCase):

    def test_basic_replacement(self):
        c = "A\n<!-- S -->\nold\n<!-- E -->\nB"
        result = sync._inject_section(c, '<!-- S -->', '<!-- E -->', 'new')
        self.assertEqual(result, "A\n<!-- S -->\nnew\n<!-- E -->\nB")

    def test_backreference_in_body_not_interpreted(self):
        # re.sub would raise or corrupt output if body contains \1 or \g<n>
        c = "A\n<!-- S -->\nold\n<!-- E -->\nB"
        body = r"title \1 and \g<name> and \2"
        result = sync._inject_section(c, '<!-- S -->', '<!-- E -->', body)
        self.assertIn(r'\1', result)
        self.assertIn(r'\g<name>', result)
        self.assertIn('A', result)
        self.assertIn('B', result)

    def test_replaces_existing_content(self):
        c = "<!-- S -->\nold content here\n<!-- E -->"
        result = sync._inject_section(c, '<!-- S -->', '<!-- E -->', 'replaced')
        self.assertNotIn('old content here', result)
        self.assertIn('replaced', result)

    def test_empty_body(self):
        c = "<!-- S -->\nstuff\n<!-- E -->"
        result = sync._inject_section(c, '<!-- S -->', '<!-- E -->', '')
        self.assertEqual(result, "<!-- S -->\n\n<!-- E -->")


# ── Bug 6: empty all_tags must not wipe existing tag pages ───────────────────
# ── Bug 7: removeprefix('./')  vs lstrip('./') character-stripping ───────────

class TestGenerateTagPages(unittest.TestCase):

    def setUp(self):
        self._orig = sync.TAGS_DIR

    def tearDown(self):
        sync.TAGS_DIR = self._orig

    def test_empty_tags_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as d:
            existing = os.path.join(d, 'Git.md')
            _write(existing, 'keep me')
            sync.TAGS_DIR = d
            sync.generate_tag_pages({}, [])
            self.assertTrue(os.path.exists(existing), "existing tag file must not be deleted when all_tags is empty")

    def test_path_prefix_only_dot_slash_stripped(self):
        # lstrip('./') treats '.' and '/' as individual chars to strip,
        # so './.hidden/post.md' → 'hidden/post.md' (wrong).
        # removeprefix('./') strips only the literal './' prefix → '.hidden/post.md'.
        with tempfile.TemporaryDirectory() as d:
            sync.TAGS_DIR = d
            posts = [{'title': 'T', 'date': '2026-01-01', 'tags': ['X'], 'path': './.hidden/post.md'}]
            sync.generate_tag_pages({'X': 1}, posts)
            with open(os.path.join(d, 'X.md')) as f:
                body = f.read()
            self.assertIn('../.hidden/post.md', body, "hidden-dir dot must not be stripped from path")

    def test_normal_post_path(self):
        with tempfile.TemporaryDirectory() as d:
            sync.TAGS_DIR = d
            posts = [{'title': 'T', 'date': '2026-01-01', 'tags': ['Git'], 'path': './posts/p.md'}]
            sync.generate_tag_pages({'Git': 1}, posts)
            with open(os.path.join(d, 'Git.md')) as f:
                body = f.read()
            self.assertIn('../posts/p.md', body)


# ── Bug 1: rotate_mascot daily file extension must match source ──────────────

class TestRotateMascot(unittest.TestCase):

    def setUp(self):
        self._orig = sync.MASCOTS_DIR

    def tearDown(self):
        sync.MASCOTS_DIR = self._orig

    def test_daily_extension_matches_png_source(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, '01.png'), 'w').close()
            sync.MASCOTS_DIR = d
            sync.rotate_mascot()
            daily = [f for f in os.listdir(d) if f.startswith('daily.')]
            self.assertEqual(daily, ['daily.png'])

    def test_daily_extension_matches_gif_source(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, '01.gif'), 'w').close()
            sync.MASCOTS_DIR = d
            sync.rotate_mascot()
            daily = [f for f in os.listdir(d) if f.startswith('daily.')]
            self.assertEqual(daily, ['daily.gif'])

    def test_stale_daily_with_wrong_extension_removed(self):
        # Pre-existing daily.gif when source is PNG — old stale file must be cleaned up.
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, '01.png'), 'w').close()
            open(os.path.join(d, 'daily.gif'), 'w').close()
            sync.MASCOTS_DIR = d
            sync.rotate_mascot()
            self.assertFalse(os.path.exists(os.path.join(d, 'daily.gif')))
            self.assertTrue(os.path.exists(os.path.join(d, 'daily.png')))

    def test_default_mascot_excluded_from_pool(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, 'default_mascot.png'), 'w').close()
            sync.MASCOTS_DIR = d
            result = sync.rotate_mascot()
            self.assertIsNone(result)

    def test_returns_path_to_daily_file(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, '01.png'), 'w').close()
            sync.MASCOTS_DIR = d
            result = sync.rotate_mascot()
            self.assertTrue(result.endswith('daily.png'))


# ── Bug 3: missing template must exit non-zero, not return None silently ──────

class TestUpdateReadme(unittest.TestCase):

    def setUp(self):
        self._orig_tpl = sync.README_TEMPLATE
        self._orig_out = sync.README_OUTPUT

    def tearDown(self):
        sync.README_TEMPLATE = self._orig_tpl
        sync.README_OUTPUT = self._orig_out

    def _minimal_template(self, path):
        _write(path,
            "{{DAILY_MASCOT}}\n"
            "<!-- BLOG-POST-LIST:START -->\n<!-- BLOG-POST-LIST:END -->\n"
            "<!-- TAG-CLOUD:START -->\n<!-- TAG-CLOUD:END -->\n"
            "{{LAST_SYNC}}"
        )

    def test_missing_template_raises_systemexit(self):
        sync.README_TEMPLATE = '/nonexistent/__missing__.md'
        with self.assertRaises(SystemExit):
            sync.update_readme([], {})

    def test_daily_mascot_placeholder_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = os.path.join(d, 'README.template.md')
            out = os.path.join(d, 'README.md')
            self._minimal_template(tpl)
            sync.README_TEMPLATE = tpl
            sync.README_OUTPUT = out
            sync.update_readme([], {}, daily_mascot='./assets/mascots/daily.png')
            with open(out) as f:
                body = f.read()
            self.assertIn('./assets/mascots/daily.png', body)
            self.assertNotIn('{{DAILY_MASCOT}}', body)

    def test_no_daily_mascot_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = os.path.join(d, 'README.template.md')
            out = os.path.join(d, 'README.md')
            self._minimal_template(tpl)
            sync.README_TEMPLATE = tpl
            sync.README_OUTPUT = out
            sync.update_readme([], {}, daily_mascot=None)
            with open(out) as f:
                body = f.read()
            self.assertNotIn('{{DAILY_MASCOT}}', body)
            self.assertIn('default_mascot.png', body)

    def test_last_sync_placeholder_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = os.path.join(d, 'README.template.md')
            out = os.path.join(d, 'README.md')
            self._minimal_template(tpl)
            sync.README_TEMPLATE = tpl
            sync.README_OUTPUT = out
            sync.update_readme([], {})
            with open(out) as f:
                body = f.read()
            self.assertNotIn('{{LAST_SYNC}}', body)



# ── GitHub Pages static export ───────────────────────────────────────────────

class TestExportStaticSite(unittest.TestCase):

    def setUp(self):
        self._orig = {
            'POSTS_DIR': sync.POSTS_DIR,
            'TAGS_DIR': sync.TAGS_DIR,
            'README_TEMPLATE': sync.README_TEMPLATE,
            'README_OUTPUT': sync.README_OUTPUT,
            'MASCOTS_DIR': sync.MASCOTS_DIR,
            'ASSETS_DIR': sync.ASSETS_DIR,
            'PUBLIC_DIR': sync.PUBLIC_DIR,
        }

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(sync, k, v)

    def _setup_repo(self, d):
        posts = os.path.join(d, 'posts')
        tags = os.path.join(d, 'tags')
        assets = os.path.join(d, 'assets')
        mascots = os.path.join(assets, 'mascots')
        public = os.path.join(d, 'public')
        os.makedirs(posts)
        os.makedirs(tags)
        os.makedirs(mascots)
        open(os.path.join(mascots, '01.png'), 'wb').close()
        tpl = os.path.join(d, 'README.template.md')
        _write(tpl,
            "{{DAILY_MASCOT}}\n"
            "<!-- BLOG-POST-LIST:START -->\n<!-- BLOG-POST-LIST:END -->\n"
            "<!-- TAG-CLOUD:START -->\n<!-- TAG-CLOUD:END -->\n"
            "{{LAST_SYNC}}"
        )
        _write(
            os.path.join(posts, 'hello_world.md'),
            "---\n"
            "title: Hello World\n"
            "date: 2026-01-15\n"
            "tags: Test\n"
            "---\n\n"
            "First paragraph for description.\n\n"
            "More body text.\n",
        )
        sync.POSTS_DIR = posts
        sync.TAGS_DIR = tags
        sync.README_TEMPLATE = tpl
        sync.README_OUTPUT = os.path.join(d, 'README.md')
        sync.MASCOTS_DIR = mascots
        sync.ASSETS_DIR = assets
        sync.PUBLIC_DIR = public
        return public

    def test_export_creates_sitemap_and_post_html(self):
        with tempfile.TemporaryDirectory() as d:
            public = self._setup_repo(d)
            all_posts = []
            for f in os.listdir(sync.POSTS_DIR):
                if f.endswith('.md'):
                    post = sync.parse_post(os.path.join(sync.POSTS_DIR, f))
                    if post is not None:
                        all_posts.append(post)
            all_posts.sort(key=lambda x: x['date'], reverse=True)
            all_tags = {}
            for p in all_posts:
                for tag in p['tags']:
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            sync.export_static_site(all_posts, all_tags)

            sitemap = os.path.join(public, 'sitemap.xml')
            post_html = os.path.join(public, 'posts', 'hello_world.html')
            index_html = os.path.join(public, 'index.html')
            self.assertTrue(os.path.exists(sitemap), "public/sitemap.xml must exist after export")
            self.assertTrue(os.path.exists(post_html), "public/posts/<basename>.html must exist")
            self.assertTrue(os.path.exists(index_html), "public/index.html must exist")
            with open(sitemap, encoding='utf-8') as f:
                sm = f.read()
            self.assertIn('hello_world.html', sm)
            self.assertIn('https://hanalice.github.io/hanalice', sm)
            with open(post_html, encoding='utf-8') as f:
                body = f.read()
            self.assertIn('Hello World', body)
            self.assertIn('rel="canonical"', body)

    def test_export_nav_and_tag_pages(self):
        with tempfile.TemporaryDirectory() as d:
            public = self._setup_repo(d)
            all_posts = []
            for f in os.listdir(sync.POSTS_DIR):
                if f.endswith('.md'):
                    post = sync.parse_post(os.path.join(sync.POSTS_DIR, f))
                    if post is not None:
                        all_posts.append(post)
            all_tags = {'Test': 1}
            sync.export_static_site(all_posts, all_tags)

            index_html = os.path.join(public, 'index.html')
            tags_index = os.path.join(public, 'tags', 'index.html')
            tag_page = os.path.join(public, 'tags', 'Test.html')
            post_html = os.path.join(public, 'posts', 'hello_world.html')
            css = os.path.join(public, 'assets', 'site.css')

            self.assertTrue(os.path.exists(tags_index), "public/tags/index.html must exist")
            self.assertTrue(os.path.exists(tag_page), "public/tags/<Tag>.html must exist")

            with open(index_html, encoding='utf-8') as f:
                index = f.read()
            self.assertIn('site-nav', index)
            self.assertIn('data-filter="all"', index)
            self.assertIn('data-filter="Test"', index)
            self.assertIn('data-tags=', index)
            self.assertIn('/hanalice/tags/', index)
            self.assertIn('Posts', index)

            with open(tags_index, encoding='utf-8') as f:
                ti = f.read()
            self.assertIn('site-nav', ti)
            self.assertIn('Test', ti)
            self.assertIn('/hanalice/tags/Test.html', ti)

            with open(tag_page, encoding='utf-8') as f:
                tp = f.read()
            self.assertIn('Hello World', tp)
            self.assertIn('site-nav', tp)

            with open(post_html, encoding='utf-8') as f:
                post = f.read()
            self.assertIn('site-nav', post)
            self.assertIn('/hanalice/tags/Test.html', post)

            with open(css, encoding='utf-8') as f:
                style = f.read()
            self.assertIn('-apple-system', style)
            self.assertIn('#f5f5f7', style)
            self.assertIn('#0066cc', style)

            with open(os.path.join(public, 'sitemap.xml'), encoding='utf-8') as f:
                sm = f.read()
            self.assertIn('/tags/', sm)
            self.assertIn('/tags/Test.html', sm)

    def test_parse_post_includes_description_from_body(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'post.md')
            _write(p, "---\ntitle: T\ndate: 2026-01-01\n---\n\nAlpha beta gamma.\n")
            result = sync.parse_post(p)
            self.assertIsNotNone(result)
            self.assertIn('Alpha beta gamma', result['description'])
            self.assertEqual(result['basename'], 'post')


# ── Pages polish: excerpt skips headings; posts/*.md → .html ─────────────────

class TestFirstParagraphExcerpt(unittest.TestCase):

    def test_skips_markdown_heading_paragraph(self):
        body = (
            "## 1. 问题现象 (Problem Symptoms)\n\n"
            "上一篇工具面讲过现象 C：超时之后凭什么敢重试。\n\n"
            "More prose here.\n"
        )
        excerpt = sync._first_paragraph_excerpt(body)
        self.assertNotIn('问题现象', excerpt)
        self.assertTrue(excerpt.startswith('上一篇'))

    def test_skips_heading_then_takes_prose(self):
        body = "### 问题描述\n\n在 WSL 环境下，使用 pnpm 安装后构建失败。\n"
        excerpt = sync._first_paragraph_excerpt(body)
        self.assertNotEqual(excerpt, '问题描述')
        self.assertIn('WSL', excerpt)

    def test_parse_post_description_skips_heading(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'post.md')
            _write(
                p,
                "---\n"
                "title: T\n"
                "date: 2026-01-01\n"
                "---\n\n"
                "## 1. 问题现象 Problem Symptoms\n\n"
                "Real prose paragraph about the bug.\n",
            )
            result = sync.parse_post(p)
            self.assertIsNotNone(result)
            self.assertNotIn('问题现象', result['description'])
            self.assertIn('Real prose', result['description'])


class TestRewritePostMdLinks(unittest.TestCase):

    def test_rewrites_site_posts_md_to_html(self):
        html_in = (
            '<p><a href="/hanalice/posts/foo.md">a</a> '
            '<a href="posts/bar.md">b</a> '
            '<a href="../posts/baz.md#sec">c</a></p>'
        )
        out = sync._rewrite_post_md_links(html_in)
        self.assertIn('/hanalice/posts/foo.html', out)
        self.assertIn('posts/bar.html', out)
        self.assertIn('../posts/baz.html#sec', out)
        self.assertNotIn('posts/foo.md', out)
        self.assertNotIn('posts/bar.md', out)

    def test_leaves_non_posts_md_alone(self):
        html_in = '<a href="https://example.com/x.md">ext</a> <a href="notes/x.md">n</a>'
        out = sync._rewrite_post_md_links(html_in)
        self.assertIn('https://example.com/x.md', out)
        self.assertIn('notes/x.md', out)

    def test_render_post_rewrites_in_article_links(self):
        post = {
            'title': 'T',
            'date': '2026-01-01',
            'tags': ['Git'],
            'description': 'desc',
            'body': 'See [other](posts/other_post.md) for details.\n',
            'basename': 't',
            'path': './posts/t.md',
        }
        html_out = sync._render_post(post)
        self.assertIn('posts/other_post.html', html_out)
        self.assertNotIn('posts/other_post.md', html_out)


class TestIndexTagPolish(unittest.TestCase):

    def test_post_tag_chips_overflow(self):
        html_out = sync._post_tag_chips_html(
            ['A', 'B', 'C', 'D'], max_visible=3, overflow_href='/hanalice/posts/x.html'
        )
        self.assertEqual(html_out.count('class="tag-chip"'), 3)
        self.assertIn('+1', html_out)
        self.assertIn('tag-more', html_out)

    def test_index_shows_top_tags_and_more_link(self):
        all_tags = {f'Tag{i}': (20 - i) for i in range(15)}
        posts = [{
            'title': 'Hello',
            'date': '2026-01-01',
            'tags': ['Tag0', 'Tag1', 'Tag2', 'Tag3'],
            'basename': 'hello',
            'description': 'd',
            'body': 'body',
            'path': './posts/hello.md',
        }]
        html_out = sync._render_index(posts, all_tags)
        self.assertIn('data-filter="all"', html_out)
        self.assertIn('tag-chip-more', html_out)
        self.assertIn('更多', html_out)
        self.assertIn('/hanalice/tags/', html_out)
        self.assertIn('data-filter="Tag0"', html_out)
        self.assertNotIn('data-filter="Tag14"', html_out)
        self.assertIn('+1', html_out)



# ── Pages polish P2: nav active, dark mode CSS, mermaid ──────────────────────

class TestNavActiveState(unittest.TestCase):

    def test_posts_index_marks_posts_active(self):
        html_out = sync._render_index([], {})
        self.assertIn('class="active">Posts</a>', html_out)
        self.assertNotIn('class="active">Tags</a>', html_out)

    def test_tags_index_and_detail_mark_tags_active(self):
        ti = sync._render_tags_index({'Git': 1})
        self.assertIn('class="active">Tags</a>', ti)
        self.assertNotIn('class="active">Posts</a>', ti)
        post = {
            'title': 'T',
            'date': '2026-01-01',
            'tags': ['Git'],
            'basename': 't',
            'description': 'd',
            'body': 'body',
            'path': './posts/t.md',
        }
        tp = sync._render_tag_page('Git', [post], 1)
        self.assertIn('class="active">Tags</a>', tp)
        self.assertNotIn('class="active">Posts</a>', tp)

    def test_article_page_marks_neither_posts_nor_tags(self):
        post = {
            'title': 'T',
            'date': '2026-01-01',
            'tags': ['Git'],
            'basename': 't',
            'description': 'd',
            'body': 'Just prose.\n',
            'path': './posts/t.md',
        }
        html_out = sync._render_post(post)
        nav = html_out.split('nav-links', 1)[1].split('</ul>', 1)[0]
        self.assertNotIn('class="active"', nav)


class TestDarkModeCss(unittest.TestCase):

    def test_site_css_has_prefers_color_scheme_dark(self):
        self.assertIn('@media (prefers-color-scheme: dark)', sync._SITE_CSS)
        self.assertIn('--bg: #000000', sync._SITE_CSS)
        self.assertIn('--card: #1d1d1f', sync._SITE_CSS)
        # Light theme remains the default :root
        self.assertIn('--bg: #f5f5f7', sync._SITE_CSS)


class TestMermaidSupport(unittest.TestCase):

    def _post(self, body):
        return {
            'title': 'Diagram',
            'date': '2026-01-01',
            'tags': ['Test'],
            'basename': 'diagram',
            'description': 'd',
            'body': body,
            'path': './posts/diagram.md',
        }

    def test_detects_mermaid_fence(self):
        self.assertTrue(sync._content_has_mermaid("```mermaid\nflowchart LR\nA-->B\n```\n"))
        self.assertTrue(sync._content_has_mermaid('', '<pre><code class="language-mermaid">x</code></pre>'))
        self.assertFalse(sync._content_has_mermaid("```python\nprint(1)\n```\n"))

    def test_render_post_includes_mermaid_only_when_needed(self):
        with_m = sync._render_post(self._post(
            "Intro\n\n```mermaid\nflowchart LR\nA-->B\n```\n"
        ))
        self.assertIn(sync.MERMAID_CDN, with_m)
        self.assertIn('mermaid.initialize', with_m)
        self.assertIn('mermaid.run', with_m)
        self.assertIn('language-mermaid', with_m)

        without = sync._render_post(self._post('No diagrams, only `code`.\n'))
        self.assertNotIn('mermaid.min.js', without)
        self.assertNotIn('mermaid.initialize', without)




# ── Pages polish: subtitle, card descriptions, TOC ───────────────────────────

class TestSiteDescription(unittest.TestCase):

    def test_site_description_persona(self):
        self.assertEqual(sync.SITE_DESCRIPTION, 'Apple-Style Minimalist Developer')

    def test_index_page_sub_uses_site_description(self):
        html_out = sync._render_index([], {})
        self.assertIn('Apple-Style Minimalist Developer', html_out)
        self.assertIn('class="page-sub"', html_out)
        self.assertIn('name="description" content="Apple-Style Minimalist Developer"', html_out)


class TestIndexCardDescription(unittest.TestCase):

    def test_card_includes_description_and_reading_time(self):
        posts = [{
            'title': 'Hello Card',
            'date': '2026-03-01',
            'tags': ['Git'],
            'basename': 'hello_card',
            'description': 'Gray description under the title for the homepage card.',
            'body': '正文' * 200 + '\n\n' + ('word ' * 50),
            'path': './posts/hello_card.md',
        }]
        html_out = sync._render_index(posts, {'Git': 1})
        self.assertIn('class="post-card"', html_out)
        self.assertIn('class="post-desc"', html_out)
        self.assertIn('Gray description under the title', html_out)
        self.assertIn('分钟阅读', html_out)
        self.assertIn('2026-03-01', html_out)
        # meta → title → desc → tags order
        meta_i = html_out.find('post-meta-line')
        title_i = html_out.find('class="post-title"')
        desc_i = html_out.find('class="post-desc"')
        tags_i = html_out.find('class="post-tags"')
        self.assertTrue(meta_i < title_i < desc_i < tags_i)

    def test_estimate_reading_minutes_minimum_one(self):
        self.assertEqual(sync._estimate_reading_minutes(''), 1)
        self.assertEqual(sync._estimate_reading_minutes('hi'), 1)

    def test_site_css_has_post_desc_clamp(self):
        self.assertIn('.post-desc', sync._SITE_CSS)
        self.assertIn('-webkit-line-clamp', sync._SITE_CSS)


class TestArticleToc(unittest.TestCase):

    def _post(self, body):
        return {
            'title': 'TOC Demo',
            'date': '2026-01-01',
            'tags': ['Test'],
            'basename': 'toc_demo',
            'description': 'd',
            'body': body,
            'path': './posts/toc_demo.md',
        }

    def test_toc_generated_when_headings_exist(self):
        html_out = sync._render_post(self._post(
            '## Alpha\n\nText.\n\n### Beta nested\n\nMore.\n\n## Gamma\n\nEnd.\n'
        ))
        self.assertIn('本文目录', html_out)
        self.assertIn('class="toc"', html_out)
        self.assertIn('has-toc', html_out)
        self.assertIn('1. Alpha', html_out)
        self.assertIn('— Beta nested', html_out)
        self.assertIn('2. Gamma', html_out)
        self.assertIn('id="alpha"', html_out)
        self.assertIn('href="#alpha"', html_out)
        self.assertIn('IntersectionObserver', html_out)
        self.assertIn('返回文章列表', html_out)

    def test_no_toc_when_no_headings(self):
        html_out = sync._render_post(self._post('Just a plain paragraph.\n'))
        self.assertNotIn('本文目录', html_out)
        self.assertNotIn('has-toc', html_out)

    def test_site_css_has_toc_sidebar(self):
        self.assertIn('.toc', sync._SITE_CSS)
        self.assertIn('position: sticky', sync._SITE_CSS)
        self.assertIn('post-layout.has-toc', sync._SITE_CSS)



if __name__ == '__main__':
    unittest.main()
