"""Local-only future experiment overlay; never modifies the shared source.

Remove development output/individual-request caps; the common episode deadline
remains the sole time limit. Original token default is delegated to vLLM.
"""
import ast,hashlib,inspect,textwrap

SOURCE_SHA='5640c0462fa04123691fc770ac5ddfd0edf50bfc6d54d9c94371b2e54317bef2'
LIMIT=2100

def transform(source):
    before='deadline_limit = 1200 if local_generator else 300'
    after='deadline_limit = 2100 if local_generator else 300'
    anchor='kwargs = request_kwargs.copy()'
    if source.count(before)!=1 or source.count(anchor)!=1:raise ValueError('exact bounded method source required')
    line,=[line for line in source.splitlines() if line.strip()==anchor]
    indent=line[:len(line)-len(line.lstrip())]
    replacement=anchor+f"\n{indent}if local_generator:\n{indent}    kwargs.pop('max_tokens')"
    changed=source.replace(before,after).replace(anchor,replacement)
    ast.parse(changed)
    return changed

def install(backend):
    if getattr(backend,'_full_deadline_installed',False):return
    with open(backend.__file__,'rb') as handle:raw=handle.read()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('backend source drift')
    classes=[value for value in vars(backend).values() if inspect.isclass(value) and value.__module__==backend.__name__ and '_query_once_bounded' in vars(value)]
    cls,=classes
    source=textwrap.dedent(inspect.getsource(cls._query_once_bounded))
    modified=transform(source)
    namespace={};exec(compile(modified,'<frozen-full-deadline-overlay>','exec'),vars(backend),namespace)
    cls._query_once_bounded=namespace['_query_once_bounded']
    backend._full_deadline_installed=True
