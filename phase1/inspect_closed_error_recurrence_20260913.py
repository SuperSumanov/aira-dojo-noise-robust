"""Deduplicate categorical failure cases and extract bounded API-error exemplars."""
from collections import Counter
import json
from pathlib import Path
import re
from forets_environment_build_20260912 import read,write,encode,sha
from audit_closed_error_families_20260913 import BASE,ROOTS,SECRET,ANSI

SUMMARY=BASE/'forets-wallclock-20260912-5_czzimk/closed-error-families.json'
SUMMARY_SHA='fbea5f58486ea518255e6227f5d26014a5e5b0d138c78ce335b66086e3c1ef2b'

def main():
    source=read(SUMMARY,SUMMARY_SHA);rows=[];keywords=Counter();keyword_runs={};paths={}
    for p in source['proof']:paths[(p['root'],p['run_id'])]=p['journal_sha256']
    byrun={}
    for r in source['rows']:
        if r['exit_nonzero'] and ('categorical_new_fill_value' in r['message_families'] or 'fit_or_train_keyword' in r['message_families']):
            byrun.setdefault((r['root'],r['run_id']),[]).append(r)
    for (root,rid),targets in byrun.items():
        path=BASE/root/'runs'/rid/'checkpoint/journal.jsonl';raw=path.read_bytes()
        if sha(raw)!=paths[(root,rid)]:raise ValueError('closed journal changed')
        safe=SECRET.sub('[REDACTED]',raw.decode());nodes=[json.loads(line) for line in safe.splitlines()]
        for r in targets:
            found=[n for n in nodes if n['step']==r['step']]
            if len(found)!=1:raise ValueError('unique observed node')
            node=found[0];term=node.get('term_out') or '';term='\n'.join(term) if isinstance(term,list) else term;term=ANSI.sub('',term)
            if 'categorical_new_fill_value' in r['message_families']:
                rows.append(dict(root=root,run_id=rid,step=r['step'],task=r['task'],code_sha256=sha(node['code'].encode()),
                    operators=[x for x in node.get('operators_used',[]) if isinstance(x,str) and re.fullmatch('[A-Za-z0-9_.-]{1,80}',x)]))
            if 'fit_or_train_keyword' in r['message_families']:
                # Only callable/argument identifiers, never arbitrary error text.
                pairs=re.findall(r"\b([A-Za-z_][A-Za-z0-9_.]*)\(\) got an unexpected keyword argument ['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",term)
                for pair in set(pairs):
                    keywords[pair]+=1;keyword_runs.setdefault(pair,set()).add((root,rid))
        if sha(path.read_bytes())!=paths[(root,rid)]:raise ValueError('journal mutation')
    result=dict(role='closed_development_error_recurrence_not_repair_efficacy',source_summary_sha256=SUMMARY_SHA,
        categorical=dict(occurrences=len(rows),distinct_code_hashes=len({r['code_sha256'] for r in rows}),distinct_runs=len({r['run_id'] for r in rows}),
            tasks=sorted({r['task'] for r in rows}),protocols=len({r['root'] for r in rows}),rows=rows),
        keyword_examples=[dict(callable=k[0],argument=k[1],occurrences=v,distinct_runs=len(keyword_runs[k])) for k,v in sorted(keywords.items())],
        limitations='Code uniqueness is byte-level only, not independent strategies. All categorical cases are a single-task finding; heterogeneous protocols, incomplete saved journals.')
    digest=write(SUMMARY.with_name('closed-error-recurrence.json'),encode(result));print(json.dumps(dict(summary_sha256=digest,**result)))

if __name__=='__main__':main()
