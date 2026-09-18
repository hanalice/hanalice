import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import traffic_rollup


class TestMergeRepoViews(unittest.TestCase):

    def test_merges_days_and_sums_counts(self):
        store = traffic_rollup.load_traffic('/nonexistent.json')
        traffic_rollup.merge_repo_views(store, {
            'count': 10,
            'uniques': 4,
            'views': [
                {'timestamp': '2026-09-01T00:00:00Z', 'count': 3, 'uniques': 2},
                {'timestamp': '2026-09-02T00:00:00Z', 'count': 7, 'uniques': 3},
            ],
        })
        traffic_rollup.merge_repo_views(store, {
            'count': 8,
            'uniques': 5,
            'views': [
                {'timestamp': '2026-09-02T00:00:00Z', 'count': 5, 'uniques': 2},
                {'timestamp': '2026-09-03T00:00:00Z', 'count': 1, 'uniques': 1},
            ],
        })
        self.assertEqual(store['repo']['days']['2026-09-01']['count'], 3)
        self.assertEqual(store['repo']['days']['2026-09-02']['count'], 5)
        self.assertEqual(store['repo']['total_count'], 9)
        self.assertEqual(store['repo']['uniques_14d'], 5)
        self.assertEqual(store['repo']['count_14d'], 8)
        self.assertTrue(store['repo']['updated_at'])


class TestGoatCounterParse(unittest.TestCase):

    def test_parses_formatted_strings(self):
        totals = traffic_rollup.parse_goatcounter_total({
            'count': '1,234',
            'count_unique': '56',
        })
        self.assertEqual(totals['count'], 1234)
        self.assertEqual(totals['count_unique'], 56)

    def test_code_from_env(self):
        self.assertEqual(
            traffic_rollup.goatcounter_code(environ={'GOATCOUNTER_CODE': 'from-env'}),
            'from-env',
        )
        self.assertEqual(
            traffic_rollup.goatcounter_code(environ={'GOATCOUNTER_CODE': 'NOPE'}),
            '',
        )
        self.assertEqual(traffic_rollup.goatcounter_code(environ={}), '')


if __name__ == '__main__':
    unittest.main()
