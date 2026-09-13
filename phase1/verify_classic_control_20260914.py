"""Bounded CPU fixtures: shared RF, every model family, real child/publication path."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest

import run_classic_control_20260914 as r


def verify(root):
    p=r.checked(root);r.source_check();r.setup(root,p)
    import numpy as np
    import pandas as pd
    from threadpoolctl import threadpool_limits
    import classic_search_20260914 as c
    from readout_classic_control_20260914 import select_incumbent
    from dojo.solvers.fore_ts import common_start
    from test_classic_control_20260914 import Tests
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    out=io.StringIO();unit_result=unittest.TextTestRunner(stream=out).run(suite)
    if not unit_result.wasSuccessful():raise ValueError('unit failure')
    proofs=[]
    with tempfile.TemporaryDirectory(prefix='classic-preflight-',dir=root) as tmp:
        base=Path(tmp);old=Path.cwd();rng=np.random.default_rng(777)
        try:
            for index,task in enumerate(('leaf-classification','spaceship-titanic')):
                work=base/task;work.mkdir();(work/'data').mkdir();os.chdir(work)
                if task=='leaf-classification':
                    frame=pd.DataFrame(rng.normal(size=(120,4)),columns=['f1','f2','f3','f4']);frame.insert(0,'id',range(120));frame['species']=np.tile(['a','b','c'],40)
                    test=frame.drop(columns='species').iloc[:17].copy()
                else:
                    frame=pd.DataFrame({'PassengerId':[str(i) for i in range(120)],'Name':['n']*120,
                        'HomePlanet':np.tile(['Earth','Mars',None],40),'CryoSleep':np.tile([True,False,None],40),
                        'Age':rng.normal(size=120),'Transported':np.tile([True,False],60)})
                    test=frame.drop(columns='Transported').iloc[:17].copy()
                frame.to_csv('data/train.csv',index=False);test.to_csv('data/test.csv',index=False)
                repeats=[]
                for _ in range(3):
                    with threadpool_limits(limits=6),redirect_stdout(io.StringIO()) as stdout:
                        exec(compile(common_start.original_code_for(task),'<original-RF>','exec'),{})
                    repeats.append((Path('submission.csv').read_bytes(),float(stdout.getvalue().splitlines()[0].split(':',1)[1].strip())))
                original,expected=repeats[0]
                def equivalent(raw,validation):
                    # Six-thread RF floating-point summation is not guaranteed
                    # byte-deterministic. Labels/columns stay exact; numeric
                    # equality is checked at a fixed roundoff-only tolerance.
                    first=pd.read_csv(io.BytesIO(original));second=pd.read_csv(io.BytesIO(raw))
                    pd.testing.assert_frame_equal(first,second,check_exact=False,rtol=0,atol=1e-12)
                    if abs(validation-expected)>1e-12:raise ValueError('RF validation differs beyond roundoff')
                for raw,value in repeats:equivalent(raw,value)
                trial=work/'single-trial';trial.mkdir()
                r.write(work/'single.json',dict(task=task,output=str(trial),spec=c.specifications(42)[0],best_validation=None))
                c.trial(work/'single.json')
                result=r.read(trial/'trial-result.json')
                equivalent((trial/'submission.csv').read_bytes(),result['validation'])
                X,y,_,_=c.data_for(task);families=[]
                with threadpool_limits(limits=6):
                    for family in c.FAMILIES:
                        spec=next(s for s in c.specifications(42) if s['family']==family)
                        model=c.pipeline_for(X,spec);model.fit(X,y);proba=model.predict_proba(X[:7])
                        if not np.isfinite(proba).all() or not np.allclose(proba.sum(axis=1),1):raise ValueError('model interface')
                        families.append(family)
                start=time.monotonic_ns();config=dict(task=task,seed=42,started_ns=start,deadline_ns=start+1200*10**9)
                cfg_sha=r.write(work/'classic-config.json',config)
                original_specs=c.specifications
                # The production module is unmodified: only this fixture's
                # in-memory parent search matrix is shortened to one RF trial.
                c.specifications=lambda seed: [original_specs(seed)[0]]
                try:c.search(work/'classic-config.json')
                finally:c.specifications=original_specs
                finish=work/'classic-finished.json'
                selected=select_incumbent(work,dict(task=task,seed=42),dict(status='completed',deadline_ns=config['deadline_ns'],
                    finished_sha256=r.sha(finish.read_bytes()),config_sha256=cfg_sha))
                if selected['index']!=0:raise ValueError('real process/promotion mismatch')
                equivalent(selected['path'].read_bytes(),selected['validation'])
                if r.read(finish)['attempts']!=1:raise ValueError('fixture child loop')
                proofs.append(dict(task=task,RF_submission_and_validation_equivalent_atol=1e-12,families=families,
                    original_RF_repeats=3,original_RF_distinct_submission_hashes=len({r.sha(raw) for raw,_ in repeats}),
                    original_RF_validation_range=max(v for _,v in repeats)-min(v for _,v in repeats),
                    actual_child_trials=1,incumbent_selection_verified=True))
        finally:os.chdir(old)
    proof=dict(status='PASS',utc=r.now(),prepared_sha256=r.sha((root/'prepared.json').read_bytes()),unit_tests=unit_result.testsRun,
        verifier_sha256=r.sha(Path(__file__).read_bytes()),unit_source_sha256=r.sha(Path(__file__).with_name('test_classic_control_20260914.py').read_bytes()),
        synthetic_actual_execution=proofs,api_calls=0,gpu_jobs=0,protected_data_opened=False,
        note='Synthetic CPU wiring only, not model acceptance or task quality. Actual original-image execution is the planned control.')
    print(json.dumps(dict(status='PASS',sha256=r.write(root/'preflight.json',proof),proof=proof)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);verify(p.parse_args().root.resolve(strict=True))
