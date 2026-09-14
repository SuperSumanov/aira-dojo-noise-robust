"""Local derived evidence only: no fitting, data execution or outcome selection."""
import hashlib,json,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCES={
 'old':('results/forets_cheap_e2e_s46_s47_20260914/cheap-selector-summary.json','a2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82'),
 'new':('results/forets_class_gate_s48_20260914/cheap-selector-summary.json','aa9c4610c0c6bc91011fca4e0edc8a6f6a8f7459351978bc73298d1a70258609'),
 'replay':('results/forets_first_pool_replay_20260914/summary.json','e1a07d80bf396d2f02c81f22f4dbd4e8b534a02f79ae2870fc29e0fa380aef28')}
ARMS=('uniform','short_code','learned_validity','class_gate')
def sha(b):return hashlib.sha256(b).hexdigest()

def opportunity(pairs):
    counts={'pools':len(pairs),'both_invalid':0,'mixed_validity':0,'both_valid':0,'unknown':0}
    picked={a:0 for a in ARMS}; missed_all=0
    for p in pairs:
        ys=p['labels']
        if len(ys)!=2 or any(y is not None and type(y) is not bool for y in ys):raise ValueError('two Boolean labels')
        choices=p['choices']
        if set(choices)!=set(ARMS) or any(type(c) is not int or c not in (0,1) for c in choices.values()):raise ValueError('choice shape')
        if any(y is None for y in ys):counts['unknown']+=1;continue
        total=sum(ys);counts[['both_invalid','mixed_validity','both_valid'][total]]+=1
        for a in ARMS:picked[a]+=int(ys[choices[a]])
        if total>0 and not any(ys[choices[a]] for a in ARMS):missed_all+=1
    return dict(**counts,known_pools=counts['pools']-counts['unknown'],any_valid_known_pools=counts['mixed_validity']+counts['both_valid'],selected_valid_by_policy=picked,valid_opportunities_missed_by_all=missed_all)

def main():
    data={}
    for name,(path,h) in SOURCES.items():
        b=(ROOT/path).read_bytes()
        if sha(b)!=h:raise ValueError('source hash')
        data[name]=json.loads(b)
    if len(data['old']['rows'])!=12 or len(data['new']['rows'])!=8 or len(data['replay']['rows'])!=24 or len(data['replay']['pairs'])!=12:raise ValueError('all fixed denominators')
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        for arm in ARMS[:3]:
            rr=[r for r in data['old']['rows'] if (r['task'],r['arm'])==(task,arm)]
            if len(rr)!=2 or not all(r['technical_eligible'] and r['action_valid'] for r in rr):raise ValueError('old exact eligible repeats')
            xs=[r['action_score'] for r in rr]
            groups.append(dict(task=task,arm=arm,seeds=[r['seed'] for r in rr],median=statistics.median(xs),sample_sd=statistics.stdev(xs)))
    new=data['new'];pairs=data['replay']['pairs']
    gate=next(r for r in new['rows'] if (r['task'],r['arm'])==('spaceship-titanic','class_gate'))
    comparison=next(r for r in new['rows'] if (r['task'],r['arm'])==('spaceship-titanic','learned_validity'))
    if not(gate['technical_eligible'] and comparison['technical_eligible']):raise ValueError('known new contrast')
    out=dict(role='descriptive_evidence_synthesis_not_confirmatory_pooling',sources={k:h for k,(_,h) in SOURCES.items()},old_groups=groups,
        first_pool_opportunity=opportunity(pairs),retest_known=sum(p['original_known_retest'] for p in pairs),retest_disagreements=sum(p['original_validity_disagreements'] for p in pairs),
        new_space_gate_vs_continuous_percentage_points=(gate['action_score']-comparison['action_score'])*100,
        new_main_investment_gate=new['investment_gate'],new_technical_eligible=sum(r['technical_eligible'] for r in new['rows']),
        new_secondary_short_vs_uniform=new['secondary_short_code'],
        gpu_hours_old_new_replay=[data[n]['allocation_gpu_hours'] for n in ('old','new','replay')],
        api_calls=0,gpu_jobs=0,models_fit=0,script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Old simultaneous versus new sequential schedules are not causally pooled. Replay first pools only, no debug; binary validity opportunity is not a final-score ceiling or policy regret. Unknown retained, single new seed has no variance estimate.')
    raw=(json.dumps(out,sort_keys=True,allow_nan=False)+'\n').encode()
    dest=ROOT/'results/forets_class_gate_s48_20260914/evidence-synthesis.json'
    with dest.open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**out)))
if __name__=='__main__':main()
