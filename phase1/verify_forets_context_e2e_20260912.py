"""Post-terminal seed13 verification, with no model call or experiment mutation.

Check the actual two-order responses, selection and archived final submission.
An incomplete pool is a failure observation, never a cue to replay or impute.
"""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess

from verify_forets_review_final_20260912 import check_selection, SECRET
from verify_forets_review_selection_20260912 import replay, code_contrast

ROOT=Path('/research/d7/spc/yzyang4/forets-context-e2e-20260912-5xz0w6iy')
JOB='13123'
PREPARED='aa8fcffdfefe12e7bd93ce0c1925b28bc03f296b593ee6f321f1c4a7130566a1'
TREE='5950c7d3acf1e03173ba2ea7081d8ba6593279d9'
AUTH='f38b37f695e122d8f5df7a26fe781b80952708d8701dec22ab9dbca17ad70613'


def parsed_report(report):
    return {k:float(v) if isinstance(v,(bool,int,float)) else v for k,v in report.items()}


def match_archive(metric, archives):
    """Match all original report fields, including timestamp; not score alone."""
    matches=[item for item in archives if parsed_report(item[1])==metric]
    if len(matches)!=1:raise ValueError('selected report missing or ambiguous in submission archive')
    return matches[0]


def independent_rank(raw, order):
    if (raw.get('model')!='qwen/qwen3-coder-plus' or str(raw.get('provider','')).lower()!='alibaba'
        or len(raw.get('choices',[]))!=1 or raw['choices'][0].get('finish_reason')!='stop'):
        raise ValueError('incomplete/wrong-route rank')
    answer=json.loads(raw['choices'][0]['message']['content'])
    if not isinstance(answer,dict) or set(answer)!={'ranking'}:raise ValueError('ranking schema')
    ranking=answer['ranking']
    if (not isinstance(ranking,list) or any(type(i) is not int for i in ranking)
        or sorted(ranking)!=list(range(len(order)))):raise ValueError('ranking permutation')
    return [order[i] for i in ranking]


def independent_borda(ranks,n):
    if n not in (3,4) or len(ranks)!=2:raise ValueError('unplanned rank dimensions')
    for r in ranks:
        if any(type(i) is not int for i in r) or sorted(r)!=list(range(n)):raise ValueError('bad ranks')
    return [(2*n-ranks[0].index(i)-ranks[1].index(i))/2 for i in range(n)]


def main():
    if not (ROOT/'diagnostics.json').is_file():raise ValueError('whole-block closeout not available')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-nP','-j',JOB,'-o',
        'JobIDRaw,State%32,NodeList,ElapsedRaw,AllocTRES%256,User'],text=True,timeout=25,env=env).strip()
    if len(raw.splitlines())!=1:raise ValueError('ambiguous job')
    job,state,node,seconds,tres,user=raw.split('|')
    if (job!=JOB or node!='gpu28' or user!='yzyang4' or state.split()[0].rstrip('+') not in
        {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}):
        raise ValueError('not independently terminal')
    resources=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
    if resources.get('gres/gpu')!='1' or resources.get('cpu')!='6':raise ValueError('hardware contract')
    evidence={}
    def bytes_read(path):
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():raise ValueError('unsafe evidence path')
        data=path.read_bytes();evidence[str(path.relative_to(ROOT))]=hashlib.sha256(data).hexdigest();return data
    def read(path):
        data=bytes_read(path)
        if SECRET.search(data.decode()):raise ValueError('credential-shaped evidence; stop before export')
        return json.loads(data)
    prepared=read(ROOT/'prepared.json')
    if evidence['prepared.json']!=PREPARED or prepared['source_tree']!=TREE:raise ValueError('source identity')
    manifest=read(ROOT/'runtime-manifest.json');summary=read(ROOT/'final-readout/summary.json')
    expected=prepared['run_configs']
    if len(expected)!=4 or [r['run_id'] for r in expected]!=[r['run_id'] for r in summary['runs']]:
        raise ValueError('missing or reordered planned slots')
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest FROM auth').fetchall()!=[(AUTH,)]:raise ValueError('budget identity')
        calls=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if len(calls)<187 or sum(c[2] for c in calls)>4942593566:raise ValueError('lost carryover or exceeded budget')
    by_call={r[0]:r for r in calls};rows=[];pools=[];numeric=[]
    for spec,primary in zip(expected,summary['runs']):
        rid=spec['run_id'];base=ROOT/'runs'/rid;checkpoint=base/'checkpoint'
        cfg=read(ROOT/'configs'/(rid+'.json'));solver=cfg['solver']
        if (spec['seed'],solver['selector_seed'],solver['critic_top_k'],solver['num_children_to_choose'])!=(13,13,2,1):
            raise ValueError('selector config')
        nodes=[];journal=checkpoint/'journal.jsonl'
        if journal.exists():
            text=bytes_read(journal).decode()
            if SECRET.search(text):raise ValueError('credential-shaped journal')
            nodes=[json.loads(line) for line in text.splitlines() if line.strip()][1:]
        archives=[]
        # All evidence is outside the task workspace. Read only after all runs close.
        escrow=Path(cfg['task']['results_output_dir'])/'submission-escrow'
        for path in sorted(escrow.glob('grade-*')):
            if not (path/'complete.json').is_file():raise ValueError('incomplete submission archive')
            receipt=read(path/'complete.json');report=read(path/'report.json');submission=bytes_read(path/'submission.csv')
            if (hashlib.sha256(submission).hexdigest()!=receipt['submission_sha256'] or
                evidence[str((path/'report.json').relative_to(ROOT))]!=receipt['report_sha256'] or
                len(submission)!=receipt['submission_bytes']):raise ValueError('archive hash mismatch')
            archives.append((path,report))
        score=None;number=None
        if primary['comparable_final']:
            process=next(x['process_summary'] for x in manifest['runs'] if x['run_id']==rid)
            process=read(ROOT/process)
            if process['status']!='completed' or process['returncode']!=0 or process['started'] is not True:
                raise ValueError('invalid final process')
            event=read(base/'json/eval.jsonl');score=check_selection(event,nodes,spec['task'])
            if score!=primary['comparable_score']:raise ValueError('final differs from primary')
            chosen=next(n for n in nodes if n['id']==event['data']['selected_node_id'])
            archive,report=match_archive(chosen['metric_info'],archives)
            # Lazy imports and answer access occur strictly beyond the closure gate.
            import pandas as pd
            from mlebench.registry import registry
            from verify_forets_current_pool_20260912 import independent_leaf_loss,independent_accuracy
            competition=registry.set_data_dir(ROOT.parent/'mle-bench-data').get_competition(spec['task'])
            truth=pd.read_csv(competition.answers);pred=pd.read_csv(archive/'submission.csv')
            fn=independent_leaf_loss if spec['task']=='leaf-classification' else independent_accuracy
            number=fn(pred,truth)
            if not math.isfinite(number) or round(number,5)!=score or report['score']!=score:
                raise ValueError('final numerical regrade mismatch')
            numeric.append(rid)
        elif primary['comparable_score'] is not None:raise ValueError('missing final imputed')
        rows.append(dict(run_id=rid,task=spec['task'],arm=spec['arm'],seed=13,
            comparable_final=primary['comparable_final'],official_final_score=score,independent_score=number,
            archived_submissions=len(archives),executed_nodes=len(nodes)))
        directory=checkpoint/'forets-candidates-private'
        if list(directory.glob('*.lock')):raise ValueError('unfinished ledger lock')
        for path in sorted(directory.glob('batch-*.sqlite')):
            before=hashlib.sha256(bytes_read(path)).hexdigest()
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                snapshot=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
            if len(snapshot)!=1:raise ValueError('ambiguous snapshot')
            text,digest=snapshot[0]
            if hashlib.sha256(text.encode()).hexdigest()!=digest or SECRET.search(text):raise ValueError('snapshot hash/security')
            pool=json.loads(text);binding=pool['binding'];candidates=pool['candidates'];n=len(candidates);step=binding['step']
            if binding['task']!=spec['task'] or binding['selection_policy']!=spec['arm']:raise ValueError('pool binding')
            if pool['phase']!='complete':
                pools.append(dict(run_id=rid,step=step,phase=pool['phase'],completed=False));continue
            bypass=solver['skip_redundant_critic'] and spec['arm']=='critic_topk_random' and n<=2
            scores=[c['score'] for c in candidates];ranked=spec['arm']=='critic_topk_random' and not bypass
            order_invariant=None
            if ranked:
                rank_dir=checkpoint/'forets-contextual-judge-private'/f'batch-{step}'
                inp=read(rank_dir/'input.json');codes=[c['node']['code'] for c in candidates]
                if inp['codes_sha256']!=[hashlib.sha256(c.encode()).hexdigest() for c in codes]:raise ValueError('rank code mismatch')
                orders=[list(range(n)),list(reversed(range(n)))];ranks=[]
                if inp['orders']!=orders or inp['aggregation']!='two_order_borda_v1':raise ValueError('rank order contract')
                for j,order in enumerate(orders):
                    request=read(rank_dir/f'request-{j}.json');response=read(rank_dir/f'response-{j}.json')
                    shown=json.loads(request['messages'][1]['content'])['candidates']
                    if shown!=[dict(displayed_index=i,code=codes[s]) for i,s in enumerate(order)]:raise ValueError('truncated/changed rank input')
                    ranks.append(independent_rank(response,order))
                    call=by_call[f'{rid}-context-pool-{step}-order-{j}']
                    if call[1]!=rid or call[3] is None or call[4]!='settled':raise ValueError('unsettled rank')
                if independent_borda(ranks,n)!=scores:raise ValueError('actual Borda scores differ')
                done=read(rank_dir/'finished.json')
                if done['rankings']!=ranks or done['borda']!=scores:raise ValueError('rank receipt differs')
                order_invariant=set(ranks[0][:2])==set(ranks[1][:2])
            elif any(s is not None for s in scores):raise ValueError('unplanned scores')
            effective='critic_topk_random' if ranked else 'uniform_random'
            selected=replay(n,scores,effective,binding['selection_coupling'],13,spec['task'],step)
            if selected!=pool['selected']:raise ValueError('actual selection differs')
            task_calls=pool['task_calls'];original=[c for c in task_calls if c['intent']['role']=='candidate']
            if len(original)!=1 or original[0]['slot']!=selected[0] or any(c['slot']!=selected[0] or c['state']!='returned' for c in task_calls):
                raise ValueError('different actual execution')
            uniform=replay(n,None,'uniform_random',binding['selection_coupling'],13,spec['task'],step)
            pools.append(dict(run_id=rid,step=step,completed=True,pool_width=n,context_ranked=ranked,
                order_top2_invariant=order_invariant,changed_same_pool_choice=selected!=uniform,
                **code_contrast([c['node']['code'] for c in candidates],selected[0],uniform[0])))
            if hashlib.sha256(path.read_bytes()).hexdigest()!=before:raise ValueError('ledger changed during verification')
    report=dict(utc=datetime.now(timezone.utc).isoformat(),job=JOB,source_tree=TREE,seed=13,
        verification='passed',numerical_final_regrades=len(numeric),rows=rows,pools=pools,
        valid_finals=sum(r['comparable_final'] for r in rows),
        cumulative_settled_usd=str(Decimal(sum(c[3] or 0 for c in calls))/10**9),
        cumulative_accounted_usd=str(Decimal(sum(c[2] for c in calls))/10**9),
        allocation_gpu_hours=int(seconds)/3600,evidence_sha256=evidence,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Single exploratory seed; not replicated benefit or clean scaling.',
                    'Same-pool choice contrast is not the unexecuted candidate outcome.'])
    with (ROOT/'independent-context-verification.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','pools','evidence_sha256')}))


if __name__=='__main__':main()
