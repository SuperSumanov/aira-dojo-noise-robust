"""Bounded, read-only streaming watch for exactly this window's two trials.

No task submission, retries, files written or runtime mutation. It exits at a
closure receipt; terminal resource accounting remains a separate final check.
"""
import argparse
import contextlib
import datetime
import io
import json
import sys
import time


def compact(kind,state):
    if kind=='neural':
        return dict(job=state['job'],blocks=state['blocks_complete'],
            completed=sum(r.get('complete') is True for r in state['rows'] if r['index']!=36),
            rows=[{k:r.get(k) for k in ('index','arm','started','candidate_started','candidate_ended','closed','complete','error_type','returncode','gpu_steps','cell_statuses','prelude_diagnostic_terms')}
                  for r in state['rows'] if r['started']],
            closed=state.get('batch_closed'))
    return dict(job=state['launch'].get('job'),closed=state['controller_closed'],
        blocks=[dict(block=b['block'],service_ready=bool(b['service_ready']),
            worker_started=b['worker_started'],worker_finished=b['worker_finished'],
            supervisor_closed=b['supervisor_closed'],candidate_receipts=b['candidate_receipts'],
            scoring_receipts=b['scoring_receipts'],cycle_closed=b['cycle_closed'],
            slot_closed=bool(b['budget_slot']),gpu_clean=b['gpu_clean'],
            states=[{k:r.get(k) for k in ('index','status','returncode','cleanup_verified')} for r in b['worker_states']],
            service_errors=(b['service_log'] or {}).get('exception_types'),
            block_errors=(b['block_log'] or {}).get('exception_types')) for b in state['blocks']])


def sample(kind):
    captured=io.StringIO()
    with contextlib.redirect_stdout(captured):
        if kind=='neural':
            import neural_status
            neural_status.main('extension')
        else:
            import live_status
            old=sys.argv
            try:
                sys.argv=['live_status.py','--version','twochild'];live_status.main()
            finally:sys.argv=old
    return compact(kind,json.loads(captured.getvalue()))


def main(kind):
    limit=6300 if kind=='neural' else 10500
    deadline=time.monotonic()+limit;previous=None
    while time.monotonic()<deadline:
        try:
            for attempt in range(3):
                try:state=sample(kind);break
                except json.JSONDecodeError:
                    if attempt==2:raise
                    time.sleep(1) # bounded tolerance for a writer in progress
        except Exception as error:
            print(json.dumps(dict(monitor_failed=type(error).__name__,not_experiment_verdict=True)),flush=True)
            return 1
        if state!=previous:
            print(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,**state),sort_keys=True),flush=True)
            previous=state
        if state.get('closed'):return 0
        time.sleep(25)
    print(json.dumps(dict(monitor_expired=True,not_experiment_verdict=True)),flush=True)
    return 2


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=('neural','twochild'))
    sys.exit(main(ap.parse_args().kind))
