"""Read-only, credential-first semantic inspection of the closed developer batch.

Never loads predictions or scorer labels. The inventory masks numbers in model
reasons and does not print metric fields. Actual code is inspected separately;
AST call counts are navigation aids, not verified semantic diagnoses.
"""
import argparse, ast, collections, hashlib, json, re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/executable-evidence-20261004-v1')
PLAN='f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,}|(?:api[_-]?key|password|secret|token)\s*[=:]\s*[\x22\x27]?[a-z0-9_./+-]{12,})')
def read(p):
    raw=p.read_bytes();assert not SECRET.search(raw),'credential-shaped data: stop before output';return json.loads(raw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def hide_numbers(s):return re.sub(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?','[NUMBER]',s)
def accepted_content(action):
    node=action/'node.private.json'
    if node.exists():return read(node),sha(node),'returned'
    fmt=action/'format.json';generation=action/'generation.private.json'
    if not fmt.exists() or read(fmt)['status']!='PASS' or not generation.exists():return None,None,None
    raw=read(generation)['response'];parts=re.findall(r'\x60\x60\x60python\s*\n(.*?)\x60\x60\x60',raw,re.S)
    assert len(parts)==1 and raw.count(chr(96)*3)==2
    ast.parse(parts[0])
    return dict(code=parts[0],plan=raw.split(chr(96)*3,1)[0],terminal='[No returned execution output; do not infer test evidence.]'),sha(generation),'accepted_without_return'

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['inventory','detail','bundle']);p.add_argument('--index',type=int);p.add_argument('--step',type=int);p.add_argument('--terminal',action='store_true');p.add_argument('--stop',type=int);a=p.parse_args()
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    plan=read(R/'plan.json')
    if a.mode=='bundle':
        assert 0<=a.index<a.stop<=18
        programs={};actions=[]
        for row in plan['schedule']:
            if not a.index<=row['index']<a.stop:continue
            for step in range(1,7):
                action_dir=R/f'episode-{row["index"]}/action-{step}'
                n,source_sha,state=accepted_content(action_dir)
                if n is None:continue
                h=hashlib.sha256(n['code'].encode()).hexdigest()
                programs[h]=n['code']
                action=dict(index=row['index'],arm=row['arm'],task=row['task'],step=step,code_sha256=h,source_sha256=source_sha,return_state=state,reason_numbers_masked=hide_numbers(n['plan']))
                if a.terminal:
                    action['agent_visible_terminal_numbers_masked']=hide_numbers(n['terminal'][-12000:])
                    action['terminal_total_chars']=len(n['terminal'])
                    action['terminal_prefix_chars_not_delivered']=max(0,len(n['terminal'])-12000)
                actions.append(action)
        print(json.dumps(dict(actions=actions,programs=programs,scope='All accepted action code/reasons in specified index range; identical code shown once. No numeric result fields. Qualitative same-analyst review, not blinded.'),ensure_ascii=False));return
    if a.mode=='detail':
        assert 0<=a.index<18 and 0<=a.step<=6
        n,source_sha,state=accepted_content(R/f'episode-{a.index}/action-{a.step}');assert n is not None
        out=dict(index=a.index,step=a.step,source_sha256=source_sha,return_state=state,reason=hide_numbers(n['plan']),code=n['code'])
        if a.terminal:
            out['agent_visible_terminal_numbers_masked']=hide_numbers(n['terminal'][-12000:])
            out['terminal_total_chars']=len(n['terminal'])
            out['terminal_prefix_chars_not_delivered']=max(0,len(n['terminal'])-12000)
        print(json.dumps(out,ensure_ascii=False));return
    inventory=[]
    for row in plan['schedule']:
        ep=R/f'episode-{row["index"]}';actions=[]
        for step in range(1,7):
            d=ep/f'action-{step}';np=d/'node.private.json';rp=d/'result.json'
            if not np.exists():
                actions.append(dict(step=step,returned=False,generated=(d/'generation.private.json').exists(),format=read(d/'format.json') if (d/'format.json').exists() else None));continue
            n=read(np);r=read(rp);tree=ast.parse(n['code']);calls=collections.Counter(ast.unparse(z.func) for z in ast.walk(tree) if isinstance(z,ast.Call))
            actions.append(dict(step=step,returned=True,kind=r['kind'],execution_success=r['execution_success'],exit_code=r['exit_code'],timed_out=r['timed_out'],
                reason_numbers_masked=hide_numbers(n['plan']),code_sha256=r['code_sha256'],lines=len(n['code'].splitlines()),calls=dict(calls),
                terminal_chars=len(n['terminal']),exception_names=re.findall(r'(?m)^([A-Za-z]+Error|[A-Za-z]+Exception):',n['terminal'])))
        inventory.append(dict(index=row['index'],task=row['task'],arm=row['arm'],seed=row['seed'],actions=actions))
    print(json.dumps(dict(plan_sha256=PLAN,scope='All18 assigned; no quality fields or predictions read. Number masking only aids pre-readout mechanism review; same analyst/arm visible.',rows=inventory),ensure_ascii=False))
if __name__=='__main__':main()
