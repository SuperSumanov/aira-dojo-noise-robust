"""Named verified derivative export: no raw programs, model files or logs."""
import io,json,tarfile
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import checked,sha,BASE

def main():
    stage=Path(__file__).parent;root=BASE/'forets-leave-task-out-20260914-3bppxdqh'
    inputs={
        'leave_task_out/summary.json':(root/'summary.json','43573a5c8dcf96b72fa60a3dfbd195c1c966a5fe12746c977ef8df95c2cdaeba'),
        'leave_task_out/independent.json':(root/'independent.json','c8fd3a01d9659a77352736bda955e9bf7f29134611e01f4f2ed0c9780a3d0a59'),
        'valid_quality/summary.json':(stage/'cheap-valid-quality.json','93beff6761de70a1632e4fefc09a55329b254b108a9f007f64d27b1bea37a752'),
        'valid_quality/independent.json':(stage/'cheap-valid-quality-independent.json','8c7dc0202df7e806c672e7fa2df4c1aeaf952f53acb1dd9fa2c313a647844fd5')}
    data={name:checked(p,h) for name,(p,h) in inputs.items()}
    for folder in ('leave_task_out','valid_quality'):
        if json.loads(data[folder+'/independent.json'])['summary_sha256']!=sha(data[folder+'/summary.json']):raise ValueError('verification graph')
    data['manifest.json']=(json.dumps({name:dict(sha256=sha(raw),bytes=len(raw)) for name,raw in data.items()},sort_keys=True)+'\n').encode()
    dest=stage/'cheap-stress-public-20260914.tar'
    with dest.open('xb') as f,tarfile.open(fileobj=f,mode='w') as archive:
        for name,raw in sorted(data.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;info.mtime=0;archive.addfile(info,io.BytesIO(raw))
    print(json.dumps(dict(path=str(dest),sha256=sha(dest.read_bytes()),files=len(data))))
if __name__=='__main__':main()
