import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run_comparison_reuse_20260919 as driver
from run_comparison_third_bank_20260919 import configure,RUN
from test_comparison_reuse_verifier_20260919 import fixture
from verify_comparison_reuse_results_20260919 import verify

class ThirdBankTests(unittest.TestCase):
    def setUp(self):
        names=('RUNS','ROOT_PREFIX','ALLOCATION_SECONDS','SCRIPT','PLAN','READER','CONTEXT_MODULE','EXTRA_FILES','PREPARED_METADATA')
        self.restore=patch.multiple(driver,**{n:copy.deepcopy(getattr(driver,n)) for n in names})
        self.restore.start();self.addCleanup(self.restore.stop);configure()
    def test_only_third_group_executed(self):
        p=dict(allocation_seconds=7800,rows=[dict(index=i,seed=3) for i in range(6)])
        process=Mock();process.wait.return_value=0
        with tempfile.TemporaryDirectory() as folder,patch.object(driver,'prepared',return_value=p),\
             patch.object(driver,'source_check'),patch.object(driver,'read',return_value={'job':'123'}),\
             patch.object(driver,'write') as output,patch.dict(driver.os.environ,SLURM_JOB_ID='123'),\
             patch.object(driver.socket,'gethostname',return_value='gpu28'),\
             patch.object(driver.time,'monotonic',return_value=0),patch.object(driver.subprocess,'Popen',return_value=process) as launch:
            driver.coordinate(Path(folder))
            self.assertEqual([int(c.args[0][-1]) for c in launch.call_args_list],list(range(6)))
            self.assertEqual(output.call_args.args[1]['attempted_seeds'],[3])
    def test_six_source_rows_not_twelve(self):
        nodes=[]
        for step,parents,role,group in [(1,[0],'draft','executed'),(2,[1],'debug','executed')]+[(i,[0],'draft','unselected') for i in range(3,7)]:
            nodes.append(dict(run=RUN,step=step,parents=parents,operators_used=[role],group=group,
                creation_time=step,id=str(step),code_sha256='f'*64))
        rows=driver.select_rows(nodes)
        self.assertEqual(len(rows),6);self.assertEqual({r['seed'] for r in rows},{3})
    def test_independent_single_bank_can_reject_an_optimistic_result(self):
        full=fixture(.2,[.1,.3,None,None]);full['rows']=full['rows'][:6];full['groups']=full['groups'][:1]
        for row in full['rows']:row['seed']=3
        full['groups'][0]['seed']=3
        full.update(valid=3,no_valid_output=3)
        self.assertEqual(verify(full,expected_seeds=(3,))['status'],'PASS')
        full['groups'][0]['one_action_cache_vs_debug']['wins']+=1
        with self.assertRaises(AssertionError):verify(full,expected_seeds=(3,))
    def test_unsupported_cohort_not_inferred(self):
        with self.assertRaises(ValueError):verify({},expected_seeds=(99,))

if __name__=='__main__':unittest.main()
