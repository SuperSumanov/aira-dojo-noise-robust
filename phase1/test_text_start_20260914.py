"""CPU synthetic interface checks only, not real-task efficacy."""
import ast,contextlib,io,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
import forets_text_start_20260914 as s
import forets_edit_scope_20260914 as scope


class TextStart(unittest.TestCase):
    def test_actual_program_and_scope_assembly(self):
        code=s.code_for(s.TASK);tree=ast.parse(code)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_model')
        assembled,receipt=scope.assemble(code,ast.get_source_segment(code,function))
        self.assertTrue(receipt['interface_accepted'])
        for program in (code,assembled):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'data').mkdir()
                examples=[dict(id=f't-{i}',author=('A','B','C')[i%3],
                    text=f"sample prose unique{i} "+('alpha verse','beta fiction','gamma tale')[i%3]) for i in range(60)]
                pd.DataFrame(examples).to_csv(root/'data/train.csv',index=False)
                pd.DataFrame({'id':['z','a','p'],'text':['alpha new verse',None,'gamma tale']}).to_csv(root/'data/test.csv',index=False)
                fit_rows=[];original=Pipeline.fit
                def logged(instance,X,y=None,**kwargs):
                    fit_rows.append(len(X));return original(instance,X,y,**kwargs)
                prior=os.getcwd()
                try:
                    os.chdir(root)
                    with patch.object(Pipeline,'fit',logged),contextlib.redirect_stdout(io.StringIO()):exec(compile(program,'fixture.py','exec'),{'__name__':'__main__'})
                finally:os.chdir(prior)
                out=pd.read_csv(root/'submission.csv')
                self.assertEqual(out['id'].tolist(),['z','a','p'])
                self.assertEqual(list(out.columns),['id','A','B','C'])
                values=out[['A','B','C']].to_numpy()
                self.assertTrue(np.isfinite(values).all());self.assertTrue((values>=0).all())
                np.testing.assert_allclose(values.sum(axis=1),1.,rtol=0,atol=1e-12)
                self.assertEqual(fit_rows,[48,60])

    def test_unknown_task_rejected(self):
        with self.assertRaises(ValueError):s.code_for('another-task')


if __name__=='__main__':unittest.main()
