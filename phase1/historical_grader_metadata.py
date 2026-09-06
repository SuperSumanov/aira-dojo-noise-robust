"""Detect recorded grading provenance fields, never return metric/identity values.

Only for an externally authenticated historical-development scope. JSON bytes
may contain outcomes and enter the parser; no outcome value is inspected for
selection, returned, or used for qualification. Presence is not attestation.
"""
import hashlib
import json
import re

FIELDS=frozenset({'evaluator_commit','evaluator_git_commit','grader_commit','grader_git_commit',
 'git_commit_id','git_commit','commit_sha','code_commit','code_sha256','evaluator_sha256',
 'grader_sha256','mlebench_version','mle_bench_version','package_versions','runtime_versions',
 'grading_command','grader_command','evaluator_command','evaluator_id','grader_id'})
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def unique(rows):
    result={}
    for k,v in rows:
        if k in result:raise ValueError('duplicate_json_key')
        result[k]=v
    return result

def project(raw):
    if type(raw) is not bytes or not 0<len(raw)<=2**20:raise ValueError('grading_metadata_size')
    if SECRET.search(raw):raise ValueError('grading_credential_shape')
    root=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(root,(dict,list)):raise ValueError('grading_json_container')
    counts={};stack=[(root,0)];visited=0
    while stack:
        node,depth=stack.pop();visited+=1
        if depth>40 or visited>100000:raise ValueError('grading_metadata_complexity')
        if isinstance(node,dict):
            for k,v in node.items():
                if k.lower() in FIELDS:counts[k.lower()]=counts.get(k.lower(),0)+1
                if isinstance(v,(dict,list)):stack.append((v,depth+1))
        elif isinstance(node,list):
            stack.extend((v,depth+1) for v in node if isinstance(v,(dict,list)))
    return {'possible_provenance_field_counts':dict(sorted(counts.items())),
            'has_possible_provenance_fields':bool(counts),'record_bytes':len(raw),
            'record_sha256':hashlib.sha256(raw).hexdigest(),
            'evaluator_identity_attested':False,'outcome_values_used_for_selection':False}

def aggregate(rows):
    if not rows:raise ValueError('grading_metadata_empty')
    counts={}
    for r in rows:
        if set(r)!={'possible_provenance_field_counts','has_possible_provenance_fields','record_bytes',
                   'record_sha256','evaluator_identity_attested','outcome_values_used_for_selection'}:
            raise ValueError('grading_metadata_projection_schema')
        if r['evaluator_identity_attested'] is not False or r['outcome_values_used_for_selection'] is not False:
            raise ValueError('grading_metadata_claim')
        if r['has_possible_provenance_fields'] is not bool(r['possible_provenance_field_counts']):
            raise ValueError('grading_metadata_presence')
        for k,n in r['possible_provenance_field_counts'].items():
            if k not in FIELDS or type(n) is not int or n<=0:raise ValueError('grading_metadata_count')
            counts[k]=counts.get(k,0)+n
    return {'records':len(rows),'records_with_possible_provenance':sum(r['has_possible_provenance_fields'] for r in rows),
            'possible_provenance_field_counts':dict(sorted(counts.items())),
            'evaluator_identity_attested':False,'outcome_values_used_for_selection':False}
