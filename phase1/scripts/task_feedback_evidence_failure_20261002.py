"""Read only a lifecycle-verified aborted batch; aggregate failure signatures."""
import argparse,collections,json,re
from pathlib import Path
from task_feedback_evidence_edit_readout_20261002 import ROOT,read,terminal_gate
def run(cert,h):
    terminal_gate(cert,h);plan=read(ROOT/'plan.json');rows=[]
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}';p=ep/'action-1/result.json'
        row=dict(**s,returned=p.exists(),generation_returned=(ep/'action-1/generation.private.json').exists())
        if p.exists():
            r=read(p);text=read(p.parent/'node.private.json')['terminal']
            text='\n'.join(text) if isinstance(text,list) else str(text)
            text=re.sub(r'\x1b\[[0-9;]*m','',text)
            row.update(valid=r['valid'],timed_out=r['timed_out'],execution_started=r['execution_started'],
                classes=sorted(set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception))\s*:',text))))
        else:row.update(valid=None,classes=[],scope='startup missing' if s['index']==10 else 'deadline before return')
        rows.append(row)
    terminal_gate(cert,h)
    return dict(scope='coarse error classes, no new root-cause or effect attribution; full12 denominator',rows=rows,
                counts=dict(planned=12,generations=sum(x['generation_returned'] for x in rows),returned=sum(x['returned'] for x in rows),valid=sum(x['valid'] is True for x in rows),
                    errors=dict(collections.Counter(c for x in rows for c in x['classes']))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cert',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(a.cert,a.sha)
    with a.out.open('x') as f:json.dump(r,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(r,sort_keys=True))
