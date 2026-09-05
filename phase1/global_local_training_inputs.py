"""Connect authorized in-memory train projections to the existing consumer.

No files, source admission, model loading, GPU launch or split creation. The
caller must supply an already-qualified train-only projection, not raw Cards
or a seven-role declaration masquerading as qualification. Nothing is filtered
into eligibility here. Topology/encoding/planning never receives true labels.
"""
from dataclasses import dataclass
from types import MappingProxyType
import re

from phase1.g_reuse_endpoint_inference import encode_endpoints
from phase1.global_local_batch_adapter import encoding_digest
from phase1.global_local_execution_plan import EncoderBinding,Endpoint,Pair,PlanError,digest_records
from phase1.global_local_token_budget_plan import Plan,build_plan
from phase1.verify_global_local_token_budget_plan import TokenPlanVerificationError,verify_plan


def require(ok,reason):
    if not ok:raise PlanError(reason)


@dataclass(frozen=True)
class PreparedTrainingInputs:
    pools: tuple
    encoder: EncoderBinding
    protocol_sha256: str
    projection_sha256: str
    _encoded: object

    def encoding_provider(self,context_sha256,card_id):
        try:return self._encoded[(context_sha256,card_id)]
        except KeyError:raise PlanError('encoding_outside_prepared_training_support') from None

    def plan(self,arm,seed,shape):
        return build_plan(arm,*self.pools,seed=seed,shape=shape,encoder=self.encoder,
                          protocol_sha256=self.protocol_sha256)

    def _required_label_rows(self,plan):
        require(type(plan) is Plan and plan.encoder==self.encoder
            and plan.protocol_sha256==self.protocol_sha256,'training_label_plan_binding')
        try:verify_plan(plan,*self.pools)
        except TokenPlanVerificationError:
            raise PlanError('training_label_plan_invalid') from None
        return {r.key:r for batch in plan.batches for r in batch.rows
                if not (plan.arm=='Ghash_to_L' and r.source=='G')}

    def required_label_keys(self,plan):
        """Caller can project exactly these train labels, before reading values."""
        return tuple(sorted(self._required_label_rows(plan)))

    def true_sign_provider(self,winner_by_pair,*,plan):
        """Bind only the planned arm's true TRAIN labels; Ghash never admits G."""
        rows=self._required_label_rows(plan)
        require(type(winner_by_pair) is dict and set(winner_by_pair)==set(rows),'training_label_support_mismatch')
        signs={}
        for key,row in rows.items():
            winner=winner_by_pair[key]
            require(type(winner) is str and winner in (row.a.card_id,row.b.card_id),'invalid_training_winner')
            signs[key]=1 if winner==row.a.card_id else -1
        frozen=MappingProxyType(signs)
        def lookup(key):
            try:return frozen[key]
            except KeyError:raise PlanError('label_outside_prepared_training_support') from None
        return lookup


def prepare_training_inputs(cards,global_edges,local_edges,tokenizer,*,encoder,protocol_sha256):
    require(type(encoder) is EncoderBinding and isinstance(protocol_sha256,str)
            and re.fullmatch('[0-9a-f]{64}',protocol_sha256),'training_encoder_protocol_binding')
    require(type(cards) is list and bool(cards),'training_projection_required')
    require(all(type(c) is dict and set(c)=={'endpoint_id','task_name','code'} for c in cards),'training_card_projection_schema')
    require(all(type(c['endpoint_id']) is str and bool(c['endpoint_id']) for c in cards),'training_card_identity')
    by_id={c['endpoint_id']:c for c in cards}
    require(len(by_id)==len(cards),'duplicate_training_card')
    pools=[];used=set();seen=set()
    for source,edges in (('G',global_edges),('L',local_edges)):
        require(type(edges) in (list,tuple) and bool(edges),'empty_training_edge_pool')
        normalized=[]
        for edge in edges:
            require(type(edge) in (list,tuple) and len(edge)==2 and all(type(x) is str for x in edge),'training_edge_schema')
            a,b=sorted(edge)
            require(a!=b and a in by_id and b in by_id,'training_edge_support')
            require(by_id[a]['task_name']==by_id[b]['task_name'],'cross_task_training_pair')
            require((a,b) not in seen,'duplicate_or_cross_source_training_pair')
            seen.add((a,b));used.update((a,b));normalized.append((a,b))
        pools.append((source,sorted(normalized)))
    require(used==set(by_id),'extra_unreferenced_training_cards')
    # Reuse the already source-parity-tested serializer, never .sha256 from a
    # different digest protocol. Batch descriptors use encoding_digest below.
    encoded=encode_endpoints(cards,tokenizer,max_len=encoder.max_len)
    endpoints={r.endpoint_id:Endpoint(r.endpoint_id,len(r.input_ids),encoding_digest(r.input_ids)) for r in encoded}
    contexts={name:digest_records([(encoder.serialization_sha256,c['task_name'])]) for name,c in by_id.items()}
    result=tuple(tuple(Pair.canonical(source,endpoints[a],endpoints[b],contexts[a]) for a,b in edges) for source,edges in pools)
    lookup=MappingProxyType({(contexts[r.endpoint_id],r.endpoint_id):r.input_ids for r in encoded})
    projection=digest_records([{'cards':sorted(cards,key=lambda c:c['endpoint_id']),
        'pairs':[(source,edges) for source,edges in pools]}])
    return PreparedTrainingInputs(result,encoder,protocol_sha256,projection,lookup)
