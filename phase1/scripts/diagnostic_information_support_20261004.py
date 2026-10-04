"""Reuse frozen transport/readout/verifier with new observation-only conditions."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

B = Path('/research/d7/spc/yzyang4')
P = B/'opportunity-information-20261003-v2'
R = B/'diagnostic-information-20261004-v1'
PY = B/'venvs/aira/bin/python'
OLD_PLAN = '6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
TEMPLATES = {
    'cpu': ('opportunity_information_cpu_20261003.py', '4e270eee98dad9cd339f4e396aefdab2bc17dfa37006123f829e6b9a8304f89b'),
    'readout': ('opportunity_information_readout_20261003.py', '73959a378739d913bf80b32c401b52b133555cee5c43a22f94df72605595c75e'),
    'verifier': ('opportunity_information_verify_20261003.py', '6c110ac0fbcaadc130a6d96e13a526cbfad3bfd14dcfb100823918381fa49f77')}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_bytes())


def write(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)


def replace(text, before, after, count=1):
    assert text.count(before) == count, (before, text.count(before))
    return text.replace(before, after)


def module(role):
    path = R/'analysis_templates'/f'{role}.py'
    spec = importlib.util.spec_from_file_location('diagnostic_information_'+role, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def prepare():
    assert not (R/'launch.json').exists()
    plan = sha(R/'plan.json')
    directory = R/'analysis_templates'
    directory.mkdir()
    records = {}
    for role, (name, expected) in TEMPLATES.items():
        source = P/name
        assert sha(source) == expected
        text = replace(source.read_text(), str(P), str(R))
        if role == 'cpu':
            text = replace(text, '==19453', '==19463')
            text = replace(text,
                "assert all((x.FACTS[task_index] in p)==(arm=='B') and (x.SPECS[task_index] in p)==(arm=='C') for p in prompts)",
                "assert all(x.advice(s) in p and ('AUXILIARY PUBLIC-CV OBSERVATION' in p)==(arm!='A') and f'CURRENT MODEL CALL: {i+1} of 4.' in p for i,p in enumerate(prompts))")
        else:
            text = replace(text, OLD_PLAN, plan)
            text = text.replace('numerical_B_gate', 'numerical_C_gate')
        if role == 'readout':
            text = replace(text,
                "bs=[x for x in stats if x['contrast']=='B_minus_A']\n    gate=len(bs)==2 and all(x['paired']==2 and x['median']>0 and x['negative']==0 and any(r['arm']=='B' and r['task']==x['task'] and (r['improved_candidates'] or 0)>0 for r in runs) for x in bs)",
                "cs=[x for x in stats if x['contrast'] in ('C_minus_A','C_minus_B')]\n    gate=len(cs)==4 and all(x['paired']==2 and x['median']>=.002 and x['negative']==0 and any(r['arm']=='C' and r['task']==x['task'] and (r['improved_candidates'] or 0)>0 for r in runs) for x in cs)")
            marker = "    rr[1]['initial']=None;assert not compare(rr)[2]"
            extra = """    import copy
    for condition in ('tie_A','tie_B','one_negative','different_initial','small_gain'):
        bad=copy.deepcopy(rr)
        if condition in ('tie_A','tie_B','small_gain'):
            for r in bad:
                if r['arm']=='C':r['gain']={'tie_A':0.,'tie_B':.1,'small_gain':.101}[condition]
        elif condition=='one_negative':bad[2]['gain']=-.01
        else:bad[2]['initial_sha256']='different'
        assert not compare(bad)[2],condition
    rr[1]['initial']=None;assert not compare(rr)[2]"""
            text = replace(text, marker, extra).replace('fixtures=2', 'fixtures=7')
        if role == 'verifier':
            text = replace(text,
                "assert (x.FACTS[s['start']] in q['prompt'])==(s['arm']=='B') and (x.SPECS[s['start']] in q['prompt'])==(s['arm']=='C')",
                "assert x.COMMON in q['prompt'] and x.advice(s) in q['prompt'] and ('AUXILIARY PUBLIC-CV OBSERVATION' in q['prompt'])==(s['arm']!='A') and f'CURRENT MODEL CALL: {step} of 4.' in q['prompt']")
            text = replace(text,
                "gate=(R/'all-closed.json').exists() and all(t['paired']==2 and t['median']>0 and t['negative']==0 and any(r['arm']=='B' and r['task']==t['task'] and (r['improved'] or 0)>0 for r in actual) for t in stats if t['contrast']=='B_minus_A')",
                """gate=(R/'all-closed.json').exists() and len(actual)==12
    task_names=sorted({r['task'] for r in actual})
    gate=gate and len(task_names)==2
    for task_name in task_names:
        ps=[p for p in pairs if p['task']==task_name]
        if len(ps)!=2 or not all(p['comparable'] for p in ps):gate=False;continue
        for contrast in ('C_minus_A','C_minus_B'):
            values=[p[contrast] for p in ps]
            gate=gate and sum(values)/2>=.002 and min(values)>=-1e-12
        gate=gate and any(r['task']==task_name and r['arm']=='C' and (r['improved'] or 0)>0 for r in actual)""")
        ast.parse(text)
        target = directory/f'{role}.py'
        with target.open('x') as f:
            f.write(text)
        records[role] = sha(target)
    module('readout').freeze()
    write(R/'analysis-freeze.json', dict(plan_sha256=plan, files=records, templates=TEMPLATES,
        script_sha256=sha(__file__), mechanism=[
            'All12 assigned trajectories retained, including parsing/timeouts/failures.',
            'Check whether actual next code and prediction changes differ; comments/reasoning alone are insufficient.',
            'Does C exceed no-report A, not only unaligned-report B? Correcting harmful advice need not add value.',
            'No automatic correction or novelty claim; researcher-supplied packet selection is disclosed.',
            'Qualitative review sees conditions; no independent blinded semantic-annotation claim.',
            'No extra seeds, prompts or replacements after outcomes. A positive numeric gate is exploratory, not significance.']))
    print(json.dumps(dict(status='ANALYSIS_FROZEN', plan_sha256=plan, files=records)))


def check():
    receipt = read(R/'analysis-freeze.json')
    assert receipt['plan_sha256'] == sha(R/'plan.json') and receipt['script_sha256'] == sha(__file__)
    for role, expected in receipt['files'].items():
        assert sha(R/'analysis_templates'/f'{role}.py') == expected


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'cpu', 'launch', 'status', 'analyze', 'verify'])
    args = parser.parse_args()
    if args.mode == 'prepare':
        return prepare()
    check()
    if args.mode == 'cpu':
        subprocess.run([str(PY), '-B', str(R/'analysis_templates/cpu.py')], check=True)
    elif args.mode == 'launch':
        cpu = read(R/'transport-loop-cpu.json')
        assert cpu['status'] == 'PASS' and cpu['plan_sha256'] == sha(R/'plan.json')
        assert cpu['script_sha256'] == sha(R/'analysis_templates/cpu.py')
        assert not (R/'submit-intent.json').exists() and not (R/'launch.json').exists()
        write(R/'budget-approval.json', dict(approved=True, gpu_hours_cap=6, plan_sha256=sha(R/'plan.json'),
            basis='User2026-10-04HKT explicitly requested another complete four-hour experimental window with assistant judgment. Assistant previewed two tasks/three observation conditions/two paired seeds,12 runs,600sec/fourcalls each,four3090 at most90min,6GPUh,no paid API/base training. Single bounded conditional-information batch.'))
        subprocess.run([str(PY), '-B', str(R/'task_feedback_real_20261001.py'), 'submit'], check=True)
    elif args.mode == 'verify':
        module('verifier').main()
    else:
        getattr(module('readout'), args.mode)()


if __name__ == '__main__':
    main()
