"""Header-only evaluator interface check; never loads any truth rows."""
import csv,json,os
from pathlib import Path
os.environ['PYTHON_DOTENV_DISABLED']='1'
from mlebench.registry import registry

base=Path('/research/d7/spc/yzyang4/mle-bench-data')
competition=registry.set_data_dir(base).get_competition('spooky-author-identification')
expected={'id','EAP','HPL','MWS'}
records=[]
for role,path in [('answer_schema',competition.answers),('public_submission_schema',base/'spooky-author-identification/prepared/public/sample_submission.csv')]:
    with Path(path).open(newline='') as handle:
        header=next(csv.reader(handle))
    if set(header)!=expected:raise ValueError('independent numerical interface does not match task schema')
    records.append(dict(role=role,columns=header,truth_rows_loaded=0))
print(json.dumps(dict(status='SCHEMA_PASS',records=records)))
