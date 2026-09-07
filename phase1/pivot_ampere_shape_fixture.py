"""Same synthetic endpoints, smaller per-GPU batch; no production admission."""
import hashlib
from phase1.pivot_zero3_shape_fixture import fixture as original_fixture,COUNT,LENGTH
from phase1.global_local_execution_plan import BatchShape
from phase1.global_local_token_budget_plan import build_plan

SHAPE=BatchShape(2,1,64)
PROTOCOL=hashlib.sha256(b'synthetic:pivot-ampere-two-update-shape-v1-not-development').hexdigest()

def fixture():
    original,pools,encode,truth=original_fixture()
    plan=build_plan('G_to_L',*pools,seed=6,shape=SHAPE,encoder=original.encoder,protocol_sha256=PROTOCOL)
    assert plan.steps==2 and plan.planned_valid_tokens==8388608
    return plan,pools,encode,truth

def summary():
    plan,pools,_,_=fixture()
    return {'classification':'SYNTHETIC_AMPERE_MAX_LENGTH_SHAPE_PLAN_NOT_REAL_TOKENIZATION',
        'plan_sha256':plan.sha256,'protocol_sha256':PROTOCOL,'seed':plan.seed,
        'global_pairs':len(pools[0]),'local_pairs':len(pools[1]),'endpoints':2*COUNT,
        'sequence_length':LENGTH,'world':SHAPE.world_size,'pairs_per_rank':SHAPE.pairs_per_rank,
        'accumulation':SHAPE.accumulation,'steps':plan.steps,'valid_tokens':plan.planned_valid_tokens,
        'padded_slots':sum(b.padded_slots for b in plan.batches),'fit_or_source_admission':False}

def guard(plan):
    expected,*_=fixture()
    if plan.sha256!=expected.sha256 or plan!=expected:
        raise ValueError('only_fixed_synthetic_ampere_plan_allowed')
