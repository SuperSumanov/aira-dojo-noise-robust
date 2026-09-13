"""Outcome-free cheap comparator on every fixed first pool, not a new method claim.

Designed after the parent e2e readout; new completion outcomes must not be read.
Only code/parent/seed metadata is used. These are exploratory diagnostic baselines.
"""
from contextlib import closing
import difflib
import io
import json
from pathlib import Path
import sqlite3
import time
import tokenize
from forets_environment_build_20260912 import read,write,encode,sha

PARENT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')
COMPLETION=Path('/research/d7/spc/yzyang4/forets-pool-completion-20260912-n3c3ijtb')


def tokens(code):
    excluded={tokenize.ENCODING,tokenize.COMMENT,tokenize.NL,tokenize.NEWLINE,tokenize.ENDMARKER,
              tokenize.INDENT,tokenize.DEDENT}
    return [(t.type,t.string) for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type not in excluded]


def scores(parent,codes):
    a=tokens(parent);distances=[];malformed=[]
    for code in codes:
        try:
            b=tokens(code);distances.append(1-difflib.SequenceMatcher(None,a,b,autojunk=False).ratio());malformed.append(False)
        except (tokenize.TokenError,IndentationError,SyntaxError):
            distances.append(1.0);malformed.append(True)
    return distances,malformed


def main():
    finish=read(PARENT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('parent closure')
    if (COMPLETION/'completion-summary.json').exists():raise ValueError('completion already revealed')
    prepared=read(COMPLETION/'prepared.json');rows=[]
    if len(prepared['pools'])!=4 or len(prepared['rows'])!=9:raise ValueError('fixed all-pool coverage')
    for pool in prepared['pools']:
        rid=pool['parent_run_id'];cp=PARENT/'runs'/rid/'checkpoint';path=cp/'forets-candidates-private/batch-2.sqlite'
        before=sha(path.read_bytes())
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
        if sha(raw.encode())!=h or sha(path.read_bytes())!=before:raise ValueError('pool drift')
        v=json.loads(raw);nodes=[json.loads(l) for l in (cp/'journal.jsonl').read_bytes().splitlines()]
        parent=[n for n in nodes if n['id']==v['binding']['parent_id'] and n['step']<2 and n['exec_time'] is not None]
        if len(parent)!=1:raise ValueError('actual executed parent')
        codes=[c['node']['code'] for c in v['candidates']]
        if [sha(c.encode()) for c in codes]!=pool['code_sha256']:raise ValueError('code binding')
        start=time.perf_counter();distance,malformed=scores(parent[0]['code'],codes);elapsed=time.perf_counter()-start
        rows.append(dict(parent_run_id=rid,task=pool['task'],seed=pool['seed'],pool_sha256=before,
            parent_code_sha256=sha(parent[0]['code'].encode()),code_sha256=pool['code_sha256'],
            normalized_parent_token_distance=distance,malformed_tokens=malformed,
            parent_distance_order=sorted(range(4),key=lambda i:(distance[i],i)),
            code_length_order=sorted(range(4),key=lambda i:(len(codes[i]),i)),
            measured_query_seconds=elapsed))
    result=dict(role='exploratory_cheap_comparators_not_novelty_or_confirmatory',rows=rows,
        parent_finish_sha256=sha((PARENT/'readout-finished.json').read_bytes()),
        completion_prepared_sha256=sha((COMPLETION/'prepared.json').read_bytes()),
        script_sha256=sha(Path(__file__).read_bytes()),
        definition='Token sequence parent->candidate SequenceMatcher autojunk=False; ignore whitespace/comments, keep names/literals. Ascending distance, slot tie-break. Code-length ascending, slot tie-break.',
        disclosure='Designed after parent e2e results, before reading any new completion outcome. No tuning, learned model, feedback, API or execution. Not an e2e effect or a novel algorithm.')
    print(json.dumps(dict(sha256=write(COMPLETION/'cheap-comparators.json',encode(result)),rows=rows)))


if __name__=='__main__':main()
