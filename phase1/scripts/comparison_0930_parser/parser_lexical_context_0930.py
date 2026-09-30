"""Check whether rescued triple-backtick tokens occur inside Python literals.

Only lexical token types, counts and AST digests are exported. No program or
literal value leaves the remote reader, and no candidate is executed.
"""
import argparse,ast,collections,hashlib,io,json,signal,tarfile,tokenize
from pathlib import Path,PurePosixPath
from independent_raw_comparison_0930 import PIN,BAD,KEY,digest
from compiler_feedback_census_0930 import terminal,GENERIC
from fence_replay_0930 import alternative


def token_counts(source):
    counts=collections.Counter()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if '```' in token.string:
            counts[tokenize.tok_name[token.type]]+=token.string.count('```')
    return dict(counts)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(600)
    rows=[]
    for name,pin in PIN.items():
        p=a.source/name;assert digest(p)==pin
        with tarfile.open(p,'r|gz') as tf:
            for m in tf:
                path=PurePosixPath(m.name)
                if not m.isfile() or path.name!='JOURNAL.jsonl':continue
                assert m.size<64*1024**2
                raw=tf.extractfile(m).read();assert not BAD.search(raw) and not KEY.search(raw)
                jsha=hashlib.sha256(raw).hexdigest();segment=0
                for line in raw.splitlines():
                    n=json.loads(line)['data']
                    if not n['step']:segment+=1;continue
                    if terminal(n)!=GENERIC:continue
                    mode,source,_,passed=alternative(n['code'])
                    assert mode=='single_valid_block' and passed==1
                    found=token_counts(source)
                    assert found and set(found)<= {'STRING','COMMENT','FSTRING_MIDDLE'}
                    rows.append({'journal_sha256':jsha,'segment':segment,'step':n['step'],
                                 'token_context_counts':found,
                                 'accepted_ast_sha256':hashlib.sha256(ast.dump(ast.parse(source),include_attributes=False).encode()).hexdigest()})
    assert len(rows)==204
    classes=collections.Counter(tuple(sorted(r['token_context_counts'])) for r in rows)
    result={'status':'PASS','rejected_responses_checked':len(rows),
            'rows_by_token_context':[{'token_types':list(k),'rows':v} for k,v in sorted(classes.items())],
            'distinct_rescued_ast':len({r['accepted_ast_sha256'] for r in rows}),
            'rows':rows,'script_sha256':digest(Path(__file__)),
            'boundary':'Lexical context only. No literal text, semantic-quality judgment, execution or new score.'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__}));raise SystemExit(2)
