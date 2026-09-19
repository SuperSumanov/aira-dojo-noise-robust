"""Closed episodes only: action attribution and prompt equality, never raw text."""
import hashlib,json
from pathlib import Path
import local_generator_runtime_20260914 as rt
ROOT=rt.BASE/'comparison-online-continuation-20260919-qpw9ys94'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def main():
    summary=rt.read(ROOT/'summary.json')
    if summary['closure']!='all_four_episodes_closed':raise ValueError('not closed')
    rows=[]
    for index in range(4):
        ep=ROOT/f'episode-{index}';actions=[];requests=[]
        for path in sorted(ep.glob('action-*.json')):
            row=rt.read(path)
            keys=('depth','kind','status','native_accepted','exit_code','timed_out','analysis_status','error_type','started_seconds','completed_seconds','code_sha256')
            actions.append({key:row[key] for key in keys if key in row})
        for path in sorted(ep.glob('generation-*.private.json')):
            value=rt.read(path);info=value['info'];usage=info.get('usage') or {}
            requests.append(dict(depth=int(path.name.split('-')[1].split('.')[0]),prompt_sha256=digest(info.get('prompt_messages')),response_sha256=digest(value['answer']),
                usage={k:usage[k] for k in ('prompt_tokens','completion_tokens','finish_reason') if k in usage}))
        rows.append(dict(index=index,actions=actions,requests=requests))
    out=dict(summary_sha256=rt.sha(ROOT/'summary.json'),rows=rows,raw_text_exported=False)
    rt.write(ROOT/'mechanism-diagnostic.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
