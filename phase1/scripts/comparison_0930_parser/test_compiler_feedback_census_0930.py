import unittest
from compiler_feedback_census_0930 import syntax_fact, analyze, GENERIC

class Checks(unittest.TestCase):
    def test_compile_does_not_execute(self):
        self.assertIsNone(syntax_fact('raise RuntimeError("must not run")'))
    def test_no_literal_export(self):
        f=syntax_fact('s = "private text\n')
        self.assertEqual(f['family'],'unterminated_string')
        self.assertNotIn('private',str(f))
    def test_line_column(self):
        f=syntax_fact('x=1\nif True\n    pass\n')
        self.assertEqual(f['line'],2)
    def test_same_line_not_just_same_family(self):
        self.assertNotEqual(syntax_fact('x="bad\n')['source_line_sha256'],
                            syntax_fact('y="bad\n')['source_line_sha256'])

if __name__=='__main__':unittest.main()
