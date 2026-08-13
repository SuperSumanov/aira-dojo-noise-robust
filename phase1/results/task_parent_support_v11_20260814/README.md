# v11 task/parent support audit

Status: **`AUDIT_COMPLETE`**. This is a train-only structural audit, not a model
result and not an unlock decision. It reads `decision_train_v11_b0.jsonl` plus
the locked physical-run fold column from the prior training OOF output. It has
no frozen/test-pair argument and reports `frozen_read=false`.

## Exact support

- 4,263 training sibling pairs, 333 physical runs, 23 tasks, 2,293 parents,
  and 5,499 endpoints;
- 2,259/2,293 parents are complete comparison graphs, and all 2,259 form a
  strict total order;
- 773/2,293 parents (33.7113%) contain at least three candidates;
- those multi-candidate parents contribute 2,743/4,263 pairs (64.3444%);
- locked outer folds have zero physical-run overlap.

The multi-candidate mass is large enough that a parent-centered objective is
not merely a relabeling of binary pairs. Support is nevertheless highly uneven:
several tasks have only two or three runs, and one active outer fold has no fit
run for `text-normalization-challenge-english-language`. Therefore 23
independent task heads are structurally invalid. The next admissible candidate
is a shared global head plus regularized task residuals, with an exact global
fallback when a task is absent from an outer-fit partition.

## Files

- `audit.json`: complete global/fold/task support and input hashes;
- `per_task.csv`: compact task-level support table;
- `phase1/task_parent_support_audit.py`: deterministic producer;
- `phase1/tests/test_task_parent_support_audit.py`: forbidden-path,
  run-isolation, and complete-order tests (2 passed remotely).

No model accuracy was used to choose task eligibility, and this audit does not
change the completed frozen-embedding gate.

The JSON records both raw checkout hashes and canonical-LF hashes. This matters
because the Windows worktree may materialize CRLF while the formal cluster
launcher locks the LF bytes; row identity and the canonical-LF hash remain
portable across the two environments.
