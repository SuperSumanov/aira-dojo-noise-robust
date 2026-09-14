"""One read-only status snapshot; never read model responses or task labels."""
import datetime,json,os,re
from pathlib import Path
ASSETS=Path('/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy')
ROOT=ASSETS/'integration-v6'
PRIVATE_LINE=re.compile(r'(?i)(api[_ -]?key|access[_ -]?token|auth[_ -]?token|bearer|password|credential|https?://[^\s]*[?&](token|key|secret)=)')
SHAPE=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|[a-f0-9]{64})')
def read(path):return json.loads(path.read_bytes())
def tail(path,n=20000):
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-n));return f.read(n).decode(errors='replace')
def snapshot():
    value={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if ASSETS.resolve(strict=True)!=ASSETS:raise ValueError('asset scope')
    plan=read(ASSETS/'plan.json');completed=[];partial=[]
    for entry in plan['files']:
        if not entry['path'].startswith('model/'):continue
        path=ASSETS/entry['path'];part=path.with_name(path.name+'.partial')
        if path.is_file():completed.append({'path':entry['path'],'bytes':path.stat().st_size})
        elif part.is_file():partial.append({'path':entry['path'],'bytes':part.stat().st_size,'expected_bytes':entry['size']})
    value['download']={'completed_files':len(completed),'completed_shards':sum(p['path'].endswith('.safetensors') for p in completed),
        'completed_bytes':sum(p['bytes'] for p in completed),'partial':partial,'full_receipt_present':(ASSETS/'complete.json').exists()}
    pidfile=ASSETS/'download-weights-redirect-fixed-launch.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text());proc=Path('/proc')/str(pid)
        value['download'].update(pid=pid,pid_exists=proc.exists())
        if proc.exists():value['download']['comm']=(proc/'comm').read_text().strip()
    allowed=('status','job','utc','gpu_hours_cap','actual_model_calls','native_draft_calls','actual_config_paths',
      'startup_seconds','disjoint','controller_seconds','process_codes','task','seed','index','finish_reason','prompt_tokens',
      'completion_tokens','code_chars','generation_seconds','error_type','execution_status','execution_seconds','exit_code',
      'timed_out','submission_present','execution_error')
    value['integration']={}
    value['integration']['stage_files']={
        'native_previews_completed':sum((ROOT/f'preview-{i}.private.json').exists() for i in range(2)),
        'warmup_completed':(ROOT/'warmup.json').exists(),
        'calibration_completed':(ROOT/'calibration-results.json').exists()}
    for name in ('launch.json','cpu-preflight.json','driver-cpu.json','ready.json','closed.json',
                 'generation-0.json','generation-1.json','execution-0.json','execution-1.json'):
        path=ROOT/name
        if path.exists():value['integration'][name]={k:v for k,v in read(path).items() if k in allowed}
    # No raw LLM response, prompt, .env, program stdout or outcome file is read.
    # Server/worker launch diagnostics are redacted remotely before display.
    for name in ('server.private.log','worker.private.log'):
        path=ROOT/name
        if not path.exists():continue
        lines=[]
        for line in tail(path).splitlines()[-18:]:
            if PRIVATE_LINE.search(line):line='[REDACTED_CREDENTIAL_LINE]'
            lines.append(SHAPE.sub('[REDACTED_TOKEN_OR_DIGEST]',line)[:700])
        value['integration'][name+'_redacted_tail']=lines
    print(json.dumps(value,sort_keys=True),flush=True)
if __name__=='__main__':snapshot()
