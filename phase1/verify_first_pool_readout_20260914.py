"""Independent planned-case, CSV, native hardware and same-pool arithmetic audit."""
import argparse,csv,json,math,statistics
from pathlib import Path
from run_first_pool_replay_20260914 import prepared,read,checked,sha,write
def comparisons(policies,rows):
    if len(rows)!=24 or {r['index'] for r in rows}!=set(range(24)):raise ValueError('all24 rows')
    for r in rows:
        if r['valid'] is not None and type(r['valid']) is not bool:raise ValueError('validity type')
        if r['valid']:
            if type(r['score']) not in (int,float) or not math.isfinite(r['score']):raise ValueError('finite score')
        elif r['score'] is not None:raise ValueError('missing score imputed')
    pairs=[]
    for policy in policies:
        rr={r['slot']:r for r in rows if r['source_run_id']==policy['source_run_id']}
        if len(rr)!=2:raise ValueError('same pool pair')
        cs=[]
        for arm in ('short_code','learned_validity','class_gate'):
            for baseline in ('uniform','short_code','learned_validity'):
                if baseline==arm:continue
                x,y=rr[policy['choices'][arm]],rr[policy['choices'][baseline]];sign=None;gain=None
                if x['valid'] is not None and y['valid'] is not None:
                    if x['valid'] and y['valid']:
                        gain=(y['score']-x['score']) if policy['task']=='leaf-classification' else (x['score']-y['score'])
                        sign=int(gain>0)-int(gain<0)
                    else:sign=int(x['valid'])-int(y['valid'])
                cs.append(dict(arm=arm,baseline=baseline,sign=sign,gain=gain))
        old=[(a,rr[i]['valid']) for i,a in enumerate(policy['original_initial_labels']) if a is not None and rr[i]['valid'] is not None]
        pairs.append(dict(**policy,labels=[rr[i]['valid'] for i in (0,1)],grades=[rr[i]['score'] for i in (0,1)],contrasts=cs,
            original_known_retest=len(old),original_validity_disagreements=sum(bool(a)!=b for a,b in old)))
    return pairs
def main(root):
    p=prepared(root);finish=read(root/'readout-finished.json');s=read(root/'summary.json',finish['summary_sha256'])
    checked(root/'runs.csv',finish['csv_sha256'])
    if comparisons(p['policies'],s['rows'])!=s['pairs']:raise ValueError('independent paired effects')
    for g in s['groups']:
        cc=[c for q in s['pairs'] if q['task']==g['task'] for c in q['contrasts'] if (c['arm'],c['baseline'])==(g['arm'],g['baseline'])]
        if len(cc)!=g['runs']:raise ValueError('group denominator')
        for key,sign in [('wins',1),('ties',0),('losses',-1),('unknown',None)]:
            if sum(c['sign']==sign for c in cc)!=g[key]:raise ValueError('group sign')
        vv=[c['gain'] for c in cc if c['gain'] is not None]
        if g['conditional_both_valid_median_gain']!=(statistics.median(vv) if vv else None) or g['sample_sd_conditional_gain']!=(statistics.stdev(vv) if len(vv)>1 else None):raise ValueError('group dispersion')
    with (root/'runs.csv').open(newline='') as f:csvrows=list(csv.DictReader(f))
    if len(csvrows)!=24:raise ValueError('CSV denominator')
    physical={1:set(),2:set()};native=0
    for row,cr,planned in zip(s['rows'],csvrows,p['rows']):
        if set(cr)!=set(row) or any(cr[k]!=('' if v is None else str(v)) for k,v in row.items()):raise ValueError('CSV binding')
        if any(row[k]!=v for k,v in planned.items()):raise ValueError('planned case')
        if row['status']=='returned':
            r=read(root/f'result-{row["index"]}.json',s['proofs'][f'result-{row["index"]}.json'])
            binding=read(root/f'identity-{row["index"]}.native-binding.json',r['native_binding_sha256']);ident=binding['native_identity']
            launch=read(root/f'launch-{row["block"]}.json')
            if ident['job']!=launch['job'] or ident['node']!='gpu28' or ident['device_count']!=1 or '3090' not in ident['device_name'] or not binding['namespace']['exact_device_namespace']:raise ValueError('native task environment')
            physical[row['block']].add(ident['selected_uuid']);native+=1
            if row['valid'] and (r['exit_code']!=0 or r['timed_out'] or r['submission_sha256'] is None):raise ValueError('valid noncompleted case')
    if any(len(v)>1 for v in physical.values()):raise ValueError('physical device changed in block')
    out=dict(status='independent_same_pool_csv_effects_hardware_verified',summary_sha256=finish['summary_sha256'],rows=24,pools=len(p['policies']),native_receipts=native,
        valid=sum(r['valid'] is True for r in s['rows']),unknown=sum(r['valid'] is None for r in s['rows']),script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Original trusted grader versus independent numerical score checked in primary readout; this pass checks paired arithmetic, provenance and hardware, not another execution.')
    print(json.dumps(dict(sha256=write(root/'independent.json',out),**out)))
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
