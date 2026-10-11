"""Change only diagnostic receipt allocation, not the validated shutdown logic."""
import ast

OLD='''    with Path('/workspace/kernel-shutdown-guard-installed.json').open('x') as f:
'''
NEW='''    # Fresh receipt for every gateway launch, including a reused workspace.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', prefix='kernel-shutdown-guard-installed-',
                                     suffix='.json', dir='/workspace', delete=False) as f:
'''

def overlay(source):
    assert source.count(OLD)==1
    updated=source.replace(OLD,NEW,1)
    a=ast.parse(source);b=ast.parse(updated)
    before={x.name:ast.dump(x,include_attributes=False) for x in a.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
    after={x.name:ast.dump(x,include_attributes=False) for x in b.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert before.keys()==after.keys() and {k for k in before if before[k]!=after[k]}=={'install'}
    compile(updated,'reusable-shutdown-receipt','exec')
    return updated
