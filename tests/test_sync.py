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


if __name__ == '__main__':
    unittest.main()
