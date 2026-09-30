import unittest
from fence_replay_0930 import alternative

class Tests(unittest.TestCase):
    def test_inline_fence_inside_raw_python(self):
        s='text = "```python"\n';k,out,*_=alternative(s)
        self.assertEqual((k,out),('raw_python',s))
    def test_inline_fence_inside_envelope(self):
        s='Plan.\n```python\ntext = "```python"\nprint(text)\n```\n'
        k,out,*_=alternative(s)
        self.assertEqual(k,'single_valid_block');self.assertEqual(out,'text = "```python"\nprint(text)\n')
    def test_multiple_valid_blocks_rejected(self):
        self.assertEqual(alternative('Plan\n```python\nx=1\n```\n```python\ny=2\n```')[0],'ambiguous')
    def test_invalid_code_not_repaired(self):
        self.assertIsNone(alternative('Plan\n```python\nx=(\n```')[1])
    def test_unclosed_fence_rejected(self):
        self.assertEqual(alternative('Plan\n```python\nx=1\n')[0],'unclosed_fence')
    def test_longer_outer_fence(self):
        k,out,*_=alternative('Plan\n````python\ns="```"\n````\n');self.assertEqual(k,'single_valid_block')
    def test_empty_block_rejected(self):
        self.assertIsNone(alternative('Plan\n```python\n\n```')[1])
    def test_compile_only_no_execution(self):
        self.assertEqual(alternative('raise RuntimeError("not run")')[0],'raw_python')

if __name__=='__main__':unittest.main()
