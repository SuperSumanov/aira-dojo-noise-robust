"""Frozen-parser replay on the sole default-zero legacy row; no execution."""
import argparse,hashlib,importlib.util,json,sys,tarfile
from pathlib import Path,PurePosixPath
from audit_legacy_exit_labels_20261001 import ROOT,PINS,pinned,SECRET,KEY,PROTECTED,sha

TARGET='f04eba2a8986d2db3805e296ba43dcb079ac8923ce1a698754a0ec1e32915c9c'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    load('dojo.utils.python_code_blocks',a.bundle/'candidate/src/dojo/utils/python_code_blocks.py')
    old=load('legacy_old_parser',a.bundle/'baseline/src/dojo/utils/code_parsing.py')
    new=load('legacy_new_parser',a.bundle/'candidate/src/dojo/utils/code_parsing.py')
    runs=pinned(ROOT/'qwen-readout-v1/runs.json',PINS['runs.json'])
    wanted={r['run']:r for r in runs if r['arm'].startswith('forets') and r['journal_present']}
    manifest=pinned(ROOT/'structure.redacted.json',PINS['structure.redacted.json']);found=[]
    for rec in manifest['archives']:
        p=ROOT/'archives'/rec['archive'];assert p.parent==ROOT/'archives'
        with tarfile.open(p,'r|gz') as tf:
            for member in tf:
                path=PurePosixPath(member.name)
                if not member.isfile() or path.name!='journal.jsonl' or path.parent.name!='checkpoint':continue
                run=sha(str(path.parent.parent).encode())[:16]
                if run not in wanted:continue
                raw=tf.extractfile(member).read();assert sha(raw)==wanted[run]['journal_sha256']
                assert not any(p.search(raw) for p in (SECRET,KEY,PROTECTED))
                for line in raw.splitlines():
                    n=json.loads(line)
                    if sha((run+':'+n['id']).encode())!=TARGET:continue
                    record={'row_digest':TARGET,'run_digest':run,'journal_sha256':sha(raw),
                            'stored_code_sha256':sha(n['code'].encode()),'input_20000_sha256':sha(n['code'][:20000].encode()),
                            'stored_code_chars':len(n['code'])}
                    for label,parser in [('old',old),('new',new)]:
                        try:
                            result=parser.extract_code(n['code']);compile(result,'<candidate>','exec')
                            record[label+'_admitted']=True;record[label+'_output_sha256']=sha(result.encode())
                        except Exception as e:
                            assert str(e)=='Solution is not valid python code.'
                            record[label+'_admitted']=False
                    found.append(record)
    assert len(found)==1
    result={'status':'FIXED_SINGLE_ROW_REPLAY','rows':found,
            'source_reference_commit':'e385f863cb531904e611e987f7f71606796db656',
            'script_sha256':sha(Path(__file__).read_bytes()),
            'package_hashes':{p.relative_to(a.bundle).as_posix():sha(p.read_bytes()) for p in a.bundle.rglob('*.py')},
            'boundary':'Existing failed label case only, not a quality-selected candidate or an efficacy trial. No model calls or candidate execution.'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='package_hashes'}))


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__}));raise SystemExit(2)
