"""Shared generator context from the unchanged, inspected task image.

An exploratory system repair, not a new selector. Applied at the configured
system-template boundary, BEFORE normal rendering, request hashes and billing.
No task labels, candidate-specific advice, new data access or scoring changes.
"""
import copy
import hashlib


CONTEXT = """

# Installed execution environment (verified, unchanged image)
numpy 1.26.4; pandas 2.1.4; scikit-learn 1.9.0; lightgbm 4.6.0;
catboost 1.2.10; xgboost 2.1.4; torch 2.5.1+cu124.
Each complete program has AT MOST 300 seconds, including preprocessing,
all cross-validation folds, final fitting and writing submission.csv. The
time budget and requested evaluation procedure are unchanged. Use the installed
environment; do not install or upgrade packages to work around an API error.

LightGBM 4.6.0 API facts:
- lightgbm.train accepts callbacks; it does NOT accept verbose_eval or
  early_stopping_rounds keywords. LGBMClassifier.fit likewise accepts callbacks,
  not verbose or early_stopping_rounds keywords.
- Use callbacks=[lightgbm.early_stopping(stopping_rounds=50, verbose=False),
  lightgbm.log_evaluation(period=0)] WITH an appropriate validation set if early
  stopping is needed. Omit the early-stopping callback for a final fit with no
  validation set, and use an explicitly bounded number of rounds instead.
- Native LightGBM verbosity is an integer (e.g. verbosity=-1), not a boolean.
scikit-learn OneHotEncoder uses sparse_output, not the old sparse keyword.
""".strip()
CONTEXT_SHA = hashlib.sha256(CONTEXT.encode()).hexdigest()
GENERATION_OPERATORS = ('draft', 'improve', 'debug')


def apply_context(config):
    """Only three generation/repair system templates change; analysis is fixed."""
    result = copy.deepcopy(config)
    if config['solver']['execution_timeout'] != 300:
        raise ValueError('context timeout does not match actual execution limit')
    for name in GENERATION_OPERATORS:
        template = result['solver']['operators'][name]['system_message_prompt_template']
        if CONTEXT in template['template']:
            raise ValueError('environment context already applied')
        template['template'] += '\n\n' + CONTEXT
    return result
