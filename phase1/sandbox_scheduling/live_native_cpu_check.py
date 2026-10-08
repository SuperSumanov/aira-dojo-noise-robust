"""Read-only frozen-source and native hook compatibility check; no model calls."""
import ast
import hashlib
import json
from pathlib import Path
import re

D=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
SECRET=re.compile(rb'(?i)(?<![a-z0-9_-])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def main():
    plan=json.loads((D/'plan.json').read_bytes())
    selections={
      'src/dojo/tasks/mlebench/task.py':('__init__','_step_search_only_dev','prepare'),
      'src/dojo/solvers/mcts/mcts.py':('update_data_preview',),
      'src/dojo/core/interpreters/jupyter/jupyter_code_executor.py':('execute_code',),
      'src/dojo/core/solvers/llm_helpers/generic_llm.py':('__call__',),
      'src/dojo/utils/experiment_deadline.py':('ExperimentDeadline',),
    }
    for rel,names in selections.items():
        raw=(D/'source'/rel).read_bytes()
        if SECRET.search(raw):raise ValueError('credential shape; refuse source output')
        if hashlib.sha256(raw).hexdigest()!=plan['files']['source/'+rel]:raise ValueError('source drift')
        code=raw.decode();tree=ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
                print(rel,ast.get_source_segment(code,node),sep='\n')

if __name__=='__main__':main()
