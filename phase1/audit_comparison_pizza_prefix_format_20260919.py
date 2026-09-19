"""Match exact native humanize trailer, preserving original false gate."""
import hashlib,json,tarfile
from pathlib import Path,PurePosixPath
from run_comparison_pizza_prefix_20260919 import old,prepared,RUNS,TASK
from audit_comparison_third_prefix_20260919 import core
ROOT=old.BASE/'comparison-pizza-prefix-20260919-0guhqznb'
SUMMARY='b3fff2aa4228b7b09e82296c0f3929e4fa7b9083a6bb510cdfcef63f28ddaa29'

def strip_exact(error,seconds,limit,formatter):
    trailer=f'Execution time: {formatter(seconds)} (time limit is {formatter(limit)}).'
    return error[:-len(trailer)].rstrip() if error.endswith(trailer) else error

def main():
    import humanize
    p=prepared(ROOT);s=old.read(ROOT/'summary.json',SUMMARY);times={}
    wanted={r['node'] for r in p['rows']}
    with tarfile.open(old.INPUT/f'archives/{TASK}.tar.gz','r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile() or path.name!='journal.jsonl' or old.sha(str(path.parent.parent).encode())[:16] not in RUNS.values():continue
            for raw in archive.extractfile(member):
                if old.SECRET.search(raw):raise ValueError('credential-first')
                node=json.loads(raw)
                if node.get('id') in wanted:times[node['id']]=node['exec_time']
    if set(times)!=wanted:raise ValueError('original duration identity')
    rows=[]
    for row in p['rows']:
        observed=s['rows'][row['index']];log=ROOT/f'output-{row["index"]}.private.log'
        if old.sha(log.read_bytes())!=observed['log_sha256']:raise ValueError('fresh log identity')
        original=strip_exact(row['historical_error'],times[row['node']],7200,humanize.naturaldelta)
        same=original==core(log.read_text()) and observed['exit_code']==1 and not observed['timed_out']
        rows.append(dict(seed=row['seed'],original_gate=observed['prefix_reproduced'],exact_native_trailer_removed=original!=row['historical_error'],same_core_error=same))
    result=dict(role='posthoc_exact_native_format_supplement_not_overwrite',source_summary_sha256=SUMMARY,
        formatter='humanize.naturaldelta',reader_sha256=old.sha(Path(__file__).read_bytes()),rows=rows,all_core_errors_match=all(r['same_core_error'] for r in rows),
        cached_outcomes_opened=False,labels_opened=False)
    old.write(ROOT/'prefix-format-supplement.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
