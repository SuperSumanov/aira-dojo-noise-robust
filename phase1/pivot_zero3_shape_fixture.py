"""Deterministic maximum-length workload, not a production corpus or effect test.

No reader, tokenizer, model import, job submission or data admission. Integer
tokens are synthetic and never presented as correctly serialized real programs.
All G endpoints are reused from L; labels come from synthetic ordinal identities.
"""
import hashlib
from phase1.global_local_execution_plan import BatchShape,EncoderBinding,Endpoint,Pair,PlanError
from phase1.global_local_batch_adapter import encoding_digest
from phase1.global_local_token_budget_plan import build_plan

LENGTH=16384
SHAPE=BatchShape(2,8,8)
COUNT=128
CONTEXT=hashlib.sha256(b'synthetic:pivot-shape-not-real-data').hexdigest()
PROTOCOL=hashlib.sha256(b'synthetic:pivot-two-update-shape-v1-not-development').hexdigest()


def encoded(context,identity):
    if context!=CONTEXT or not identity.startswith('synthetic:pivot:'):
        raise PlanError('pivot_synthetic_identity')
    suffix=identity.removeprefix('synthetic:pivot:')
    if len(suffix)!=3 or not suffix.isdigit() or not 0<=int(suffix)<2*COUNT:
        raise PlanError('pivot_synthetic_identity')
    index=int(suffix)
    return tuple(1+(index*37+position*13)%1000 for position in range(LENGTH))


def fixture():
    ends=tuple(Endpoint(f'synthetic:pivot:{i:03d}',LENGTH,
        encoding_digest(encoded(CONTEXT,f'synthetic:pivot:{i:03d}'))) for i in range(2*COUNT))
    local=tuple(Pair.canonical('L',ends[2*i],ends[2*i+1],CONTEXT) for i in range(COUNT))
    global_rows=tuple(Pair.canonical('G',ends[2*i],ends[(2*i+3)%(2*COUNT)],CONTEXT) for i in range(COUNT))
    if {r.key for r in local}&{r.key for r in global_rows}:raise PlanError('pivot_synthetic_edge_overlap')
    plan=build_plan('G_to_L',global_rows,local,seed=6,shape=SHAPE,
        encoder=EncoderBinding(hashlib.sha256(b'synthetic-integer-encoder').hexdigest(),
            hashlib.sha256(b'synthetic-no-program-serialization').hexdigest(),LENGTH),protocol_sha256=PROTOCOL)
    truth={r.key:1 if r.a.card_id>r.b.card_id else -1 for r in (*global_rows,*local)}
    return plan,(global_rows,local),encoded,truth


def summary():
    plan,pools,_,_=fixture()
    return {'classification':'SYNTHETIC_MAX_LENGTH_SHAPE_PLAN_NOT_REAL_TOKENIZATION',
        'plan_sha256':plan.sha256,'protocol_sha256':PROTOCOL,'seed':plan.seed,
        'global_pairs':len(pools[0]),'local_pairs':len(pools[1]),'endpoints':2*COUNT,
        'sequence_length':LENGTH,'world':SHAPE.world_size,'pairs_per_rank':SHAPE.pairs_per_rank,
        'accumulation':SHAPE.accumulation,'steps':plan.steps,'valid_tokens':plan.planned_valid_tokens,
        'padded_slots':sum(b.padded_slots for b in plan.batches),'fit_or_source_admission':False}
