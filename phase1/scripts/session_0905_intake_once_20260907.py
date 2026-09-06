"""One foreground intake transaction in the user's six-hour session.

Original scientific intake, registry, stability and first-960 closure untouched.
No scheduler, background loop, model fit, or result-value reader.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time
from phase1.scripts import foreground_intake_session_20260905 as base

BASE_SHA='d0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43'
SHELL_SHA='f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599'
START=dt.datetime.fromisoformat('2026-09-06T22:25:00+00:00').timestamp()
END=dt.datetime.fromisoformat('2026-09-07T03:53:36+00:00').timestamp()
CALL_CAP=2700
MAX_CALLS=16
OUT=Path('/research/d7/spc/yzyang4/session-0905-intake-20260907')
BASELINE='cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2'
SOURCE=Path('/research/d7/spc/yzyang4/external/senior_data/mle/0905')
PROOF=Path('/research/d7/spc/yzyang4/senior-0905-readonly-20260907/manifest.private.json')
PROOF_SHA='6b84ee91f1c0652842db57635942f8ebc85ff15c039e4041883302ef7b3582be'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


def source_binding():
    raw=base.regular(PROOF)
    base.require(hashlib.sha256(raw).hexdigest()==PROOF_SHA and not base.SECRET.search(raw),'readonly_source_proof_drift')
    rows=json.loads(raw)['records'];base.require(len(rows)==12,'source_count')
    base.require({p.name for p in SOURCE.iterdir()}=={r['name'] for r in rows},'source_inventory_drift')
    base.require(sum(1 for _ in SOURCE.parent.glob('*/*.tar.gz'))==343,'unknown_source_accrual')
    for r in rows:
        p=SOURCE/r['name'];base.require(p.parent==SOURCE and p.resolve()==p and not p.is_symlink(),'unsafe_source_file')
        s=p.stat()
        actual=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)
        base.require(actual==tuple(r['readonly_fingerprint']) and not s.st_mode&0o222
            and s.st_nlink==1 and sha(p)==r['sha256'],'source_bytes_or_metadata_drift')
        base.require(time.time()-s.st_mtime>=21600,'source_age_gate')


def main():
    now=time.time()
    base.require(START<=now and now+CALL_CAP<=END,'outside_bounded_session_window')
    prior=sorted(OUT.glob('wrapper-*.json')) if OUT.exists() else []
    base.require(len(prior)<MAX_CALLS,'session_call_limit')
    base.require([p.name for p in prior]==[f'wrapper-{i:03d}.json' for i in range(len(prior))],'wrapper_history_gap')
    base.require(len(list(OUT.glob('poll-*')))==len(prior),'unfinished_prior_intake')
    base.require(sha(Path(base.__file__))==BASE_SHA,'base_driver_drift')
    shell=Path(base.__file__).resolve().with_name(Path(base.REL).name)
    base.require(sha(shell)==SHELL_SHA,'derived_shell_drift')
    source_binding()
    previous=(base.START,base.END,base.OUT,base.BASELINE)
    try:
        base.START,base.END,base.OUT,base.BASELINE=START,END,OUT,BASELINE
        base.main()
    finally:base.START,base.END,base.OUT,base.BASELINE=previous
    source_binding()
    receipt={'wrapper_sha256':sha(Path(__file__)),'base_driver_sha256':BASE_SHA,
        'readonly_source_manifest_sha256':PROOF_SHA,'poll':len(prior),
        'foreground_receipt_sha256':sha(OUT/f'poll-{len(prior):03d}'/'receipt.json'),
        'session_end_utc':dt.datetime.fromtimestamp(END,dt.timezone.utc).isoformat(),
        'background_process_started':False,'archive_bytes_or_mtime_modified':False}
    target=OUT/f'wrapper-{len(prior):03d}.json'
    with target.open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    target.chmod(0o400)
    print(json.dumps({'status':'0905_FOREGROUND_CALL_COMPLETE',**receipt},sort_keys=True))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[a-z_]+',str(exc)) else 'detail_withheld'
        print(json.dumps({'status':'0905_INTAKE_FAILED_CLOSED','reason':reason}));raise SystemExit(1)
