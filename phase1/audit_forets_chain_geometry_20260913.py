"""Closed development topology only, not a counterfactual search-utility test."""
import collections
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')
SUMMARY='e1722e9277dda73a9c73471f2cb2c53703e260d107e8bdaa31311fe48259cdab'


def geometry(nodes):
    # Journal.get_node_data serializes edge endpoints as step integers, not UUIDs.
    ids={n['step']:n for n in nodes}
    if len(ids)!=len(nodes) or len({n['id'] for n in nodes})!=len(nodes):raise ValueError('duplicate node')
    if any(type(n['step']) is not int for n in nodes):raise ValueError('noninteger step')
    missing=[];degrees=[];roots=[]
    for node in nodes:
        if not node['parents']:roots.append(node['step'])
        children=node['children'];degrees.append(len(children))
        if len(set(children))!=len(children):raise ValueError('duplicate children')
        for parent in node['parents']:
            if parent not in ids or node['step'] not in ids[parent]['children']:raise ValueError('missing/asymmetric saved parent')
        for child in children:
            if child is not None and type(child) is not int:raise ValueError('noninteger child reference')
            if child not in ids:missing.append(child);continue
            if node['step'] not in ids[child]['parents']:raise ValueError('asymmetric saved edge')
    visited=set();stack=list(roots)
    while stack:
        node=stack.pop()
        if node in visited:raise ValueError('cycle or shared child')
        visited.add(node);stack.extend(c for c in ids[node]['children'] if c in ids)
    return dict(persisted_nodes=len(nodes),roots=len(roots),max_saved_children=max(degrees,default=0),
        branching_nodes=sum(d>1 for d in degrees),unpersisted_child_references=len(set(missing)),
        unreachable_saved_nodes=len(ids)-len(visited))


def run():
    summary=read(ROOT/'wallclock-summary.json',SUMMARY)
    if read(ROOT/'readout-finished.json')['status']!='verified':raise ValueError('closed readout required')
    rows=[]
    for r in summary['rows']:
        directory=ROOT/'runs'/r['run_id']/'checkpoint';path=directory/'journal.jsonl'
        row=dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],journal_present=path.exists())
        if path.exists():
            raw=path.read_bytes();nodes=[json.loads(line) for line in raw.splitlines() if line.strip()]
            row.update(geometry(nodes));row['journal_sha256']=sha(raw)
            ids={n['id']:n for n in nodes};parents=[]
            for ledger in sorted((directory/'forets-candidates-private').glob('batch-*.sqlite')):
                with closing(sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True)) as db:
                    records=db.execute('select payload,sha256 from snapshot where id=1').fetchall()
                if len(records)!=1 or sha(records[0][0].encode())!=records[0][1]:raise ValueError('snapshot')
                value=json.loads(records[0][0]);binding=value['binding']
                if binding['step']==1:continue
                parent=ids.get(binding['parent_id'])
                previously_recognized=any(0<n['step']<binding['step'] and n.get('is_buggy') is False for n in nodes)
                parents.append(dict(step=binding['step'],parent_in_journal=parent is not None,
                    parent_internally_buggy=None if parent is None else parent.get('is_buggy'),
                    internally_nonbuggy_history_available=previously_recognized))
            row['post_initial_parents']=parents
            row['buggy_parent_despite_nonbuggy_history']=sum(p['parent_internally_buggy'] is True and p['internally_nonbuggy_history_available'] for p in parents)
            if sha(path.read_bytes())!=sha(raw):raise ValueError('concurrent mutation')
        rows.append(row)
    previous=ROOT/'chain-geometry-audit.json'
    result=dict(role='posthoc_saved_graph_and_parent_diagnostic',schema=2,summary_sha256=SUMMARY,rows=rows,
        inspector_sha256=sha(Path(__file__).read_bytes()),
        supersedes_sha256=sha(previous.read_bytes()),
        correction='v1 misinterpreted serialized integer step references as UUID references; all graph reachability results from v1 are void.',
        limitation='Missing journals are not empty trees. Internal is_buggy is not external grade. No alternative parent executed, no efficacy claim.')
    digest=write(ROOT/'chain-geometry-audit-v2.json',encode(result))
    print(json.dumps(dict(rows=rows,sha256=digest)))


if __name__=='__main__':run()
