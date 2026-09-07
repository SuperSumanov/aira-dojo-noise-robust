"""Historical-only, outcome-unused program and parent-structure projection.

Whole JSON lines may contain old outcomes. They enter the parser but are never
used, returned, or consulted for selecting programs. This module is NOT an
execution or source-admission gate. Only a hash-bound fixed-scope caller may use
it; it has no corpus-reading CLI and never executes code.
"""
import hashlib,json,re
from collections import defaultdict

SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate_json_key')
        d[k]=v
    return d
def project(raw):
    if type(raw) is not bytes or not 0<len(raw)<=32*2**20:raise ValueError('journal_member_size')
    if SECRET.search(raw):raise ValueError('journal_credential_shape')
    lines=raw.splitlines()
    if not lines or len(lines)>10000:raise ValueError('journal_line_cap')
    nodes=[];unsupported=0
    for line in lines:
        if not line.strip():raise ValueError('blank_journal_line')
        obj=json.loads(line,object_pairs_hook=unique)
        if not isinstance(obj,dict):raise ValueError('journal_object')
        data=obj.get('data',obj)
        if not isinstance(data,dict) or not {'step','code','parents'}<=set(data):
            unsupported+=1;continue
        step=data['step'];parents=data['parents'];code=data['code']
        if type(step) is not int or step<0:raise ValueError('journal_step')
        if 'data' in obj and 'step' in obj and obj['step']!=step:raise ValueError('wrapper_step_mismatch')
        if type(parents) is not list or any(type(p) is not int or p<0 or p>=step for p in parents):raise ValueError('journal_parents')
        if len(parents)!=len(set(parents)):raise ValueError('duplicate_parent')
        if code is not None and not isinstance(code,str):raise ValueError('journal_code_type')
        encoded=(code or '').encode('utf-8')
        if len(encoded)>2**20:raise ValueError('journal_code_size')
        node_id=data.get('id')
        if node_id is not None and not isinstance(node_id,str):raise ValueError('journal_id_type')
        nodes.append({'step':step,'parents':sorted(parents),'code_sha256':digest(encoded),
          'code_bytes':len(encoded),'nonempty_code':bool(code and code.strip()),
          'node_id_sha256':digest(node_id.encode()) if node_id is not None else None})
    return {'member_sha256':digest(raw),'lines':len(lines),'unsupported_lines':unsupported,'nodes':nodes}

def merge(projects):
    """Retain all programs; no score/buggy/exit filtering, no candidate choice."""
    if not projects:raise ValueError('no_journals')
    nodes={};duplicates=0;unsupported=0
    for p in projects:
        unsupported+=p['unsupported_lines']
        for row in p['nodes']:
            step=row['step']
            if step in nodes:
                if nodes[step]!=row:raise ValueError('conflicting_duplicate_step')
                duplicates+=1
            else:nodes[step]=row
    families=defaultdict(list)
    for step,row in nodes.items():
        if row['parents'] and row['nonempty_code']:families[tuple(row['parents'])].append(step)
    pairs=sum(len(s)*(len(s)-1)//2 for s in families.values())
    distinct_pairs=sum(nodes[a]['code_sha256']!=nodes[b]['code_sha256'] for s in families.values() for i,a in enumerate(s) for b in s[i+1:])
    return {'nodes':[nodes[s] for s in sorted(nodes)],'unique_steps':len(nodes),'duplicate_log_rows':duplicates,
      'unsupported_lines':unsupported,'nonempty_programs':sum(r['nonempty_code'] for r in nodes.values()),
      'unique_nonempty_program_bytes':len({r['code_sha256'] for r in nodes.values() if r['nonempty_code']}),
      'families_with_two_nonempty_children':sum(len(s)>=2 for s in families.values()),
      'same_parent_nonempty_pairs':pairs,'same_parent_distinct_program_pairs':distinct_pairs,
      'missing_parent_steps':len({p for row in nodes.values() for p in row['parents'] if p not in nodes}),
      'all_lines_supported':unsupported==0,'executability_verified':False,'source_admitted':False}
