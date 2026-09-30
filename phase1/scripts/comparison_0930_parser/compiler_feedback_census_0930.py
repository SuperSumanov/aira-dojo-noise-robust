"""Diagnose compiler-feedback erasure on already-authorized archives.

Only compile candidate strings; NEVER execute them. Return categorical findings,
coordinates, hashes and counts, never source lines or raw terminal output.
The known generic error is matched exactly, not a post-hoc regex classifier.
This is an observational source/feedback check, not an intervention efficacy test.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import signal
import sys
import tarfile
from pathlib import Path, PurePosixPath
from independent_raw_comparison_0930 import BAD, KEY, PIN, category, digest

GENERIC = 'Invalid solution: Solution is not valid python code.'

def syntax_fact(code):
    try:
        compile(code, '<candidate>', 'exec')
        return None
    except SyntaxError as e:
        msg = e.msg.lower()
        if 'unterminated string' in msg or 'eol while scanning string' in msg:
            family = 'unterminated_string'
        elif 'f-string' in msg:
            family = 'f_string_syntax'
        elif 'indent' in msg or 'unindent' in msg or 'tab' in msg:
            family = 'indentation'
        elif 'never closed' in msg or 'unmatched' in msg or 'does not match' in msg:
            family = 'delimiter'
        elif 'invalid character' in msg or 'non-printable' in msg:
            family = 'invalid_character'
        elif 'unexpected eof' in msg:
            family = 'unexpected_eof'
        elif 'invalid syntax' in msg:
            family = 'invalid_syntax'
        else:
            family = 'other_syntax'
        line = (e.text or '').strip()
        return {'family': family, 'line': e.lineno, 'column': e.offset,
                'source_line_sha256': hashlib.sha256(line.encode()).hexdigest(),
                'exception_class': type(e).__name__}

def terminal(n):
    value = n['term_out']
    assert isinstance(value, (str, list))
    if isinstance(value, list):
        assert all(isinstance(x, str) for x in value)
        value = '\n'.join(value)
    return value.strip()

def analyze(nodes, metadata):
    rows=[]; segments=[]
    for n in nodes:
        if n['step']==0: segments.append({})
        assert segments and n['step'] not in segments[-1]
        segments[-1][n['step']]=n
    for segment, ns in enumerate(segments,1):
        facts={step: syntax_fact(n['code']) for step,n in ns.items() if step}
        for step,n in ns.items():
            if not step:continue
            assert len(n['parents'])==1
            parent=n['parents'][0]
            assert parent in ns and parent<step
            f=facts[step]; pf=facts.get(parent)
            r=dict(metadata, segment=segment, step=step, parent_step=parent,
                operator=category(n), syntax_rejected=f is not None,
                generic_feedback_exact=terminal(n)==GENERIC,
                execution_zero=n['exec_time']==0, logged_exit_code=n['exit_code'],
                parent_syntax_rejected=pf is not None,
                same_family_and_line_as_parent=bool(f and pf and f['family']==pf['family'] and
                    f['source_line_sha256']==pf['source_line_sha256']),
                compiler_fact=f)
            rows.append(r)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    os.umask(0o077);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(600)
    assert not a.output.exists();rows=[];sources=[]
    for archive,pin in PIN.items():
        src=a.source/archive;assert digest(src)==pin
        configs={};journals={};seen=set();expanded=0
        with tarfile.open(src,'r|gz') as tf:
            for m in tf:
                path=PurePosixPath(m.name)
                assert not path.is_absolute() and '..' not in path.parts and m.name not in seen
                seen.add(m.name);expanded+=m.size;assert len(seen)<=100000 and expanded<=4*1024**3
                if not m.isfile() or path.name not in ('dojo_config.json','JOURNAL.jsonl'):continue
                assert m.size<=64*1024**2
                raw=tf.extractfile(m).read();assert not BAD.search(raw) and not KEY.search(raw)
                if path.name=='dojo_config.json':configs[path.parent]=(json.loads(raw),hashlib.sha256(raw).hexdigest())
                else:journals[path]=(raw,hashlib.sha256(raw).hexdigest())
        assert len(configs)==len(journals)
        for path,(raw,jsha) in journals.items():
            roots=[r for r in configs if r in path.parents];assert len(roots)==1
            root=roots[0];cfg,csha=configs[root];rd=hashlib.sha256(str(root).encode()).hexdigest()
            rows.extend(analyze([json.loads(x)['data'] for x in raw.splitlines() if x.strip()],
                {'run_digest':rd,'task':cfg['task']['name'],'arm':root.parts[3],'seed':cfg['metadata']['seed']}))
            sources.append({'run_digest':rd,'archive_sha256':pin,'config_sha256':csha,'journal_sha256':jsha})
    counts=collections.Counter();families=collections.Counter();bytask=collections.defaultdict(collections.Counter)
    for r in rows:
        keys=['actions']
        if r['syntax_rejected']:keys+=['syntax_rejected'];families[r['compiler_fact']['family']]+=1
        if r['generic_feedback_exact']:keys+=['generic_feedback_exact']
        if r['syntax_rejected'] and r['generic_feedback_exact']:keys+=['syntax_rejected_with_generic_feedback']
        if r['operator']=='debug' and r['parent_syntax_rejected']:
            keys+=['debug_after_syntax_rejection']
            if r['syntax_rejected']:keys+=['debug_still_syntax_rejected']
            if r['same_family_and_line_as_parent']:keys+=['debug_same_family_and_line']
        counts.update(keys);bytask[r['task']].update(keys)
    result={'kind':'OBSERVATIONAL_COMPILER_FEEDBACK_CENSUS','counts':dict(counts),
      'families':dict(families),'by_task':{k:dict(v) for k,v in bytask.items()},'rows':rows,'sources':sources,
      'script_sha256':digest(Path(__file__)),'python':sys.version,
      'boundary':'No source/terminal literals exported; compiler coordinates are diagnostic evidence, not measured model recovery.'}
    a.output.mkdir();(a.output/'receipt.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('kind','counts','families','by_task')}))

if __name__=='__main__':
    try:main()
    except Exception as e:
        import traceback
        print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__,
          'frames':[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(e.__traceback__)]}))
        raise SystemExit(2)
