"""Export two exact, credential-scanned result files, never the private model."""
import io,json,tarfile
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import read,checked,sha,BASE

ROOT=BASE/'forets-size-only-ablation-20260914-o8h3m5qv'
EXPECTED={'summary.json':'67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240',
          'independent.json':'9203b6f638f29a59c9d11a8caa1db32ddf6a5f270f55355078548dc7d3d3c28b'}
def main():
    data={n:checked(ROOT/n,h) for n,h in EXPECTED.items()}
    v=json.loads(data['independent.json'])
    if v['summary_sha256']!=EXPECTED['summary.json'] or not v['original_full_model_unchanged']:raise ValueError('verification')
    dest=Path(__file__).with_name('cheap-size-public-20260914.tar')
    with dest.open('xb') as f,tarfile.open(fileobj=f,mode='w') as archive:
        for name,raw in sorted(data.items()):
            member=tarfile.TarInfo(name);member.mode=0o600;member.size=len(raw);member.mtime=0
            archive.addfile(member,io.BytesIO(raw))
    print(json.dumps(dict(path=str(dest),sha256=sha(dest.read_bytes()),files=EXPECTED)))
if __name__=='__main__':main()
