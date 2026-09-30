"""Run the public synthetic native-parser regressions; never run a candidate."""
import argparse,hashlib,importlib.util,json,sys,unittest
from pathlib import Path
import black


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    spec=importlib.util.spec_from_file_location('parser_fix_test_suite',a.bundle/'test_parser_fix.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    suite=unittest.defaultTestLoader.loadTestsFromModule(mod)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'python':sys.version,'black':black.__version__,
            'source_file_sha256':{p.relative_to(a.bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(a.bundle.rglob('*.py'))},
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'Synthetic regression and real task admission with intercepted interpreter. No candidate execution or MLE score.'}
    with a.output.open('x') as f:json.dump(record,f,indent=2)
    print(json.dumps({k:v for k,v in record.items() if k!='source_file_sha256'}))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
