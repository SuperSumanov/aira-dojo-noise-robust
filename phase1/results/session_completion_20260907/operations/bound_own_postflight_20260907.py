"""Enforce the existing 900-second bound on the exact already-running checker."""
import json, os, signal, time
from pathlib import Path

pid=1946993
proc=Path('/proc')/str(pid)
expected=[b'/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python',b'-B',b'-m',
 b'phase1.scripts.verify_pivot_ampere_artifacts_20260907',b'--job',b'12664',b'--training-commit',
 b'88522f74cafcd45778751c5315fa0a89a1704965',b'--output',
 b'/research/d7/spc/yzyang4/critic-pivot-ampere-postflight-12664-20260907']

def start():
    assert proc.stat().st_uid==os.getuid()
    assert (proc/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')==expected
    return int((proc/'stat').read_text().rsplit(') ',1)[1].split()[19])

if not proc.exists():
    print(json.dumps({'status':'CHECKER_ALREADY_EXITED_NO_SIGNAL'}))
else:
    born=start(); ticks=os.sysconf('SC_CLK_TCK')
    while proc.exists():
        try: assert start()==born
        except FileNotFoundError: break
        age=float(Path('/proc/uptime').read_text().split()[0])-born/ticks
        if age>=900:
            assert start()==born
            os.kill(pid,signal.SIGTERM)
            for _ in range(10):
                if not proc.exists(): break
                time.sleep(1)
            if proc.exists():
                assert start()==born
                os.kill(pid,signal.SIGKILL)
            print(json.dumps({'status':'OWN_CHECKER_TIME_BOUND_ENFORCED','pid':pid,'limit_seconds':900,'age_seconds':age}))
            break
        time.sleep(min(5,900-age))
    else:
        print(json.dumps({'status':'CHECKER_EXITED_WITHIN_BOUND_NO_SIGNAL','pid':pid}))
