"""Minimal future-source patch for the explicitly approved node-local generator.

Closed API studies are never modified. The long local deadline cannot widen a
paid provider deadline, turn retries on, or send global credentials locally.
"""
from forets_selfhosted_guard_20260912 import patch_backend

def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('exact local adapter anchor changed')
    return source.replace(old, new, 1)

def patch(source):
    source = patch_backend(source)
    source = once(source,
        "        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300:\n"
        "            raise ValueError('bounded request timeout must be in (0, 300] seconds')",
        "        local_generator = self.provider == 'selfhosted' and self.model == 'openai/qwen3.8-27b'\n"
        "        if local_generator:\n"
        "            from .selfhosted_guard import selfhosted_key\n"
        "            if self.api_key != selfhosted_key('qwen3.8-27b', self.base_url, os.environ):\n"
        "                raise ValueError('local auth changed after construction')\n"
        "        deadline_limit = 1200 if local_generator else 300\n"
        "        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= deadline_limit:\n"
        "            raise ValueError('request exceeds fixed provider deadline')")
    source = once(source,
        "        paid = kwargs.pop('bounded_paid_budget_required', False)",
        "        paid = kwargs.pop('bounded_paid_budget_required', False)\n"
        "        if local_generator and paid:\n"
        "            raise ValueError('local route cannot enter paid transport')")
    source = once(source,
        "        stats = dict(event)\n        p, c = stats['prompt_tokens'], stats['completion_tokens']",
        "        stats = dict(event)\n"
        "        if local_generator:\n"
        "            stats.update(finish_reason=getattr(completion.choices[0], 'finish_reason', None),\n"
        "                         cost=0.0, cost_status='local_api_no_charge_excludes_gpu',\n"
        "                         gpu_cost_accounted_separately=True)\n"
        "        p, c = stats['prompt_tokens'], stats['completion_tokens']")
    source = once(source,
        "        bounded_attempts = model_kwargs.pop('bounded_max_attempts', 1)",
        "        bounded_attempts = model_kwargs.pop('bounded_max_attempts', 1)\n"
        "        if self.provider == 'selfhosted' and (bounded is not True or bounded_attempts != 1):\n"
        "            raise ValueError('local development requires bounded single-attempt transport')")
    return source
