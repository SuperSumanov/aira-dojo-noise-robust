"""Only service startup phases and artifact counts. No raw log text emitted."""
import json,os,re,subprocess,time
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-online-continuation-20260919-qpw9ys94')
rows=[]
for lane in (0,1):
    path=ROOT/f'server-{lane}-None.private.log';text=path.read_text(errors='replace') if path.exists() else ''
    cache=ROOT/f'lane-{lane}/service-cache'
    rows.append(dict(lane=lane,log_bytes=path.stat().st_size if path.exists() else 0,
        cuda_gate='LOCAL_SERVICE_CUDA ' in text,loaded='Loading weights took' in text,
        compile_mentions=text.lower().count('compil'),graph_mentions=text.lower().count('graph'),
        server_running='Application startup complete' in text,
        exception_classes=sorted(set(re.findall(r'(?m)\b([A-Z][A-Za-z]+Error):',text))),
        object_files=sum(1 for p in cache.rglob('*.o')),shared_libraries=sum(1 for p in cache.rglob('*.so'))))
print(json.dumps(dict(utc_seconds=time.time(),services=rows,raw_text_emitted=False)))
