"""Run the frozen native transport test for all four model/effort conditions."""
import hashlib
import json
from pathlib import Path
import sys

root, arm = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root))
src = (root/'long_effort_native_cpu_20261013.py').read_text()


def change(a, b):
    global src
    assert src.count(a) == 1, a[:60]
    src = src.replace(a, b)


change('import long_effort_trial_20261013 as trial', 'import weight_effort_trial_20261014 as trial')
change('import long_effort_policy_20261013 as policy', 'import weight_effort_policy_20261014 as policy')
change("os.environ.update(PYTHON_DOTENV_DISABLED='1', PRIMARY_KEY_QWEN3_8_27B='cpu-fixture-not-a-credential')",
       "os.environ.update(PYTHON_DOTENV_DISABLED='1', PRIMARY_KEY='cpu-fixture-not-a-credential', PRIMARY_KEY_QWEN3_8_27B='cpu-fixture-not-a-credential')")
change('policy.traced_call(', 'policy.trace(')
change("row = next(r for r in p['schedule'] if r['arm'] == arm)",
       "row = next(r for r in p['schedule'] if r['arm'] == arm)\nimport random\nrandom.seed(row['seed'])")
change('lambda p, e: events.append(e)', "lambda p, e: events.append(e) if 'success' in e else None")
change('async def transport(**kwargs):', """async def transport(**kwargs):
    assert kwargs['model'] == 'openai/'+policy.model(arm), 'actual transport model mismatch'
    if len(seen) == 4:
        prompt_hash = hashlib.sha256(json.dumps(kwargs['messages'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        (root/('cpu-prompt-'+arm+'.json')).write_text(json.dumps(dict(prompt_sha256=prompt_hash, model_id=kwargs['model'], seed=kwargs['seed'])))""")
exec(compile(src, str(root/'weight_effort_native_cpu_20261014.py'), 'exec'))
