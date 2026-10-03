"""Fixed-prediction query sensitivity, not heldout statistical confirmation."""
import argparse, ast, hashlib, importlib.util, json
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');P=B/'opportunity-information-20261003-v2';R=B/'executable-evidence-20261004-v1'
SOURCE='e745b1877c7885665720347eb8e6fb89769281e12ce53e49d8a19da68dfb3a89'
PLAN='f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load():
    p=R/'query_sensitivity_frozen.py';s=importlib.util.spec_from_file_location('evidence_sensitivity',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def freeze():
    src=P/'opportunity_information_sensitivity_20261003.py';assert sha(src)==SOURCE and sha(R/'plan.json')==PLAN
    text=src.read_text()
    for a,b,n in [
        (str(P),str(R),1),
        ('6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f',PLAN,1),
        ('len(pairs)!=2','len(pairs)!=3',1),
        ('np.mean([scores','np.median([scores',1),
        ('104050','106050',3),
        ('Shared query resample across both generation seeds and all arms. Average two within-seed final retained-score differences; same as median with two seeds.',
         'Shared query resample across all three generation seeds and all arms. Median of three within-seed final retained-score differences. No resampling of generation seeds or tasks.',1)]:
        assert text.count(a)==n,(a,text.count(a));text=text.replace(a,b)
    ast.parse(text)
    with (R/'query_sensitivity_frozen.py').open('x') as f:f.write(text)
    load().freeze()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','analyze']);q=a.parse_args()
    if q.mode=='freeze':freeze()
    else:load().analyze()
