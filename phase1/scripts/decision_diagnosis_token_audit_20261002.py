"""Read-only baseline length check under the deployed tokenizer; no inference."""
import ast,json
from pathlib import Path
from tokenizers import Tokenizer
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
M=Path('/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy/model')
def main():
    tok=Tokenizer.from_file(str(M/'tokenizer.json')); p=json.loads((R/'plan.json').read_bytes()); out=[]
    for i,s in enumerate(p['starts']):
        code=json.loads((R/'starts'/f'{i}.private.json').read_bytes())['code']
        out.append(dict(task=s['task'],raw_code_tokens=len(tok.encode(code).ids),
            ast_unparse_tokens=len(tok.encode(ast.unparse(ast.parse(code))).ids),
            generation_token_cap=p['max_tokens_per_call']))
    result=dict(starts=out,scope='Baseline tokenization only; no model calls, no outcome inspection, no configuration change')
    with (R/'token-audit.json').open('x') as f: json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result))
if __name__=='__main__':main()
