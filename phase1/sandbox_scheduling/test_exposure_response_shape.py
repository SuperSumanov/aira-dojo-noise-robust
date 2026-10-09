import json
import unittest
from exposure_response_shape import shape, syntax_shape


class ShapeTests(unittest.TestCase):
    def test_syntax_is_not_execution(self):
        self.assertTrue(syntax_shape('raise RuntimeError()')['parseable'])
        self.assertFalse(syntax_shape('')['nonempty'])
        self.assertEqual(syntax_shape('x = (')['error'], 'unclosed')

    def test_no_raw_exception_text(self):
        value = syntax_shape('bad PRIVATE_CONTENT text')
        self.assertNotIn('PRIVATE_CONTENT', repr(value))

    def test_empty_and_reasoning_distinct(self):
        extract = lambda s: ''
        parse = lambda s: ('thinking', '')
        self.assertEqual(shape('', '', extract, parse)['category'], 'empty_response')
        self.assertEqual(shape('reasoning', '', extract, parse)['category'], 'thinking_without_answer')

    def test_valid_alternative_is_only_syntax(self):
        value = shape('```python3\nx = 1\n```', 'unparsed', lambda s:'', lambda s:('', s))
        self.assertEqual(value['alternative_parseable_nonempty_fences'], 1)
        self.assertTrue(value['alternative_syntax_is_not_execution_evidence'])

    def test_real_extraction_not_replaced_by_shape(self):
        value = shape('explanation', 'x = 1', lambda s:s, lambda s:('', s))
        self.assertEqual(value['category'], 'nonempty_native_execution')
        self.assertNotIn('explanation', repr(value))

    def test_mixed_fences_serialize_without_raw_text(self):
        value = shape('```python\nx=1\n```\n```python\nx=(\n```', '', lambda s:'', lambda s:('',s))
        json.dumps(value, sort_keys=True)
        self.assertEqual(value['native_fence_errors'], {'parseable':1, 'unclosed':1})


if __name__ == '__main__':
    unittest.main()
