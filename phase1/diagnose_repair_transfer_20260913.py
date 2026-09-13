"""Closed T1 error transitions, all planned arms; no raw code/output export."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from prepare_repair_transfer_20260913 import SECRET

ROOT = Path('/research/d7/spc/yzyang4/forets-repair-transfer-20260913-d151en61')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(path, expected=None):
    if path.is_symlink():
        raise ValueError('symlink')
    raw=path.read_bytes()
    if expected and sha(raw)!=expected:
        raise ValueError('evidence drift')
    text=raw.decode()
    if SECRET.search(text):
        raise ValueError('credential shape; stop without raw output')
    return text


def main():
    closure=json.loads(safe(ROOT/'readout-finished.json'))
    summary=json.loads(safe(ROOT/'summary.json',closure['summary_sha256']))
    selection=json.loads(safe(ROOT/'selection-public.json'))
    inputs=json.loads(safe(ROOT/'inputs.private.json',selection['private_sha256']))['rows']
    # Use only the prior fixed pure taxonomy, not its file-reading main or imports.
    taxonomy_path=Path(__file__).with_name('audit_closed_error_families_20260913.py')
    taxonomy=safe(taxonomy_path)
    parsed=ast.parse(taxonomy)
    pure=[node for node in parsed.body if
          (isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('ANSI','EXCEPTION','RULES')) or
          (isinstance(node,ast.FunctionDef) and node.name=='classify')]
    if len(pure)!=4:
        raise ValueError('fixed pure taxonomy structure')
    namespace={'re':re}
    exec(compile(ast.Module(body=pure,type_ignores=[]),str(taxonomy_path),'exec'),namespace)
    classify=namespace['classify']
    original={(r['case'],r['arm']):r for r in inputs}
    if len(original)!=24 or len(summary['rows'])!=24:
        raise ValueError('complete matrix')
    outputs={}
    for block in (0,1):
        work=ROOT/f'block-{block}'
        for item in json.loads(safe(work/'prepared.json'))['rows']:
            p=work/f'result-{item["local_index"]}.json'
            if not p.exists():
                continue
            result=json.loads(safe(p,summary['proof'][str(p)]))
            if result.get('output_sha256'):
                outputs[item['index']]=safe(work/f'program-{item["local_index"]}.txt',result['output_sha256'])
    rows=[]
    for row in summary['rows']:
        target=original[row['case'],row['arm']]
        before_type,before=classify(target['error'])
        term=outputs.get(row['index'])
        after_type,after=classify(term) if term is not None else (None,[])
        rows.append(dict(index=row['index'],case=row['case'],task=row['task'],arm=row['arm'],
            status=row['status'],original_exception=before_type,original_families=before,
            output_recorded=term is not None,after_exception=after_type,after_families=after,
            same_recognized_family=bool(set(before)&set(after)),
            repair_success=row['repair_success']))
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        for arm in ('no_external_memory','retrieved_repair','random_repair'):
            group=[r for r in rows if (r['task'],r['arm'])==(task,arm)]
            groups.append(dict(task=task,arm=arm,status_counts=dict(Counter(r['status'] for r in group)),
                original_families=dict(Counter(f for r in group for f in r['original_families'])),
                after_families=dict(Counter(f for r in group for f in r['after_families'])),
                repeated_recognized_family=sum(r['same_recognized_family'] for r in group)))
    value=dict(role='T1_exploratory_complete_error_transitions_not_new_endpoint',
        summary_sha256=closure['summary_sha256'],taxonomy_sha256=sha(taxonomy.encode()),rows=rows,groups=groups,
        caveat='Trace patterns may overlap or occur before a later failure. Disappearance of an error does not prove its cause fixed, valid learning, or higher quality. No arm/row excluded, no changed primary gate.')
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    if SECRET.search(raw.decode()):
        raise ValueError('unsafe public diagnostic')
    with (ROOT/'error-transitions.json').open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(groups=groups,diagnostic_sha256=sha(raw))))


if __name__=='__main__':
    main()
