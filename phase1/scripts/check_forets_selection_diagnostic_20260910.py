"""Real frozen ledger writer, artificial candidates; no task/model/API calls."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_selection_diagnostic import diagnose_snapshot, read_snapshot, analyze_package, PACKAGE
from forets_selection_20260908 import choose_slots

LEDGER = Path('/research/d7/spc/yzyang4/forets-nonpruning-20260909-Wmfn3x/source-v5/src/dojo/solvers/fore_ts/candidate_ledger.py')
LEDGER_SHA = 'f0bba9b9887f03197fd3def8e5c479d4c8b98f160398c46ae1d6ce7ba109e4eb'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('no overwrite')
    if hashlib.sha256(LEDGER.read_bytes()).hexdigest() != LEDGER_SHA:
        raise ValueError('frozen ledger source changed')
    spec = importlib.util.spec_from_file_location('frozen_ledger', LEDGER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = [('critic_distinct',0,'critic_topk_random',[.9,.8,.2,.1]),
             ('critic_all_ties',0,'critic_topk_random',[.5]*4),
             ('critic_cutoff_tie',0,'critic_topk_random',[.9,.4,.4,.1]),
             ('critic_full_pool',2,'critic_topk_random',[.8,.1]),
             ('random_no_scores',0,'uniform_random',None),
             ('partial_generation',0,'critic_topk_random',None)]
    checked = []
    with tempfile.TemporaryDirectory(prefix='forets-artificial-diagnostic-', dir='/tmp') as tmp:
        for name,step,policy,scores in cases:
            path = Path(tmp)/name/'batch.sqlite'
            count = 4-step
            binding = dict(schema=4, task='leaf-classification', step=step,
                           selection_policy=policy)
            with module.CandidateLedger(path, binding, count) as ledger:
                for i in range(1 if name=='partial_generation' else count):
                    ledger.begin_generation(i)
                    ledger.generated(i, dict(id=f'artificial-{i}',ctime=0.,code='print(1)',
                        plan='',operators_used=[],operators_metrics=[]))
                if name != 'partial_generation':
                    ledger.freeze_pool()
                    if scores is not None:
                        for i,score in enumerate(scores):
                            ledger.begin_score(i);ledger.scored(i,score)
                    ledger.select(choose_slots(count,2,1,policy,6,'leaf-classification',step,scores))
                    ledger.finish()  # No task call: selection is marked skipped_budget.
            before = path.read_bytes()
            row = diagnose_snapshot(read_snapshot(path),task='leaf-classification',seed=6,policy=policy,step=step)
            assert path.read_bytes() == before
            assert not row['selected_execution_completed']
            if name=='critic_distinct': assert row['strictly_separated_cutoff'] is True
            if name=='critic_all_ties': assert row['all_scores_equal'] and row['cutoff_tie']
            if name=='critic_cutoff_tie': assert row['cutoff_tie'] and not row['all_scores_equal']
            if name=='critic_full_pool': assert row['full_pool_no_pruning'] and not row['coupled_random_slot_differs']
            if name=='random_no_scores': assert row['known_score_count']==0 and row['cutoff_tie'] is None
            if name=='partial_generation': assert not row['selection_recorded'] and row['coupled_random_slot_differs'] is None
            checked.append(name)
    # Only test the early refusal while this package has not finished. Do not
    # read real candidate data if the job changes state during this CPU check.
    gate = 'not_checked_after_state_change'
    if not (PACKAGE/'campaign.finished.json').exists():
        try:
            with patch('forets_selection_diagnostic.read_snapshot', side_effect=AssertionError('real ledger read forbidden in fixture check')):
                analyze_package(PACKAGE)
        except ValueError as exc:
            if str(exc) != 'campaign is not ready for post-run reading': raise
            gate = 'refused_before_any_development_ledger_read'
        else:
            raise AssertionError('unfinished campaign admitted')
    phase_dir = Path(__file__).resolve().parents[1]
    report = dict(status='ARTIFICIAL_INTEGRATION_PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        checks=checked,check_count=len(checked),real_frozen_ledger_writer_sha256=LEDGER_SHA,
        diagnostic_sha256=hashlib.sha256((phase_dir/'forets_selection_diagnostic.py').read_bytes()).hexdigest(),
        pending_campaign_gate=gate,real_task_executions=0,model_loads=0,gpu_jobs=0,external_api_calls=0,
        protected_data_read=False,real_candidate_ledgers_read=False,
        scope='Actual schema-4 writer, artificial candidates/scores; not model benefit or execution evidence.')
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
