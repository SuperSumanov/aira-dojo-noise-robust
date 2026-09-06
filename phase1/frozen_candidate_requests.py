"""Pre-render all generation requests before any candidate is generated.

Opt-in preparation only: no task execution, scheduler, default client, dataset
admission or automatic retry. Render/operator callbacks must themselves be
trusted and non-networked; this is not an OS sandbox. Real rollout accounting,
deadlines, model selection and confirmation remain separate qualifications.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import random
import threading


class FrozenRequestError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise FrozenRequestError(reason)


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise FrozenRequestError('request_must_be_finite_json') from exc


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def wire(messages, generation_kwargs):
    require(type(messages) is list and bool(messages), 'empty_or_invalid_messages')
    for message in messages:
        require(type(message) is dict and set(message) == {'role', 'content'}
                and message['role'] in ('system', 'user', 'assistant')
                and type(message['content']) is str, 'text_content_message_contract')
    require(type(generation_kwargs) is dict and all(type(k) is str for k in generation_kwargs), 'generation_kwargs_contract')
    require(not any(k.lower() in {'api_key','authorization','headers','extra_headers','base_url','api_base',
                'messages','json_schema','function_name','function_description'} for k in generation_kwargs),
            'routing_credentials_or_reserved_kwargs_forbidden')
    require(set(generation_kwargs) <= {'temperature','top_p','max_tokens','max_completion_tokens','seed','stop',
                                      'presence_penalty','frequency_penalty','n'}, 'generation_option_requires_review')
    require('n' not in generation_kwargs or type(generation_kwargs['n']) is int and generation_kwargs['n'] == 1,
            'one_generation_per_slot')
    for key in ('max_tokens','max_completion_tokens'):
        require(key not in generation_kwargs or type(generation_kwargs[key]) is int and generation_kwargs[key] > 0,
                'positive_output_budget')
    require(not {'max_tokens','max_completion_tokens'} <= set(generation_kwargs), 'one_output_limit_owner')
    # This opt-in wire contract is intentionally narrower than any provider SDK.
    # A new provider-specific option/range needs explicit integration review.
    for key, low, high in (('temperature',0,2),('top_p',0,1),
                          ('presence_penalty',-2,2),('frequency_penalty',-2,2)):
        if key in generation_kwargs:
            value = generation_kwargs[key]
            require(type(value) in (int,float) and low <= value <= high and math.isfinite(value)
                    and (key != 'top_p' or value > 0), 'decoding_range_contract')
    require('seed' not in generation_kwargs or type(generation_kwargs['seed']) is int
            and 0 <= generation_kwargs['seed'] < 2**32, 'decoding_seed_contract')
    if 'stop' in generation_kwargs:
        stops = generation_kwargs['stop']
        require(type(stops) is str and bool(stops) or type(stops) is list and 1 <= len(stops) <= 4
                and all(type(s) is str and s for s in stops), 'text_stop_contract')
    return canonical({'messages': messages, 'generation_kwargs': generation_kwargs})


@dataclass(frozen=True)
class FrozenRequest:
    slot: int
    preparation_seed: int
    wire_json: str

    @property
    def sha256(self):
        return digest(canonical({'slot': self.slot, 'preparation_seed': self.preparation_seed, 'wire_json': self.wire_json}))


@dataclass(frozen=True)
class FrozenBatch:
    state_sha256: str
    operator_sha256: str
    generator_contract_sha256: str
    requests: tuple[FrozenRequest, ...]

    @property
    def sha256(self):
        return digest(canonical(self.receipt()))

    def receipt(self):
        # Prompt/code and generation responses deliberately stay out of receipts.
        return {'protocol': 'pre-rendered-candidate-requests-v1', 'state_sha256': self.state_sha256,
                'operator_sha256': self.operator_sha256, 'generator_contract_sha256': self.generator_contract_sha256,
                'requests': [{'slot': r.slot, 'preparation_seed': r.preparation_seed, 'request_sha256': r.sha256}
                             for r in self.requests],
                'production_or_effect_qualification': False}


def capture_improve_batch(*, operator, operator_kwargs, render_system, generation_kwargs,
                          slot_seeds, state_sha256, operator_sha256, generator_contract_sha256):
    """Bridge the existing improve_op using a non-network capture LLM.

Call this BEFORE starting client/background threads. Each slot gets a separate
deep copy of the same (cfg,journal,parent) graph; package shuffles cannot mutate
the live config or later slots. Python preparation RNG is isolated and restored.
Provider decoding determinism is NOT implied by a preparation seed.
"""
    require(threading.current_thread() is threading.main_thread() and threading.active_count() == 1,
            'prepare_before_client_threads')
    require(type(operator_kwargs) is dict and 'improve_llm' not in operator_kwargs, 'capture_supplies_llm')
    require(type(slot_seeds) in (tuple, list) and 2 <= len(slot_seeds) <= 64
            and all(type(s) is int and 0 <= s < 2**32 for s in slot_seeds)
            and len(set(slot_seeds)) == len(slot_seeds), 'fixed_unique_preparation_seeds')
    for value in (state_sha256, operator_sha256, generator_contract_sha256):
        require(type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef'), 'fixed_external_bindings')
    require(type(generation_kwargs) is dict, 'plain_resolved_generation_kwargs_required')
    baseline = deepcopy(operator_kwargs)
    kwargs_snapshot = json.loads(canonical(generation_kwargs))
    requests = []
    initial_rng = random.getstate()
    try:
        for slot, seed in enumerate(slot_seeds):
            captured = []
            def capture(*, query_data, no_user_message):
                require(no_user_message is True and not captured, 'exactly_one_system_request_per_slot')
                messages = [{'role': 'system', 'content': render_system(**deepcopy(query_data))}]
                text = wire(messages, deepcopy(kwargs_snapshot))
                captured.append(text)
                return text
            random.seed(seed)
            result = operator(improve_llm=capture, **deepcopy(baseline))
            require(len(captured) == 1 and result == captured[0], 'operator_capture_contract')
            requests.append(FrozenRequest(slot, seed, captured[0]))
    finally:
        random.setstate(initial_rng)
    return FrozenBatch(state_sha256, operator_sha256, generator_contract_sha256, tuple(requests))


class GenerationOnlyBatch:
    """Single-use batch dispatch; selected execution is deliberately absent.

The event sink MUST durably persist before returning. Network failures are
ambiguous and poison this object: never replay its unknown request automatically.
Caller owns client-internal retry bounds and accounting; this wrapper is not
an exactly-once remote service or a budget/deadline enforcement layer.
"""
    def __init__(self, batch, *, durable_event):
        require(type(batch) is FrozenBatch and type(batch.requests) is tuple and 2 <= len(batch.requests) <= 64,
                'frozen_batch_required')
        require(all(type(r) is FrozenRequest and type(r.slot) is int for r in batch.requests), 'typed_slots')
        require(tuple(r.slot for r in batch.requests) == tuple(range(len(batch.requests))), 'slot_order')
        require(callable(durable_event), 'durable_sink_required')
        for value in (batch.state_sha256, batch.operator_sha256, batch.generator_contract_sha256):
            require(type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef'), 'fixed_external_bindings')
        # Validate EVERY wire before any intent or call, not as a lazy loop that
        # might spend on slot0 before discovering slot1 was malformed.
        for r in batch.requests:
            require(type(r.wire_json) is str and type(r.preparation_seed) is int
                    and 0 <= r.preparation_seed < 2**32, 'typed_wire_and_seed')
            try:
                obj = json.loads(r.wire_json)
                require(type(obj) is dict and set(obj) == {'messages','generation_kwargs'}, 'wire_schema')
                require(wire(obj['messages'], obj['generation_kwargs']) == r.wire_json, 'wire_drift')
            except (ValueError, TypeError, KeyError) as exc:
                raise FrozenRequestError('invalid_frozen_wire') from exc
        require(len({r.preparation_seed for r in batch.requests}) == len(batch.requests), 'unique_preparation_seeds')
        self.batch = batch
        self.events = durable_event
        self.started = False
        self.completed = False
        self._attempt_lock = threading.Lock()

    def generate(self, *, query):
        with self._attempt_lock:
            require(not self.started, 'batch_already_attempted_no_automatic_retry')
            self.started = True
        self.events({'event': 'BATCH_LOCKED', 'batch_sha256': self.batch.sha256, 'receipt': self.batch.receipt()})
        outputs = []
        for r in self.batch.requests:
            request = json.loads(r.wire_json)
            require(wire(request['messages'], request['generation_kwargs']) == r.wire_json, 'wire_drift')
            self.events({'event': 'GENERATION_INTENT', 'slot': r.slot, 'request_sha256': r.sha256})
            # Mirrors GenericLLM's no_user_message=True client.query wire call.
            response, usage = query(deepcopy(request['messages']), json_schema=None, function_name=None,
                                    function_description=None, **deepcopy(request['generation_kwargs']))
            require(type(response) is str, 'text_response_required')
            outputs.append((response, deepcopy(usage)))
            self.events({'event': 'GENERATION_RETURNED', 'slot': r.slot, 'response_sha256': digest(response)})
        self.events({'event': 'BATCH_GENERATED', 'batch_sha256': self.batch.sha256, 'slots': len(outputs)})
        self.completed = True
        return tuple(outputs)
