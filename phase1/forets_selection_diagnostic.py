"""Post-run mechanism diagnostic for the explicit ForeTS development campaign.

No model/task/API calls, no scores for unexecuted code, no alternate final metric.
Only the caller-verified terminal job's package may be read. Never use on a cohort.
"""
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from forets_e2e_readout import _inside, _json, validate_manifest
from forets_selection_20260908 import choose_slots

PACKAGE = Path('/research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/package-c')
SOURCE_TREE = '2ff5277ba17327c6c03326a018b59f704402af6b'
SELECTOR_SHA = '6f5d1b3c4f02abc78a0cab652f4b3edc6f7dbf1419bf375a07760ea3172050e5'
RESILIENCE_PACKAGE = Path('/research/d7/spc/yzyang4/forets-resilience-20260910-4LGN21/package')
RESILIENCE_TREE = 'bbd22e323d6321925a145c12bdc02445c1ad80f4'


def diagnose_snapshot(data, *, task, seed, policy, step):
    """Counts only; same-pool slot replay is not a counterfactual search outcome."""
    binding = data.get('binding', {})
    if (data.get('schema') != 4 or binding.get('schema') != 4 or
            binding.get('task') != task or binding.get('selection_policy') != policy or
            type(binding.get('step')) is not int or binding['step'] != step or
            type(step) is not int or not 0 <= step < 4):
        raise ValueError('snapshot binding mismatch')
    if binding.get('score_bypass') is not None:
        raise ValueError('submitted campaign has bypass disabled')
    candidates = data.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != min(4, 4-step):
        raise ValueError('unexpected candidate budget')
    phases = {'collecting', 'selected', 'executing', 'complete'}
    states = {'pending', 'generating', 'generated', 'scoring', 'scored',
              'executing', 'completed', 'skipped_budget'}
    if data.get('phase') not in phases or any(c.get('state') not in states for c in candidates):
        raise ValueError('unknown phase or candidate state')
    scores = [c.get('score') for c in candidates]
    known = [s for s in scores if s is not None]
    if any(type(s) not in (int, float) or not math.isfinite(s) for s in known):
        raise ValueError('invalid score')
    if policy == 'uniform_random' and known:
        raise ValueError('random arm unexpectedly contains critic scores')
    count = len(candidates)
    row = dict(step=step, phase=data['phase'], candidate_count=count,
               known_score_count=len(known), selection_recorded=False,
               selected_execution_completed=None, replay_matches=None,
               full_pool_no_pruning=count <= 2, cutoff_tie=None,
               all_scores_equal=None, strictly_separated_cutoff=None,
               coupled_random_slot_differs=None, coupled_random_excluded=None)
    selected = data.get('selected')
    if selected is None:
        if data['phase'] != 'collecting':
            raise ValueError('selection absent after collecting')
        return row
    if (not isinstance(selected, list) or len(selected) != 1 or
            type(selected[0]) is not int or not 0 <= selected[0] < count):
        raise ValueError('invalid selected slot')
    if data['phase'] == 'collecting':
        raise ValueError('selection in collecting phase')
    if any(c.get('node') is None for c in candidates) or not data.get('pool_sha256'):
        raise ValueError('selected pool incomplete')
    critic = policy == 'critic_topk_random'
    if critic and len(known) != count:
        raise ValueError('selected critic pool missing scores')
    ready_state = 'scored' if critic else 'generated'
    for slot, candidate in enumerate(candidates):
        allowed = {ready_state, 'executing', 'completed', 'skipped_budget'} if slot in selected else {ready_state}
        if candidate['state'] not in allowed:
            raise ValueError('candidate state incompatible with recorded selection')
    if data['phase'] == 'complete' and candidates[selected[0]]['state'] not in {'completed', 'skipped_budget'}:
        raise ValueError('completed batch has unfinished selection')
    expected = choose_slots(count, 2, 1, policy, seed, task, step, scores if critic else None)
    random_slot = choose_slots(count, 2, 1, 'uniform_random', seed, task, step)[0]
    if expected != selected:
        raise ValueError('stored selection disagrees with frozen selector')
    row.update(selection_recorded=True, replay_matches=True,
               selected_execution_completed=candidates[selected[0]]['state'] == 'completed',
               coupled_random_slot_differs=selected[0] != random_slot)
    if critic:
        ranked = sorted(range(count), key=lambda i: scores[i], reverse=True)
        row['all_scores_equal'] = len(set(scores)) == 1
        row['coupled_random_excluded'] = random_slot not in ranked[:min(2, count)]
        if count > 2:
            row['cutoff_tie'] = scores[ranked[1]] == scores[ranked[2]]
            row['strictly_separated_cutoff'] = not row['cutoff_tie']
    return row


def read_snapshot(path):
    """Read-only SQLite, closed explicitly; never emit payload/code/prompt/values."""
    if path.with_suffix(path.suffix+'.lock').exists():
        raise ValueError('writer lock still present')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64*1024**2:
        raise ValueError('invalid or oversized ledger')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=0)) as conn:
        conn.execute('PRAGMA query_only=ON')
        rows = conn.execute('SELECT payload, sha256 FROM snapshot WHERE id=1').fetchall()
    if len(rows) != 1:
        raise ValueError('missing snapshot')
    payload, digest = rows[0]
    if hashlib.sha256(payload.encode()).hexdigest() != digest:
        raise ValueError('snapshot hash mismatch')
    return _json(payload)


def analyze_package(root, *, deployment='12933'):
    # An explicit allowlist, not an arbitrary corpus/path override. Neither
    # deployment changes the frozen selector, top-k or four-step semantics.
    if deployment == '12933':
        expected_root, source_tree = PACKAGE, SOURCE_TREE
    elif deployment == '13004':
        expected_root, source_tree = RESILIENCE_PACKAGE, RESILIENCE_TREE
    else:
        raise ValueError('unknown reviewed development deployment')
    root = Path(root).resolve(strict=True)
    if root != expected_root.resolve(strict=True):
        raise ValueError('only the explicit development package is admitted')
    # This is not a scheduler-terminal proof. Caller must separately check sacct.
    for filename in ('campaign.started.json', 'campaign.finished.json'):
        if not (root/filename).is_file():
            raise ValueError('campaign is not ready for post-run reading')
    submission = (root if deployment == '12933' else root.parent) / 'submission.json'
    if (_json(submission.read_text())['job_id'] != deployment or
            _json((root/'campaign.started.json').read_text())['allocation_id'] != deployment):
        raise ValueError('wrong allocation')
    manifest = _json((root/'runtime-manifest.json').read_text())
    if manifest['source_tree'] != source_tree:
        raise ValueError('wrong experiment source')
    validate_manifest(manifest, root)  # Checks all eight paths before ledger reads.
    prepared = _json((root/'manifest.json').read_text())
    validate_manifest(prepared, root)
    if prepared['source_tree'] != source_tree:
        raise ValueError('wrong prepared source')
    prepared_by_id = {r['run_id']: r for r in prepared['runs']}
    runs = []
    for entry in manifest['runs']:
        task, seed, policy = (entry[k] for k in ('task', 'seed', 'policy'))
        cfg_path = _inside(root, 'configs/'+entry['run_id']+'.json')
        payload = cfg_path.read_bytes()
        original = prepared_by_id[entry['run_id']]
        if any(original[k] != entry[k] for k in ('run_id', 'run_dir', 'task', 'seed', 'policy')):
            raise ValueError('runtime/preparation identity mismatch')
        # Runtime pool may reserialize identical JSON with different whitespace.
        # Its original equality check is in the frozen campaign controller;
        # here verify preparation bytes against their own manifest, not its hash.
        if hashlib.sha256(payload).hexdigest() != original['config_sha256']:
            raise ValueError('config hash mismatch')
        cfg = _json(payload.decode())['solver']
        if (cfg['selection_policy'] != policy or cfg['selector_seed'] != seed or
                cfg['num_children'] != 4 or cfg['critic_top_k'] != 2 or
                cfg['num_children_to_choose'] != 1 or cfg['skip_redundant_critic'] is not False or
                cfg['step_limit'] != 4):
            raise ValueError('config outside diagnostic contract')
        checkpoint = _inside(root, entry['run_dir']+'/checkpoint')
        if Path(cfg['checkpoint_path']).resolve() != checkpoint:
            raise ValueError('checkpoint identity mismatch')
        # Only four exact paths, no recursive discovery, no cross-run pool matching.
        batches, missing = [], []
        for step in range(4):
            path = _inside(root, entry['run_dir']+f'/checkpoint/forets-candidates-private/batch-{step}.sqlite')
            if not path.exists():
                missing.append(step)
                continue
            try:
                row = diagnose_snapshot(read_snapshot(path), task=task, seed=seed, policy=policy, step=step)
                row['issue'] = None
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
                # No exception text: it might contain parts of a private payload.
                row = dict(step=step, issue='invalid_or_unreadable_snapshot')
            batches.append(row)
        valid = [b for b in batches if b.get('selection_recorded') and b.get('issue') is None]
        pruning = [b for b in valid if not b['full_pool_no_pruning'] and policy == 'critic_topk_random']
        runs.append(dict(run_id=entry['run_id'], task=task, seed=seed, policy=policy,
            observed_ledgers=len(batches), missing_step_files=missing,
            invalid_ledgers=sum(b.get('issue') is not None for b in batches),
            recorded_selections=len(valid), critic_pruning_selections=len(pruning),
            cutoff_tied_pruning_selections=sum(b['cutoff_tie'] for b in pruning),
            all_equal_pruning_selections=sum(b['all_scores_equal'] for b in pruning),
            coupled_random_different_selections=sum(b['coupled_random_slot_differs'] for b in valid),
            batches=batches))
    return dict(role='forets_e2e_development_diagnostic', job_id=deployment, source_tree=source_tree,
        runs=runs, limitations=[
            'No final score, candidate code, prompt, identity or critic score values exported.',
            'Missing step files may reflect debug jumps, early stop, failure or no start; not inferred.',
            'Same-pool coupled random slot is not the other arm or its unobserved final score.',
            'Ties can change selected slots through slot-order tie breaking, not learned discrimination.',
            'Recorded selection is not completed execution; no ranking accuracy or utility claim.',
            'The original full eight-run final-score readout remains primary.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deployment', choices=('12933', '13004'), default='12933')
    args = parser.parse_args()
    selector_path = Path(__file__).with_name('forets_selection_20260908.py')
    if hashlib.sha256(selector_path.read_bytes()).hexdigest() != SELECTOR_SHA:
        raise ValueError('local replay selector differs from the frozen production file')
    result = analyze_package(args.package, deployment=args.deployment)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status':'DIAGNOSTIC_ONLY', 'runs':len(result['runs'])}))


if __name__ == '__main__':
    main()
