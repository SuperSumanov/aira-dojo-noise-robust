#!/usr/bin/env bash
# Offline (no GPU/LLM) validation of the HCE grading path per task/grader type.
# Uses a PERFECT submission (= the answers) -> every arm should score ~perfect (acc/AUC ~1.0,
# RMSLE ~0). This catches id-alignment / subsetting / stratification bugs across grader types
# (spaceship=id-merge accuracy, nomad=positional RMSLE, s3e18=AUC) without burning a GPU run.
# Usage: bash test_hce_graders.sh [task1 task2 ...]
source ~/env_setup.sh 2>/dev/null
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
"$PY" - "$@" <<'PYEOF'
import sys
from pathlib import Path
import pandas as pd
from mlebench.registry import registry
from mlebench.utils import load_answers
from dojo.tasks.mlebench import hce_eval as hce

DATA = "/research/d7/spc/yzyang4/mle-bench-data"
tasks = sys.argv[1:] or ["spaceship-titanic", "nomad2018-predict-transparent-conductors"]
reg = registry.set_data_dir(Path(DATA))
for t in tasks:
    try:
        comp = reg.get_competition(t)
        ans = load_answers(comp.answers)
        lower = comp.grader.is_lower_better(pd.read_csv(comp.leaderboard))
        print(f"\n=== {t} ===  answers shape={ans.shape} cols={list(ans.columns)} lower_is_better={lower}")
        split = hce.make_hce_split(len(ans), 0.5, 0.25, 0)
        print(f"  split: search={len(split['search'])} val={len(split['val'])} test={len(split['test'])}")
        sub = ans.copy()  # PERFECT submission
        for arm in ["full", "naive", "consistency"]:
            fit, info = hce.dsearch_fitness(comp.grader, sub, ans, split, arm,
                                            proxy_frac=0.1, k=3, lam=1.0, maximize=not lower, eval_seed=[1, 0])
            dval = hce.grade_subset(comp.grader, hce._align_submission(sub, ans), ans, split["val"])
            print(f"  arm={arm:11s} Dsearch_fit={fit}  dval={dval}  info={info}")
    except Exception as e:
        import traceback
        print(f"  ERROR on {t}: {e}")
        traceback.print_exc()
print("HCE_GRADER_TEST_DONE")
PYEOF
