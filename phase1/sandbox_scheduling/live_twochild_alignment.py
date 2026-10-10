"""Post-close structural diagnosis of all 16 assigned 17368 runs.

Uses frozen native extraction before comparing journal and return hashes.
No candidate text, response, score, prediction or label is exported. No replay.
Ambiguous repeated hashes are retained rather than greedily matched.
"""
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path

from lifecycle_pilot import read, sha, write
from live_readout import lines
from live_twochild_stage_audit_v2 import counts

ROOT = Path('/research/d7/spc/yzyang4/scheduling-live-twochild-20261010-v1')
PLAN = '082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6'
PRIMARY = '447ecf6e19aace0029a3d1a0564e7c7589fca869b1152cca71146be70834b00a'
RUNS = '8fee8abbaf3c98e1594386eaee5660cdcd8177f67f05295f768dfd7a6715eaba'


def closed_rows(summary, rows):
    # Frozen primary separates its summary from the per-run table.
    if summary.get('assigned') != 16 or not isinstance(rows, list) or sorted(r['index'] for r in rows) != list(range(16)):
        raise ValueError('separate complete original run table required')
    return rows


def align(recorded, returned):
    """Exact order; diagnose at most one excess return, never infer an identity."""
    if any(not isinstance(x, str) or len(x) != 64 for x in recorded + returned):
        raise ValueError('SHA256 sequences required')
    if recorded == returned:
        return dict(status='exact_sequence', possible_unrecorded_positions=[])
    if len(returned) != len(recorded) + 1:
        return dict(status='unresolved_mismatch', possible_unrecorded_positions=[])
    possible = [i for i in range(len(returned)) if returned[:i] + returned[i+1:] == recorded]
    status = 'unique_excess_return' if len(possible) == 1 else ('ambiguous_excess_return' if possible else 'unresolved_mismatch')
    return dict(status=status, possible_unrecorded_positions=possible)


def safe_excess(candidates, events, positions, horizon):
    result = []
    for i in positions:
        candidate = candidates[i]
        t = candidate['elapsed_seconds']
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 or type(candidate['valid']) is not bool:
            raise ValueError('candidate structural metadata')
        later = [e for e in events if t < e['elapsed'] <= horizon]
        result.append(dict(return_position=i, returned_seconds=t, timely=t <= horizon,
            externally_valid=candidate['valid'], is_last_return=i == len(candidates)-1,
            later_generation_starts=sum(e['event']=='generation_started' for e in later),
            later_successful_generation_returns=sum(e['event']=='generation_returned' and e.get('success') is True for e in later),
            later_failed_generation_returns=sum(e['event']=='generation_returned' and e.get('success') is False for e in later),
            later_candidate_operations=sum(e['event']=='operation_ready' and e.get('kind')=='candidate' for e in later)))
    return result


def main():
    if sha(ROOT/'plan.json') != PLAN or sha(ROOT/'readout-v1/summary.json') != PRIMARY:
        raise ValueError('exact closed scope')
    if sha(ROOT/'readout-v1/runs.json') != RUNS:raise ValueError('original per-run table drift')
    plan, primary = read(ROOT/'plan.json'), read(ROOT/'readout-v1/summary.json')
    primary_rows = closed_rows(primary, read(ROOT/'readout-v1/runs.json'))
    if not (ROOT/'closed.json').exists() or sorted(r['index'] for r in plan['schedule']) != list(range(16)):
        raise ValueError('all original assignments')
    source = ROOT/'source/src/dojo/core/solvers/utils/response.py'
    if sha(source) != plan['files'][str(source.relative_to(ROOT))]:
        raise ValueError('frozen extractor drift')
    spec = importlib.util.spec_from_file_location('frozen_response', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pins, rows = {}, []
    for assignment in plan['schedule']:
        index = assignment['index']; ep = ROOT/f'episode-{index}'
        journal = ep/'checkpoint/journal.jsonl'; event_path = ep/'events.jsonl'
        nodes = lines(journal); stage = counts(nodes, 2)
        cs_paths = [p for p in ep.glob('candidate-*.json') if '.private.' not in p.name]
        cs = sorted([read(p) for p in cs_paths], key=lambda c:c['elapsed_seconds'])
        events = lines(event_path)
        if any(not math.isfinite(e['elapsed']) for e in events) or [e['elapsed'] for e in events] != sorted(e['elapsed'] for e in events):
            raise ValueError('event order')
        ns = [n for n in nodes if n.get('operators_used')]
        if [n['step'] for n in ns] != sorted(set(n['step'] for n in ns)):
            raise ValueError('unique journal step order')
        recorded = [hashlib.sha256(module.extract_code(n['code']).encode()).hexdigest() for n in ns]
        returned = [c['code_sha256'] for c in cs]
        original = next(r for r in primary_rows if r['index']==index)
        if len(cs) != original['candidate_returns'] + original['late_returns'] or len(ns) != stage['recorded_nodes']:
            raise ValueError('original denominator disagreement')
        alignment = align(recorded, returned)
        rows.append(dict(**assignment, **alignment, journal_candidates=len(ns), execution_returns=len(cs),
            extra_return_metadata=safe_excess(cs,events,alignment['possible_unrecorded_positions'],plan['run_seconds']),
            invalid_returns=sum(c['valid'] is False for c in cs),
            completed_cell_timeouts=sum(e['event']=='cell_return' and e.get('timed_out') is True for e in events),
            failed_generation_returns=sum(e['event']=='generation_returned' and e.get('success') is False for e in events)))
        for p in [journal,event_path,*cs_paths]:pins[str(p.relative_to(ROOT))]=sha(p)
    result = dict(plan_sha256=PLAN, primary_sha256=PRIMARY, runs_sha256=RUNS, extractor_sha256=sha(source),
        analysis_sha256=sha(__file__), assigned=16, rows=rows, receipt_sha256=pins,
        alignment_counts=dict(Counter(r['status'] for r in rows)),
        diagnostic_correction='First invocation refused before writing because the reader incorrectly expected rows inside summary.json. The frozen primary has a separate runs.json. Exact-byte-pinned run table is now read explicitly; original experimental files and gates unchanged.',
        boundary='Post-result diagnosis only. A missing journal record is not necessarily a lost useful solution. Subsequent generation can be result analysis, not a new proposal. No event-timing counterfactual, no primary-gate change, no score/identity/content export. Hash ambiguity and mismatch remain explicit.')
    dest = ROOT/'return-alignment-v1.json'; write(dest,result)
    print(json.dumps(dict(written=True,sha256=sha(dest),assigned=16,alignment_counts=result['alignment_counts'],rows=rows),sort_keys=True))


if __name__ == '__main__':main()
