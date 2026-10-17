"""Was observed quota blocking on Analyze upstream of better parent publication?

Closed18807 only. Exact candidate hash, same-worker event order and pinned
sources; no imagined faster trace or outcome re-scoring. Debug stays unlinked.
"""
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import closed_adaptation_lineage_20261017 as m

ROOT = Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
LINEAGE = 'adaptation-lineage-extension-20261017.safe.json'
PIN = 'b47201384f5d3c385f471becba37bb2f546747de89a529f55d48f0ff9a264430'
TASKS = ('aerial-cactus-identification', 'denoising-dirty-documents')


def main():
    assert m.sha(ROOT / LINEAGE) == PIN
    origin = m.load(ROOT / LINEAGE)
    def source(rel, lines=False):
        assert m.sha(ROOT / rel) == origin['source_hashes'][rel]
        result = m.load(ROOT / rel, lines)
        assert m.sha(ROOT / rel) == origin['source_hashes'][rel]
        return result

    output = []
    for block in range(4):
        events = source(f'generation-{block}/events.jsonl', True)
        slot = source(f'block-{block}/budget-slot.json')
        deadlines = {i: datetime.fromisoformat(source(f'episode-{i}/deadline.json')['started_utc']).timestamp()+1020
                     for i in range(8*block, 8*block+8)}
        waiting, active, requests = {}, {}, {}
        clock = slot['start']
        borrow = defaultdict(float)
        borrow_300 = defaultdict(float)
        release = {}
        after_release = {}
        links = {}
        valid_publications = []
        by_hash = defaultdict(list)
        for c in (x for x in origin['candidates'] if x['block'] == block):
            receipt = source(f"episode-{c['index']}/candidate-{c['candidate']}.json")
            by_hash[c['index'], receipt['code_sha256']].append(c)

        for e in events:
            now = e['time']; assert clock <= now
            counts = Counter(r['task'] for r in active.values())
            if len(active) < 4:
                for key, r in waiting.items():
                    if counts[r['task']] == 2:
                        borrow[key] += now-clock
                        borrow_300[key] += max(0., min(now-clock, deadlines[r['run']]-clock-300))
            clock = now
            kind = e['event']; i = e['run']
            if kind == 'queued':
                r = e['request']; key = r['key']
                assert key not in requests
                requests[key] = r; waiting[key] = r
                after_release.pop(i, None)
            elif kind == 'admitted':
                key = e['key']; active[key] = waiting.pop(key)
            elif kind == 'released':
                key = e['key']; r = active.pop(key); release[key] = now
                after_release[i] = key if r['role'] == 'analyze' else None
            elif kind == 'cancelled':
                waiting.pop(e['key']); after_release.pop(i, None)
            elif kind == 'round_complete':
                key = after_release.pop(i, None)
                if key is not None:
                    assert key not in links and requests[key]['role'] == 'analyze'
                    matches = [c for c in by_hash[i, e['code_sha256']]
                               if slot['start']+c['pool_elapsed'] <= now+.01]
                    # No nearest-time guesses or repair of a missing receipt.
                    if len(matches) == 1:
                        c = matches[0]
                        assert requests[key]['requested'] >= slot['start']+c['pool_elapsed']-.01
                        links[key] = dict(candidate=c['candidate'], external_valid=c['valid'],
                                          native_valid=e['valid'], score=c['score'], publication_time=now)
                        if e['valid']:
                            assert c['valid']
                            valid_publications.append((now, key, c))
                    else:
                        links[key] = dict(association_unknown=True, matches=len(matches))
            elif kind not in ('warm_start','parent_used','abandoned'):
                raise ValueError('unrecognized event')
        assert not waiting and not active
        best = {g['task']:g['initial'] for g in origin['groups'] if g['block'] == block}
        for now, key, c in sorted(valid_publications):
            sign = 1 if c['task'] == TASKS[0] else -1
            gain = sign*(c['score']-best[c['task']])
            links[key]['gain_vs_prior_matched_published_best'] = gain
            links[key]['new_published_best'] = gain > 1e-12
            if gain > 1e-12:
                best[c['task']] = c['score']
        rows = []
        for key, r in requests.items():
            if r['role'] != 'analyze':
                continue
            rows.append(dict(key=key, index=r['run'], task=r['task'], released=key in release,
                             observed_borrowable_wait_seconds=borrow[key],
                             borrowable_wait_with_300s_remaining=borrow_300[key],
                             linked=key in links, **links.get(key, {})))
        round_valid = sum(e['event']=='round_complete' and e['valid'] for e in events)
        assert round_valid == len(valid_publications), 'unmatched published valid result; cannot infer incumbent'
        output.append(dict(block=block, rows=rows, published_valid=round_valid,
                           new_best_publications=sum(r.get('new_published_best',False) for r in rows),
                           borrowable_request_seconds_by_role={role:sum(v for k,v in borrow.items() if requests[k]['role']==role)
                                                              for role in ('improve','debug','analyze')}))
    rows = [r for p in output for r in p['rows']]
    summary = dict(analyze_requests=len(rows), linked=sum(r['linked'] for r in rows),
                   published_valid=sum(p['published_valid'] for p in output),
                   new_best_publications=sum(p['new_best_publications'] for p in output),
                   blocked_analyze=sum(r['observed_borrowable_wait_seconds']>0 for r in rows),
                   blocked_new_best=sum(r.get('new_published_best',False) and r['observed_borrowable_wait_seconds']>0 for r in rows),
                   blocked_new_best_with_300s=sum(r.get('new_published_best',False) and r['borrowable_wait_with_300s_remaining']>0 for r in rows))
    result = dict(reader_sha256=m.sha(__file__), helper_sha256=m.sha(m.__file__), lineage_sha256=PIN,
                  pools=output, summary=summary,
                  limits=['Post-hoc same-worker phase association; no earlier-publication counterfactual or saved-time claim.',
                          'A new best refers to prior actual published valid results, not predicted value of a future child.',
                          'Debug requests are not linked to outcomes here. No conclusion that their waiting is useless.',
                          'No model, GPU, new score, old readout, or original protocol change.'])
    dest = Path(__file__).with_name('quota-feedback-link-20261017.safe.json')
    with dest.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps(dict(sha256=m.sha(dest),summary=summary)))


if __name__ == '__main__':
    main()
