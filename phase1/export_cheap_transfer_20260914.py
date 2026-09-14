"""Export only named, hash-checked, credential-scanned aggregate artifacts."""
from collections import Counter,defaultdict
import io,json,tarfile
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
DATA={
 'scope':('88v5m9dr',('ec995b738f2c49fb57b6e0e8cb3f7c26833f20a5ecf8db93a226963e60483cfb','9154d48fb80fe7581de485bdd87afddf6df9648afa61a482da72b870b9700662','9938703b5f96b98f142114bee71d6d58431558cefc8af96b7f4443829ef2d51c','264a2bc775d43d3f9bb5355f0afc21ef4470a32cfd5f4a7a844870299850cd7c')),
 'action':('7wzrny21',('56b9ae5c0aed055008b44bc294f73cb9f0ef82263b097ce403a8f81dbf9099e3','6e3d13fefa071021fa213712d620efc484a4c4f9d188672989a1990d47bcda35','f66697e7e22e252a605d2ee195eafaa1986a424f0bc2d127d7ccfbabc310d68c','8bc125e69df1e438b634a312f50d1470e33bc51aa8400898a81f4660c60d1853')),
 'width':('2z2s7sc3',('fb3ea5381223d792d642464861f555a0a301a610ff77dd24d78c4af92cce5072','68a23b520db6f00a3cfd65605960dfd1f5edfcb5a05b3cd032d54e13714f0d2c','00b7bd5c28b48d15bc34311f348fb035b4c81eb96f359e051cda5bcbd256bb0c','e7c7ed2880ffb61cafc210ed14a8d013c8b05e1186c1469142f6ecae7f1942bb')),
 'memory':('103zf3nb',('e7ecb9b4b250845511c35efff77379ad6016b84b562e4e6d0032faac9bb0aa98','4f14d069f46525164a54616620e707cdd1d185f413a6762a366c57d54b73a3a3','d2fe3fb28ec5306b1a95058a5f88e9625382043b9a4478ae04f762c00462cbec','3dd5fe7cace162974c6f48a2bf79640b67af207974296710336791715467e7c0'))}
FILES=('cheap-selector-transfer.json','cheap-selector-transfer-independent.json','cheap-transfer-missingness.json','cheap-rule-baselines.json')
def main():
    export={};primary=[];planned=0;rule_counts=Counter();known_critical=0;point_run_gains=defaultdict(list);pairkeys=Counter();allbounds=[];unknown=0
    for cohort,(suffix,hashes) in DATA.items():
        root=BASE/('forets-wallclock-20260912-'+suffix);values=[]
        for name,h in zip(FILES,hashes):
            raw=checked(root/name,h);export[cohort+'/'+name]=raw;values.append(json.loads(raw))
        point,independent,missing,rules=values
        if independent['summary_sha256']!=hashes[0] or rules['source_missingness_sha256']!=hashes[2]:raise ValueError('verification graph')
        planned+=len(point['runs'])
        for row in point['rows']:
            if row['technical_eligible'] and not row['duplicate_within_run']:
                primary.append(row);point_run_gains[cohort+'/'+row['run']].append(row['hgb_minus_short']);pairkeys[tuple(row['code_sha256'])]+=1
        for row in missing['rows']:
            if row['technical_eligible'] and not row['duplicate_within_run']:allbounds.append(row);unknown+=not row['fully_known']
        for row in rules['rows']:
            if row['technical_eligible'] and not row['duplicate_within_run'] and row['fully_known'] and row['labels'][0]!=row['labels'][1]:
                known_critical+=1;rule_counts['learned']+=row['hgb_validity']
                for name,value in row['comparators'].items():rule_counts[name]+=value['validity']
    critical=[r for r in primary if r['discordant']]
    if len(critical)!=known_critical:raise ValueError('broader known pool denominator changed; report separately')
    stats=dict(role='transparent_counts_not_pooled_confirmatory_estimate',planned_source_runs=planned,
        runs_with_primary_complete_pairs=len(point_run_gains),primary_complete_pairs=len(primary),discordant_pairs=len(critical),
        valid_choice_totals_on_discordant=dict(rule_counts),hgb_vs_short_pair_wins=sum(r['hgb_minus_short']>0 for r in primary),
        hgb_vs_short_pair_losses=sum(r['hgb_minus_short']<0 for r in primary),hgb_vs_short_run_wins=sum(sum(v)>0 for v in point_run_gains.values()),
        hgb_vs_short_run_losses=sum(sum(v)<0 for v in point_run_gains.values()),hgb_vs_short_run_ties=sum(sum(v)==0 for v in point_run_gains.values()),
        exact_unordered_pair_duplicates_across_all_primary_runs=sum(n-1 for n in pairkeys.values()),
        all_applicable_primary_pairs=len(allbounds),unknown_pairs=unknown,
        source_cohorts=list(DATA),no_current_e2e_results=True,
        limitations='Post-hoc transfer after model selection on older development targets. Correlated pairs, only two tasks; completed-width-two selection and source distribution limits. Pooled counts are not a macro effect, significance claim or E2E gain. See protocol/task-specific bounds and null/unknown groups.',
        exporter_sha256=sha(Path(__file__).read_bytes()))
    export['aggregate.json']=(json.dumps(stats,sort_keys=True,allow_nan=False)+'\n').encode()
    manifest={n:dict(sha256=sha(raw),bytes=len(raw)) for n,raw in export.items()}
    export['manifest.json']=(json.dumps(manifest,sort_keys=True)+'\n').encode()
    dest=Path(__file__).with_name('cheap-transfer-public-20260914.tar')
    with dest.open('xb') as stream,tarfile.open(fileobj=stream,mode='w') as archive:
        for name,raw in sorted(export.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;info.mtime=0;archive.addfile(info,io.BytesIO(raw))
    print(json.dumps(dict(path=str(dest),sha256=sha(dest.read_bytes()),export_files=len(export),aggregate=stats)))
if __name__=='__main__':main()
