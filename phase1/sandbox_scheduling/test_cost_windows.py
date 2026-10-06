import unittest
import cost_windows as c


def fixture():
    return {'rows': [dict(index=i, arm=('ROOT' if i < 2 else
        ['continue', 'reimplement', 'new_idea', 'random_hpo'][(i-2)//4]),
        task='a' if i % 2 else 'b', elapsed_seconds=100., returned_generation_seconds=20.,
        recorded_execution_seconds=30., quality=object()) for i in range(18)]}


class CostWindowTests(unittest.TestCase):
    def test_projection_denies_quality(self):
        class Guard(dict):
            def __getitem__(self, key):
                if key not in c.FIELDS:
                    raise AssertionError('forbidden result field')
                return super().__getitem__(key)
        data = fixture()
        data['rows'] = [Guard(row) for row in data['rows']]
        rows, summary = c.analyze(data)
        self.assertEqual(summary['llm_rows'], 12)
        self.assertEqual(summary['recorded_returned_generation_seconds'], 240.)
        self.assertNotIn('quality', rows[0])

    def test_missing_elapsed_remains_missing(self):
        data = fixture()
        data['rows'][2]['elapsed_seconds'] = None
        rows, summary = c.analyze(data)
        self.assertIsNone(rows[2]['returned_generation_fraction'])
        self.assertEqual(summary['unknown_elapsed'], 1)
        self.assertEqual(summary['fraction_among_known_elapsed']['n'], 11)
        self.assertEqual(summary['recorded_returned_generation_seconds'], 240.)

    def test_invalid_or_overlapping_times(self):
        for changes in ({'returned_generation_seconds': None}, {'elapsed_seconds': -1},
                        {'elapsed_seconds': float('nan')}, {'elapsed_seconds': 49}):
            data = fixture()
            data['rows'][2].update(changes)
            with self.assertRaises(ValueError):
                c.analyze(data)

    def test_incomplete_or_duplicated_denominator(self):
        data = fixture()
        data['rows'].pop()
        with self.assertRaises(ValueError):
            c.analyze(data)
        data = fixture()
        data['rows'][1]['index'] = 0
        with self.assertRaises(ValueError):
            c.analyze(data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
