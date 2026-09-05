"""Four-fit development preparation via the existing token-budget planner.

No readers, model loading, label access, source admission, or job submission.
The caller must supply an already-qualified TRAIN projection. Metadata checks
below cannot certify production provenance, experiment isolation or GPU budget.
"""
from dataclasses import dataclass

from phase1.global_local_execution_plan import BatchShape, PlanError
from phase1.global_local_training_inputs import PreparedTrainingInputs
from phase1.global_local_token_budget_plan import Plan


MATRIX = (
    ('Lbudget', 'Lbudget', 6),
    ('G-reuse-to-L-full', 'G_to_L', 6),
    ('G-reuse-to-L-full', 'G_to_L', 7),
    ('Lbudget', 'Lbudget', 7),
)
SHAPE = BatchShape(2, 8, 8)


@dataclass(frozen=True)
class ScreenFit:
    sequence: int
    reported_arm: str
    plan: Plan


def prepare_screen(prepared: PreparedTrainingInputs) -> tuple[ScreenFit, ...]:
    """Plan, do not train. Refuse extra execution endpoints in global input."""
    if type(prepared) is not PreparedTrainingInputs:
        raise PlanError('screen_requires_prepared_train_projection')
    if prepared.encoder.max_len != 16384:
        raise PlanError('screen_context_mismatch')
    global_rows, local_rows = prepared.pools
    local_support = {(r.context_sha256, e.card_id) for r in local_rows for e in (r.a, r.b)}
    global_support = {(r.context_sha256, e.card_id) for r in global_rows for e in (r.a, r.b)}
    if not global_support <= local_support:
        raise PlanError('screen_global_not_execution_endpoint_reuse')
    plans = tuple(ScreenFit(i, label, prepared.plan(consumer, seed, SHAPE))
                  for i, (label, consumer, seed) in enumerate(MATRIX, 1))
    if len({p.plan.reference_valid_tokens for p in plans}) != 1:
        raise PlanError('screen_reference_cap_mismatch')
    # This is a shared cap, NOT identical step counts or GPU/FLOP equality.
    for fit in plans:
        if fit.plan.planned_valid_tokens > fit.plan.reference_valid_tokens:
            raise PlanError('screen_cap_exceeded')
        if fit.plan.arm == 'G_to_L' and fit.plan.planned_valid_tokens != fit.plan.reference_valid_tokens:
            raise PlanError('screen_full_pass_incomplete')
    return plans


def preparation_summary(fits: tuple[ScreenFit, ...]) -> dict:
    """Keep pair/card/task identities out of a shareable planning summary."""
    if tuple((x.reported_arm, x.plan.arm, x.plan.seed) for x in fits) != MATRIX:
        raise PlanError('screen_matrix_mismatch')
    if tuple(x.sequence for x in fits) != (1, 2, 3, 4):
        raise PlanError('screen_sequence_mismatch')
    return {
        'classification': 'DEVELOPMENT_PLAN_ONLY_NOT_SOURCE_OR_GPU_ADMISSION',
        'fits': [{
            'sequence': x.sequence, 'arm': x.reported_arm, 'consumer_arm': x.plan.arm,
            'seed': x.plan.seed, 'plan_sha256': x.plan.sha256,
            'protocol_sha256': x.plan.protocol_sha256,
            'reference_valid_token_cap': x.plan.reference_valid_tokens,
            'valid_tokens': x.plan.planned_valid_tokens,
            'shortfall_tokens': x.plan.reference_valid_tokens-x.plan.planned_valid_tokens,
            'next_whole_pair_tokens': x.plan.budget_stop_next_pair_tokens,
            'pair_visits': x.plan.planned_pair_visits, 'optimizer_updates': x.plan.steps,
            'padded_token_slots': sum(b.padded_slots for b in x.plan.batches),
        } for x in fits],
        'gpu_jobs_started': 0, 'model_fits_started': 0,
        'source_qualification_verified_here': False,
        'ready_to_submit': False,
    }
