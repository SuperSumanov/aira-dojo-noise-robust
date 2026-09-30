"""Fixed counterfactual PARSING replay. No candidate execution or semantic edits.

Before reading results, alternative accepts already-valid Python unchanged;
otherwise only complete line-delimited python/empty-tag backtick fences. A
rejected native output is rescued only if exactly one nonempty compilable block
exists. Ambiguity is reported, never resolved using scores or labels.
"""
import argparse,collections,hashlib,json,re,signal,tarfile
from pathlib import Path,PurePosixPath
from independent_raw_comparison_0930 import PIN,BAD,KEY,digest
from compiler_feedback_census_0930 import terminal,GENERIC

OPEN=re.compile(r'^[ ]{0,3}(`{3,})(?:python)?[ \t]*$')

def valid(s):
    if not s.strip():return False
    try:compile(s,'<candidate>','exec');return True
    except (SyntaxError,ValueError):return False

def line_blocks(text):
    lines=text.splitlines(keepends=True);blocks=[];opening=None;body=[];start=None
    for i,line in enumerate(lines,1):
        content=line.rstrip('\r\n')
        if opening is None:
            m=OPEN.fullmatch(content)
            if m:opening=len(m[1]);body=[];start=i+1
        elif re.fullmatch(r'[ ]{0,3}`{'+str(opening)+r',}[ \t]*',content):
            blocks.append({'text':''.join(body),'start_line':start,'end_line':i-1});opening=None
        else:body.append(line)
    return blocks,opening is not None

def alternative(text):
    if valid(text):return 'raw_python',text,0,0
    blocks,unclosed=line_blocks(text)
    passed=[b for b in blocks if valid(b['text'])]
    if unclosed:return 'unclosed_fence',None,len(blocks),len(passed)
    if len(passed)!=1:return ('ambiguous' if len(passed)>1 else 'no_valid_block'),None,len(blocks),len(passed)
    return 'single_valid_block',passed[0]['text'],len(blocks),1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(600)
    assert not a.output.exists();rows=[];sources=[]
    for name,pin in PIN.items():
        p=a.source/name;assert digest(p)==pin
        configs={};journals={}
        with tarfile.open(p,'r|gz') as tf:
            for m in tf:
                path=PurePosixPath(m.name)
                if not m.isfile() or path.name not in ('JOURNAL.jsonl','dojo_config.json'):continue
                assert m.size<64*1024**2
                raw=tf.extractfile(m).read();assert not BAD.search(raw) and not KEY.search(raw)
                if path.name=='dojo_config.json':configs[path.parent]=json.loads(raw)
                else:journals[path]=(raw,hashlib.sha256(raw).hexdigest())
        for path,(raw,jsha) in journals.items():
            roots=[r for r in configs if r in path.parents];assert len(roots)==1
            root=roots[0];cfg=configs[root];rd=hashlib.sha256(str(root).encode()).hexdigest();segment=0
            for line in raw.splitlines():
                n=json.loads(line)['data']
                if not n['step']:segment+=1;continue
                code=n['code'];kind,selected,bcount,passed=alternative(code)
                native_generic=terminal(n)==GENERIC
                rows.append({'run_digest':rd,'task':cfg['task']['name'],'arm':root.parts[3],
                    'seed':cfg['metadata']['seed'],'segment':segment,'step':n['step'],
                    'native_generic_reject':native_generic,'kind':kind,'accepted':selected is not None,
                    'complete_blocks':bcount,'compilable_blocks':passed,
                    'raw_unchanged':selected==code,'raw_code_sha256':hashlib.sha256(code.encode()).hexdigest(),
                    'selected_sha256':hashlib.sha256(selected.encode()).hexdigest() if selected is not None else None,
                    'selected_chars':len(selected) if selected is not None else None})
            sources.append({'run_digest':rd,'archive_sha256':pin,'journal_sha256':jsha})
    groups=collections.Counter((r['native_generic_reject'],r['kind']) for r in rows)
    result={'kind':'PARSER_REPLAY_ONLY_NO_EXECUTION','counts':[{'native_generic_reject':g,'alternative':k,'n':n} for (g,k),n in groups.items()],
      'rows':rows,'sources':sources,'script_sha256':digest(Path(__file__)),
      'boundary':'No grade values used. No code edits. Compilable does not imply runtime success or solution quality.'}
    a.output.mkdir();(a.output/'receipt.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'kind':result['kind'],'counts':result['counts']}))

if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__}));raise SystemExit(2)
