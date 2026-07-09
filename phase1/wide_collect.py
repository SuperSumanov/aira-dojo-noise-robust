"""Wide sibling collection for C1 (noise-aware offline preference distillation).

Reuses aira's GreedySolver **unchanged** but monkeypatches its `search_policy` at import so that each
draft-seed node is improved exactly K times -> K siblings under the same parent. This gives DENSE
sibling groups (the thing MCTS starves), and a large K compensates the ~33% grade rate so each group
still yields several *graded* siblings -> many preference pairs. No aira core edit; we just swap a
method then hand off to aira's hydra entrypoint.

Run (via sbatch):
  WC_K=12 python -m phase1.wide_collect +_exp=mlebench/deepseek_greedy_spaceship \
      solver.num_drafts=6 solver.debug_prob=0.0 solver.step_limit=78 \
      solver.time_limit_secs=72000 metadata.git_issue_id=wide_collect_spaceship metadata.seed=801 \
      logger.use_wandb=False

Design: only the ORIGINAL draft nodes are used as parents (not improve-of-improve), so siblings share
one clean parent context. step_limit should be >= num_drafts * (K+1) so every seed gets its K improves.
"""
import os

K = int(os.environ.get("WC_K", "12"))          # siblings (improve attempts) per draft parent


def _wide_search_policy(self):
    """Draft `num_drafts` seeds, then improve each seed exactly K times (K siblings/parent)."""
    # phase 1 — seed drafts
    if len(self.journal.draft_nodes) < self.cfg.num_drafts:
        return None
    # phase 2 — round-robin: pick an unfinished draft seed, return it K times, then retire it
    if not hasattr(self, "_wc_done"):
        self._wc_done, self._wc_cur, self._wc_cnt = set(), None, 0
    if self._wc_cur is None or self._wc_cnt >= K:
        seeds = [n for n in self.journal.draft_nodes if id(n) not in self._wc_done]
        if not seeds:
            return None            # all seeds exhausted -> (draft more / terminate at step_limit)
        self._wc_cur, self._wc_cnt = seeds[0], 0
        self._wc_done.add(id(self._wc_cur))
    self._wc_cnt += 1
    return self._wc_cur            # non-None + non-buggy seed -> GreedySolver calls _improve(parent)


if __name__ == "__main__":
    # import aira FULLY first (patching at module top-level triggers a circular import), then patch
    from dojo.main_run import main
    from dojo.solvers.greedy.greedy import Greedy
    Greedy.search_policy = _wide_search_policy
    main()
