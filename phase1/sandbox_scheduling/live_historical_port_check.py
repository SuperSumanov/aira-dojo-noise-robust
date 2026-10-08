"""Read pinned port interfaces in closed batches, without reading outcomes."""
import ast
import hashlib
import json
from pathlib import Path
from live_node_precheck import BASE,SECRET

def main():
    for name in ('scheduling-neural-qualified-overlap-20261008-evening-v1',
                 'scheduling-neural-full-confirmation-20261008-v1'):
        root=BASE/name
        p=json.loads((root/'plan.json').read_bytes())
        print('BATCH',name)
        for rel,pin in p['files'].items():
            if not rel.endswith('.py') or rel.startswith(('programs/','data-')):
                continue
            if rel.startswith('source/') and not rel.endswith(('jupyter_interpreter.py','singularity_jupyter_server.py','jupyter_server.py')):
                continue
            raw=(root/rel).read_bytes()
            if SECRET.search(raw) or hashlib.sha256(raw).hexdigest()!=pin:
                raise ValueError('source security/hash failed')
            text=raw.decode()
            matching=[v.strip() for v in text.splitlines() if 'gateway_port' in v]
            if matching:
                print(json.dumps(dict(file=rel,port_references=matching)))
            if rel.endswith('jupyter_interpreter.py'):
                for n in ast.walk(ast.parse(text)):
                    if isinstance(n,ast.FunctionDef) and n.name in ('_gateway_port','_slurm_gateway_port'):
                        print(ast.get_source_segment(text,n))
            elif rel.endswith(('singularity_jupyter_server.py','jupyter_server.py')):
                for n in ast.walk(ast.parse(text)):
                    if isinstance(n,ast.FunctionDef) and ('port' in ast.get_source_segment(text,n)):
                        print(rel,ast.get_source_segment(text,n),sep='\n')

if __name__=='__main__':main()
