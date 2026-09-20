"""Closed diagnostic: fixed scalar/error-class allowlist; never reply text."""
import collections,json,re
from pathlib import Path
import local_generator_runtime_20260914 as rt
ROOT=rt.BASE/'comparison-pool-native-selection-20260920-ilbr14cp'
if rt.sha(ROOT/'summary.json')!='a202a427f512cbdfe855ee5176b58c5581d16ee2a49b2776b7579389befae000':raise ValueError('closed source')
rows=[]
for index in range(30):
    path=ROOT/f'analysis-{index}.json';raw=path.read_bytes()
    if rt.SHAPES.search(raw):raise ValueError('credential shape')
    value=json.loads(raw)
    if value['status']=='returned':continue
    row={k:value.get(k) for k in ('index','task','seed','slot','status','error_type','analysis_seconds','exit_code','timed_out')}
    answer=ROOT/f'answer-{index}.private.json';row['answer_exists']=answer.is_file()
    if answer.is_file():
        data=answer.read_bytes()
        if rt.SHAPES.search(data):raise ValueError('credential shape; no text readout')
        parsed=json.loads(data);response=parsed.get('response');usage=parsed.get('info',{}).get('usage',{})
        row['response_type']=type(response).__name__
        if isinstance(response,dict):
            row['is_bug_type']=type(response.get('is_bug')).__name__;row['metric_type']=type(response.get('metric')).__name__
        row['finish_reason']=usage.get('finish_reason') if usage.get('finish_reason') in ('stop','length','tool_calls',None) else 'other'
        row['prompt_tokens']=usage.get('prompt_tokens');row['completion_tokens']=usage.get('completion_tokens')
    rows.append(row)
print(json.dumps(dict(role='closed_scalar_failure_diagnosis',unknown=len(rows),rows=rows),allow_nan=False))
