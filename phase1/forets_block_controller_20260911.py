"""Fixed-block ForeTS controller core, not a production launch entry point.

The CLI only inspects the already prepared draft. The pool mixin is for the new
adapter, not the frozen 13004 campaign. OpenCL isolation, historical model input,
bounded service startup/cleanup and fresh route readiness remain unimplemented
at the live front door. No credentials, model, task results or scheduler are
accessed by this module's CLI. Do not promote a draft by changing a boolean.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

TREE = '3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
PREPARED_SHA = 'd6fcf987924bf696c8a6ea7fb252a6a634ad3fdac9de192a24eb07ec63fee76d'
CORRECTION_SHA = '2137b4e96c365351af1fe1b0d104b71dc15b67831e485ce5641142578b9bb408'
ROLE = 'forets_e2e_config_draft_not_launchable'
ALLOCATION_SECONDS = 280 * 60
STARTUP_SECONDS = 900
CLEANUP_SECONDS = 30
STEP_WITH_TERMINATION_SECONDS = 3930
POLL_SECONDS = 5


def expected_order():
    rows = []
    for block, seed in enumerate((8, 9), 1):
        for task_index, task in enumerate(('leaf-classification', 'spaceship-titanic')):
            arms = ['uniform_random', 'critic_topk_random']
            if (block - 1 + task_index) % 2:
                arms.reverse()
            for arm in arms:
                rows.append((block, task, seed, arm))
    return tuple(rows)


@dataclass(frozen=True)
class BlockSpec:
    block: int
    run_ids: tuple[str, ...]
    launcher: dict


def block_spec(prepared, block):
    if type(block) is not int or block not in (1, 2):
        raise ValueError('block must be exactly 1 or 2; no outcome-selected subset')
    if prepared.get('source_tree') != TREE or prepared.get('readiness') is not False:
        raise ValueError('not the frozen preparation')
    rows = prepared['run_configs']
    if tuple((r['block'], r['task'], r['seed'], r['arm']) for r in rows) != expected_order():
        raise ValueError('matrix or order changed')
    for i, r in enumerate(rows):
        if r['run_id'] != f"{i:02d}-{r['task']}-s{r['seed']}-{r['arm']}":
            raise ValueError('run identity changed')
    return BlockSpec(block, tuple(r['run_id'] for r in rows if r['block'] == block),
                     dict(prepared['launcher']))


def _read(path, expected=None, *, root=None):
    if path.is_symlink() or (root is not None and not path.resolve().is_relative_to(root)):
        raise ValueError('configuration link escapes the explicit draft')
    with path.open('rb') as stream:
        raw = stream.read(2**21 + 1)
    if len(raw) > 2**21:
        raise ValueError('unexpectedly large configuration')
    if expected and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('pinned artifact changed')
    return json.loads(raw)


def inspect_draft(root, block):
    """Bounded explicit configuration reads only; never inspect run folders."""
    root = Path(root).resolve(strict=True)
    prepared = _read(root / 'prepared.json', PREPARED_SHA, root=root)
    if str(root) != prepared['output']:
        raise ValueError('draft moved; embedded paths cannot be silently rebound')
    state = _read(root / 'PACKAGE_STATE.json', root=root)
    correction = _read(root / 'allocation-budget-correction.json', CORRECTION_SHA, root=root)
    if (state.get('execution_allowed') is not False or state.get('readiness') is not False
            or correction['proposed_block_minutes'] != 280):
        raise ValueError('draft promotion is not supported')
    manifest = _read(root / 'manifest.json', root=root)
    if manifest.get('role') != ROLE or manifest.get('source_tree') != TREE:
        raise ValueError('unexpected package role or source')
    if manifest['runs'] != prepared['run_configs']:
        raise ValueError('manifest differs from pinned preparation')
    spec = block_spec(prepared, block)
    launcher = _read(root / 'launchers' / f'block-{block}.json', root=root)
    if launcher != spec.launcher:
        raise ValueError('launcher budget changed')
    configs = []
    for row in prepared['run_configs']:
        if row['run_id'] in spec.run_ids:
            configs.append(_read(root / 'configs' / (row['run_id'] + '.json'), row['config_sha256'], root=root))
    return spec, configs


class BlockPoolControl:
    """Mixin for the pinned SrunPoolLauncher. Attach before calling run().

    Real service/process setup is deliberately absent. Tests exercise the actual
    pinned pool with only OS boundaries replaced; they are not GPU acceptance.
    A future live adapter must enforce startup/cleanup deadlines even while it is
    blocked in service startup or path validation, not merely check afterwards.
    """

    def configure_block(self, spec, service_alive):
        if hasattr(self, '_block_spec'):
            raise RuntimeError('block already configured')
        if tuple(c.id for c in self.run_configs) != spec.run_ids or len(spec.run_ids) != 4:
            raise ValueError('one complete fixed four-run block required')
        for name, value in spec.launcher.items():
            if getattr(self.cfg, name, object()) != value:
                raise ValueError('pool differs from prepared launcher')
        self._block_spec = spec
        self._block_service_alive = service_alive
        self._block_run_called = False
        self._block_stop_reason = ''

    def _recover(self):
        # No silent recovery/retry into a second allocation. Preserve prior
        # attempts for diagnosis; a future resume needs a separately bounded plan.
        tasks = self.manifest['tasks']
        if set(tasks) != set(self._block_spec.run_ids):
            raise ValueError('pool contains another block or missing slots')
        for task in tasks.values():
            if (task['status'] != 'pending' or task['attempt'] != 0
                    or task['attempts'] or task.get('step_id')):
                raise RuntimeError('block has prior execution; no automatic replay')
        return deque(self._block_spec.run_ids), set()

    def _block_gate(self):
        remaining = self._remaining_seconds()
        if (type(remaining) not in (int, float) or not math.isfinite(remaining)
                or not 0 < remaining <= ALLOCATION_SECONDS):
            return 'invalid_or_exhausted_allocation_deadline'
        tasks = self.manifest['tasks']
        if not any(t['attempt'] for t in tasks.values()):
            if ALLOCATION_SECONDS - remaining > STARTUP_SECONDS:
                return 'startup_allowance_exhausted'
        if self._block_service_alive() is not True:
            return 'critic_service_unavailable'
        # Equal worker cap, plus reserved shutdown/poll time. This is stricter
        # than the old pool's 3930-second launch gate, without changing configs.
        if remaining < STEP_WITH_TERMINATION_SECONDS + POLL_SECONDS + CLEANUP_SECONDS:
            return 'insufficient_time_for_full_step_and_cleanup'
        return ''

    def _can_launch(self):
        reason = self._block_gate()
        if reason:
            self._block_stop_reason = reason
            # Lack of time for the NEXT step must not cancel an active step.
            # The base loop will stop pending work once active work finishes.
            if reason != 'insufficient_time_for_full_step_and_cleanup':
                self._stop_requested = True
            return False
        return super()._can_launch()

    def _poll_external(self, external_running, pending):
        super()._poll_external(external_running, pending)
        # _can_launch is not called after the last pending run is dispatched.
        # Still detect service loss / reserve cleanup time during that run.
        remaining = self._remaining_seconds()
        if (type(remaining) not in (int, float) or not math.isfinite(remaining)
                or remaining <= CLEANUP_SECONDS):
            self._block_stop_reason = 'allocation_cleanup_deadline'
            self._stop_requested = True
        elif self._block_service_alive() is not True:
            self._block_stop_reason = 'critic_service_unavailable'
            self._stop_requested = True

    def _launch(self, run_id):
        # Path validation can consume time AFTER the pool checked _can_launch.
        # Recheck immediately at the resource-bearing dispatch boundary.
        reason = self._block_gate()
        if reason:
            self._block_stop_reason = reason
            raise RuntimeError('block dispatch stopped: ' + reason)
        if run_id not in self._block_spec.run_ids or self.manifest['tasks'][run_id]['attempt']:
            raise RuntimeError('unplanned run or repeated dispatch')
        return super()._launch(run_id)

    def run(self):
        if not hasattr(self, '_block_spec') or self._block_run_called:
            raise RuntimeError('configure exactly one block; do not rerun a controller')
        self._block_run_called = True
        try:
            return super().run()
        finally:
            if self._block_stop_reason:
                self._stop_reason = self._block_stop_reason
                for task in self.manifest['tasks'].values():
                    if task['status'] == 'pending':
                        task['reason'] = self._block_stop_reason
                self._save_manifest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, required=True)
    parser.add_argument('--block', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    spec, configs = inspect_draft(args.draft, args.block)
    print(json.dumps(dict(status='CONTROLLER_INPUTS_BOUND_NOT_LAUNCHABLE', block=spec.block,
        run_ids=spec.run_ids, actual_configs_bound=len(configs), source_tree=TREE,
        allocation_minutes=280, dispatches=0, model_loads=0, api_requests=0,
        readiness=False, live_adapter_implemented=False)))


if __name__ == '__main__':
    main()
