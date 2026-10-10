import unittest
from safe_senior_reader import redact


class UrlRedaction(unittest.TestCase):
    def test_malformed_url_fails_closed_without_aborting_document(self):
        safe, counts = redact('before https://[HOST_TEMPLATE/path?token=synthetic_example after')
        self.assertEqual(safe, 'before [REDACTED_UNPARSEABLE_URL] after')
        self.assertEqual(counts[2], 1)

    def test_valid_query_is_still_redacted(self):
        safe, counts = redact('https://example.invalid/path?accessToken=synthetic_example&x=1')
        self.assertNotIn('synthetic_example', safe)
        self.assertIn('x=1', safe)
        self.assertEqual(counts[2], 1)

    def test_ordinary_url_is_preserved(self):
        raw = 'https://example.invalid/path?x=1'
        self.assertEqual(redact(raw)[0], raw)


if __name__ == '__main__':
    unittest.main()
