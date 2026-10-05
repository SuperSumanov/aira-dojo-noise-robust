"""Complete failed preflight without changing frozen experimental artifacts.

The original path-substring assertion rejects the established Tweet view solely
because its directory name differs. Replace it with exact two-task allowlisting.
No sample, candidate, budget, seed, source or scorer is changed.
"""
import copy
import json
from pathlib import Path
import re
import subprocess
from run_collateral_factorial_20261006 import B, R, check, read, runtime, schedule, sha, write

VIEWS = {
    'random-acts-of-pizza': ('search-only-dev-pizza-20260927-v1',
        '3a6b75e6ce6b391dd04bb6ac668c063cae90c2270411f5503e493ae8d90991ae'),
    'tweet-sentiment-extraction': ('tweet-search-only-20260927-a4d1',
        '5a63eedbdffa1881f6baebe4df15b69d2f51cd3a51a036857d4b122fdee0a561'),
}

def main():
    check()
    assert not (R/'preflight.json').exists() and not (R/'launch.json').exists()
    runtime()
    from dojo.config_dataclasses.run import RunConfig
    fairness = {}
    for s in schedule():
        p = R/'configs'/f"{s['index']}.json"
        cfg = RunConfig.load_from_json(p)
        cfg.validate()
        view, scorer_sha = VIEWS[s['task']]
        public = B/view/'public'
        assert cfg.task.name == s['task']
        assert Path(cfg.task.data_dir) == Path(cfg.task.public_dir) == public
        assert public.is_dir() and not public.is_symlink()
        assert Path(cfg.task.private_dir) == B/view/'private-unavailable'
        assert not Path(cfg.task.private_dir).exists()
        assert not cfg.interpreter.read_only_binds
        assert sha(cfg.task.search_only_dev_scorer_path) == cfg.task.search_only_dev_scorer_sha256 == scorer_sha
        x = read(p)
        t = copy.deepcopy(x['task']); t.pop('results_output_dir', None)
        it = copy.deepcopy(x['interpreter']); it.pop('working_dir', None)
        sig = json.dumps([t, it], sort_keys=True)
        assert s['case'] not in fairness or fairness[s['case']] == sig
        fairness[s['case']] = sig
    for i in range(32):
        assert re.fullmatch('episode-(?:[0-9]|[12][0-9]|3[01])', f'episode-{i}')
    assert not re.fullmatch('episode-(?:[0-9]|[12][0-9]|3[01])', 'episode-32')
    subprocess.run(['bash', '-n', str(R/'run.sbatch')], check=True)
    check()
    receipt = dict(status='PASS', typed_configs=32, matched_quartets=len(fairness),
        plan_sha256=sha(R/'plan.json'), validator_sha256=sha(__file__),
        original_failure='Preflight substring /search-only-dev- rejects previously authorized tweet-search-only directory.',
        correction='Exact two-task public-view allowlist; original frozen files unchanged.',
        source_variants_frozen=True, program_cap_matches_historical_cost_screen=True,
        protected_opened=False)
    write(R/'preflight.json', receipt)
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
