"""Strict deterministic source edits: no fuzzy matching or hidden repair."""
import ast,difflib,hashlib,json,re
def apply_response(raw,parent,arm,extract_code):
    if arm=='F':
        code=extract_code(raw);count=None
    elif arm=='P':
        blocks=list(re.finditer(r'^```json[ \t]*\r?\n(.*?)^```[ \t]*$',raw,re.M|re.S))
        if len(blocks)!=1:raise ValueError('exactly one JSON block required')
        edits=json.loads(blocks[0].group(1))
        if not isinstance(edits,list) or len(edits)>8:raise ValueError('edit list size')
        code=parent
        for e in edits:
            if not isinstance(e,dict) or set(e)!={'search','replace'} or not all(isinstance(e[k],str) for k in e):raise ValueError('edit schema')
            if not e['search'] or code.count(e['search'])!=1:raise ValueError('nonunique or missing search')
            code=code.replace(e['search'],e['replace'],1)
        count=len(edits)
    else:raise ValueError('unknown arm')
    ast.parse(code)
    a=parent.splitlines();b=code.splitlines()
    changed=sum(max(i2-i1,j2-j1) for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if tag!='equal')
    return code,dict(edit_count=count,changed_lines=changed,parent_lines=len(a),result_lines=len(b),parent_sha256=hashlib.sha256(parent.encode()).hexdigest(),result_sha256=hashlib.sha256(code.encode()).hexdigest())
