import hashlib
import unittest
from closed_role_origin_20261014 import origin


class OriginTests(unittest.TestCase):
    def test_unmatched(self):
        self.assertEqual(origin([], 'x'), 'unmatched')

    def test_recorded_role(self):
        code = 'fixture'
        digest = hashlib.sha256(code.encode()).hexdigest()
        for role in ('improve', 'debug'):
            node = dict(code=code, operators_used=[role, 'analysis'])
            self.assertEqual(origin([node], digest), role)
            self.assertEqual(origin([node, node], digest), role)

    def test_conflicting_hash_matches_not_chosen(self):
        digest = hashlib.sha256(b'fixture').hexdigest()
        nodes = [dict(code='fixture', operators_used=[r]) for r in ('improve', 'debug')]
        self.assertEqual(origin(nodes, digest), 'ambiguous')

    def test_missing_or_multiple_code_roles_not_guessed(self):
        digest = hashlib.sha256(b'fixture').hexdigest()
        for roles in ([], ['analysis'], ['debug', 'improve']):
            self.assertEqual(origin([dict(code='fixture', operators_used=roles)], digest), 'ambiguous')


if __name__ == '__main__':
    unittest.main()
