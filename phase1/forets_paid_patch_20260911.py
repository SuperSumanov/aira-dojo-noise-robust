"""Deterministic additive patch to exact 3aae90ae source; old transport unchanged."""
from pathlib import Path


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('source anchor drift')
    return text.replace(old, new, 1)


def patch(text):
    text = once(text, "        kwargs = request_kwargs.copy()\n", "        kwargs = request_kwargs.copy()\n        paid = kwargs.pop('bounded_paid_budget_required', False)\n")
    old = '            completion = await asyncio.wait_for(completion_fn(messages=messages, **kwargs), timeout_seconds)'
    new = '''            if paid:
                from dojo.core.solvers.llm_helpers.backends.paid_transport import complete
                completion = await complete(messages, kwargs, timeout_seconds, event['attempt_id'])
            else:
                completion = await asyncio.wait_for(completion_fn(messages=messages, **kwargs), timeout_seconds)'''
    text = once(text, old, new)
    text = once(text, "            usage = completion.to_dict().get('usage') or {}", "            usage = completion.to_dict().get('usage') or {}\n            if paid:\n                event.update(cost=usage['cost'], cost_status='provider_account_charge')")
    text = once(text, "        # Prepare function specifications if provided", "        if model_kwargs.get('bounded_paid_budget_required') and not bounded:\n            raise ValueError('paid budget requires bounded transport')\n\n        # Prepare function specifications if provided")
    return text


def install(source, modules):
    backend = Path(source)/'src/dojo/core/solvers/llm_helpers/backends'
    target = backend/'lite_llm.py'
    target.write_text(patch(target.read_text()), encoding='utf-8', newline='\n')
    for source_name, name in [('forets_paid_budget_20260911.py','paid_budget.py'),
                              ('forets_paid_transport_20260911.py','paid_transport.py')]:
        with (backend/name).open('xb') as f:
            f.write((Path(modules)/source_name).read_bytes())
