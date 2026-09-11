import unittest
from forets_review_metric_20260912 import normalize_review, patch_parser


class ReviewMetricTests(unittest.TestCase):
    schema={'properties':{'metric':{'type':['number','null']}}}

    def test_exact_scalar_repair(self):
        for raw,wanted in [('0.75',.75),('null',None),(' -1.2e-3 ',-.0012),('0',0)]:
            with self.subTest(raw=raw):
                value={'is_bug':False,'metric':raw,'summary':'unchanged'}
                result=normalize_review(value,self.schema,'submit_review')
                self.assertEqual(result,dict(value,metric=wanted))
                self.assertEqual(value['metric'],raw)

    def test_ambiguous_or_invalid_strings_stay_rejected(self):
        for raw in ['NaN','Infinity','-Infinity','1e309','true','false','None','75%',
                    'score=0.75','0,75','', '"0.75"', '{}','[]','01']:
            with self.subTest(raw=raw):
                value={'metric':raw}
                self.assertIs(normalize_review(value,self.schema,'submit_review'),value)

    def test_no_other_function_field_or_schema_coercion(self):
        value={'metric':'0.75','is_bug':'false','summary':3}
        self.assertIs(normalize_review(value,self.schema,'submit_code'),value)
        self.assertIs(normalize_review(value,{'properties':{'metric':{'type':'number'}}},'submit_review'),value)
        result=normalize_review(value,self.schema,'submit_review')
        self.assertEqual(result['is_bug'],'false');self.assertEqual(result['summary'],3)

    def test_explicit_failure_text_is_null_and_stays_failure(self):
        for text in ['None','not available','0.75','null']:
            value={'metric':text,'is_bug':True,'summary':'failure details'}
            result=normalize_review(value,self.schema,'submit_review')
            self.assertIsNone(result['metric']);self.assertIs(result['is_bug'],True)
            self.assertEqual(result['summary'],value['summary'])
        for flag in [False,1,'true',None]:
            value={'metric':'not available','is_bug':flag}
            self.assertIs(normalize_review(value,self.schema,'submit_review'),value)

    def test_patch_fail_closed(self):
        huge={'metric':'9'*1000}
        self.assertIs(normalize_review(huge,self.schema,'submit_review'),huge)
        anchor='        jsonschema.Draft7Validator(func_spec.json_schema).validate(output)'
        self.assertIn('normalize_review',patch_parser(anchor))
        with self.assertRaises(ValueError):patch_parser('wrong')
        with self.assertRaises(ValueError):patch_parser(anchor+'\n'+anchor)


if __name__=='__main__':unittest.main()
