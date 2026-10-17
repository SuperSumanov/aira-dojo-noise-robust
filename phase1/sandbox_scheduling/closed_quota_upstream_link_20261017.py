"""Complete the upstream diagnostic: exact serial generation->publication links.

No score-dependent request inclusion. Returned/unknown requests stay explicit;
no changed-duration replay or causal attribution to the observed waiting.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import closed_adaptation_lineage_20261017 as m
from closed_quota_feedback_link_20261017 import ROOT, LINEAGE, PIN


def main():
    assert m.sha(ROOT / LINEAGE) == PIN
    lineage = m.load(ROOT / LINEAGE)
    phase_path = Path(__file__).with_name('quota-feedback-link-20261017.safe.json')
    assert m.sha(phase_path) == 'cddfd609f92720f3547528ed420973f2931fef06273bab064ec0afa3cc1f30b9'
    phase = m.load(phase_path)
    def source(rel, lines=False):
        assert m.sha(ROOT / rel) == lineage['source_hashes'][rel]
        result = m.load(ROOT / rel, lines)
        assert m.sha(ROOT / rel) == lineage['source_hashes'][rel]
        return result

    pools = []
    for block in range(4):
        events = source(f'generation-{block}/events.jsonl', True)
        requests, waiting, active, latest, released = {}, {}, {}, {}, set()
        blocked = defaultdict(float)
        last = events[0]['time']
        result = []
        candidates = {(c['index'], c['candidate']): c for c in lineage['candidates'] if c['block'] == block}
        linked = {(r['index'], r.get('publication_time')): r for r in phase['pools'][block]['rows'] if r.get('publication_time') is not None}
        linked_generation = set()
        for e in events:
            now = e['time']; assert now >= last
            count = Counter(r['task'] for r in active.values())
            if len(active) < 4:
                for key, r in waiting.items():
                    if count[r['task']] == 2: blocked[key] += now-last
            last = now
            kind = e['event']; i = e['run']
            if kind == 'queued':
                r = e['request']; key = r['key']; requests[key] = r; waiting[key] = r
                if r['role'] in ('improve', 'debug'): latest[i] = key
            elif kind == 'admitted': active[e['key']] = waiting.pop(e['key'])
            elif kind == 'released': active.pop(e['key']); released.add(e['key'])
            elif kind == 'cancelled': waiting.pop(e['key'])
            elif kind == 'round_complete':
                key = latest.pop(i, None); association = linked.get((i, now))
                if key is None or association is None: continue
                assert key in released and key not in linked_generation
                r = requests[key]; role = r['role']; assert role in ('improve', 'debug')
                c = candidates[i, association['candidate']]
                receipt = source(f"episode-{i}/candidate-{c['candidate']}.json")
                assert e['code_sha256'] == receipt['code_sha256']
                nodes = source(f'episode-{i}/checkpoint/journal.jsonl', True)
                exact = [n for n in nodes if isinstance(n.get('code'), str) and m.codehash(n['code']) == e['code_sha256']]
                journal_roles = {tuple(n.get('operators_used', [])) for n in exact}
                supported = bool(exact) and all(role in roles for roles in journal_roles)
                if role == 'improve':
                    generated = [v for v in events if v['event']=='parent_used' and v['key']==key]
                    supported = supported and len(generated)==1 and generated[0]['child']==e['code_sha256']
                linked_generation.add(key)
                result.append(dict(key=key, index=i, candidate=c['candidate'], role=role, task=r['task'],
                                   journal_role_supported=supported, valid=c['valid'], native_valid=e['valid'],
                                   new_published_best=association.get('new_published_best',False),
                                   observed_borrowable_wait_seconds=blocked[key],
                                   gain_vs_prior_published_best=association.get('gain_vs_prior_matched_published_best')))
        assert not active and not waiting
        for role, expected in phase['pools'][block]['borrowable_request_seconds_by_role'].items():
            assert abs(sum(v for k,v in blocked.items() if requests[k]['role']==role)-expected)<1e-6
        all_generations = [dict(key=k,index=r['run'],task=r['task'],role=r['role'],released=k in released,
                                linked_publication=k in linked_generation,observed_borrowable_wait_seconds=blocked[k])
                           for k,r in requests.items() if r['role'] in ('improve','debug')]
        pools.append(dict(block=block, generations=all_generations, published=result))
    generations = [r for p in pools for r in p['generations']]
    published = [r for p in pools for r in p['published']]
    summary = dict(generation_requests=len(generations), linked_publications=len(published),
                   journal_supported=sum(r['journal_role_supported'] for r in published),
                   debug_requests=sum(r['role']=='debug' for r in generations),
                   debug_valid=sum(r['role']=='debug' and r['valid'] for r in published),
                   debug_new_best=sum(r['role']=='debug' and r['new_published_best'] for r in published),
                   debug_blocked_new_best=sum(r['role']=='debug' and r['new_published_best'] and r['observed_borrowable_wait_seconds']>0 for r in published))
    output = dict(reader_sha256=m.sha(__file__),lineage_sha256=PIN,phase_sha256=m.sha(phase_path),pools=pools,summary=summary,
                  limits=['Same-worker serialized-phase association plus exact journal role/code check where available; unknown remains unknown.',
                          'Observed borrowed-slot exposure is request-seconds, NOT saved time or benefit of a new scheduler.',
                          'Valid children from Debug need not beat the best archive; no automatic discard or oracle selection.',
                          'Closed DEV data only; no GPU/model/scoring, no changes to old primary gate or artifacts.'])
    dest = Path(__file__).with_name('quota-upstream-link-20261017.safe.json')
    with dest.open('x') as f: json.dump(output,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(sha256=m.sha(dest),summary=summary)))


if __name__ == '__main__': main()
