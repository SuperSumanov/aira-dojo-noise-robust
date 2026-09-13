"""Only verified, closed width results can authorize the successor ledger."""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from forets_environment_build_20260912 import read,write,encode,sha

def run(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4'):raise ValueError('scope')
    build=read(root/'build.json');done=read(root/'readout-finished.json')
    if done['status']!='verified':raise ValueError('closed predecessor')
    for n,h in done['files'].items():
        if sha((root/n).read_bytes())!=h:raise ValueError('closed bytes drift')
    result=read(root/'width-summary.json')
    if result['source_tree']!=build['source_tree'] or {(r['task'],r['seed'],r['arm']) for r in result['rows']}!={
        (t,s,a) for t in ('leaf-classification','spaceship-titanic') for s in (38,39) for a in ('batch_four','direct_two')}:
        raise ValueError('exact full predecessor matrix')
    with closing(sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        states=db.execute('SELECT digest,stopped FROM auth').fetchall()
        if len(states)!=1 or states[0][1]!=0:raise ValueError('active parent')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    counts=[len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows)]
    if counts[3]!=2:raise ValueError('new unresolved charges')
    facts=dict(protocol='closed_uniform_width_seeds38_39',root=root.as_posix(),source_tree=build['source_tree'],
        prepared_sha256=build['prepared_sha256'],authorization=states[0][0],
        finish_sha256=sha((root/'readout-finished.json').read_bytes()),calls_sha256=sha(encode(rows)),billing_counts=counts)
    digest=write(root/'memory-parent-facts.json',encode(facts))
    print(encode(dict(**facts,facts_sha256=digest)).decode())

if __name__=='__main__':run(Path(sys.argv[1]))
