"""Safe successor facts only after the action experiment's verified closure."""
from contextlib import closing
from pathlib import Path
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')
AUTH='b00f6e77b018028a544d2c8c066ca4e239d4f50878436c182c059ccf104b2e04'

def run():
    build=read(ROOT/'build.json');finished=read(ROOT/'readout-finished.json')
    if build['source_tree']!='f7a8b9e3c07b530467573315d55f62203cc67895' or finished['status']!='verified':raise ValueError('exact verified closure required')
    for n,h in finished['files'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('closed result drift')
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH,0)]:raise ValueError('active final ledger required')
        rows=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    counts=[len(rows),sum(r[2] for r in rows),sum(r[3] or 0 for r in rows),sum(r[4]=='unresolved' for r in rows)]
    if counts[3]!=2:raise ValueError('new unresolved charges')
    result=dict(root=str(ROOT),source_tree=build['source_tree'],prepared_sha256=build['prepared_sha256'],authorization=AUTH,
        finish_sha256=sha((ROOT/'readout-finished.json').read_bytes()),calls_sha256=sha(encode(rows)),billing_counts=counts)
    digest=write(ROOT/'width-parent-facts.json',encode(result))
    print(encode(dict(**result,facts_sha256=digest)).decode())

if __name__=='__main__':run()
