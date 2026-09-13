"""Pure configuration intervention for a future strong-preservation control.

No changes to active source, parser, retry count, search, data, or scoring.
"""
import copy
from forets_edit_scope_20260914 import HEADER as MODULE_HEADER,INSTRUCTION as MODULE_INSTRUCTION,apply_config

ARMS=('whole_program','preserve_program','model_module')
SEEDS=(46,47)
TASKS=('leaf-classification','spaceship-titanic')
HEADER='EScope preservation instruction (full-program output is still required):'
INSTRUCTION='''Return a short plan and one Python code block containing the complete executable program.
Preserve the prior program's data loading, train/validation split, validation metric,
label ordering, full-training refit, and submission schema. Concentrate the proposed
improvement or repair in build_model(X), including any necessary local imports,
feature engineering, preprocessing, models, or ensemble helpers inside that function.
Do not rewrite unrelated working code or substitute a different validation procedure.
The model pipeline must fit in the stated execution limit. Do not access external
evaluation files. Return real executable code, not a placeholder or pseudocode.
This is an instruction, not an automatic repair: your entire returned program will
be executed as written and no missing or incorrect outer code will be supplied.'''


def order():
    rows=[]
    for block,seed in enumerate(SEEDS,1):
        for j,task in enumerate(TASKS):
            offset=(seed+j)%3
            rows.extend((block,task,seed,arm) for arm in ARMS[offset:]+ARMS[:offset])
    return rows


def transform(cfg,arm):
    if arm not in ARMS:raise ValueError('frozen preservation arm')
    cfg=copy.deepcopy(cfg)
    for op in ('draft','improve','debug'):
        text=cfg['solver']['operators'][op]['system_message_prompt_template']['template']
        if MODULE_HEADER in text or HEADER in text:raise ValueError('already has scope intervention')
    cfg=apply_config(cfg,'model_module' if arm=='model_module' else 'whole_program')
    if arm=='preserve_program':
        for op in ('draft','improve','debug'):
            cfg['solver']['operators'][op]['system_message_prompt_template']['template']+='\n\n'+HEADER+'\n'+INSTRUCTION
    return cfg


def strip_intervention(cfg,arm):
    cfg=copy.deepcopy(cfg);expected='model_module' if arm=='model_module' else 'whole_program'
    if cfg['solver'].pop('edit_scope')!=expected:raise ValueError('output interface drift')
    for op in ('draft','improve','debug'):
        field=cfg['solver']['operators'][op]['system_message_prompt_template']
        suffix=None
        if arm=='model_module':suffix='\n\n'+MODULE_HEADER+'\n'+MODULE_INSTRUCTION
        elif arm=='preserve_program':suffix='\n\n'+HEADER+'\n'+INSTRUCTION
        if suffix:
            if not field['template'].endswith(suffix):raise ValueError('instruction drift')
            field['template']=field['template'][:-len(suffix)]
    return cfg
