"""Style normalization for the mechanism probe: rename all variables/functions to canonical
names (v0,v1,... f0,f1,...) and strip comments/docstrings. Preserves imports and attribute
names (API calls). Falls back to the original code if the file does not parse.
Usage: python phase1/normalize_code.py in_cards.jsonl out_cards.jsonl"""
import ast, json, sys

class Norm(ast.NodeTransformer):
    def __init__(self):
        self.names = {}; self.fn = 0; self.vn = 0
        self.keep = set(dir(__builtins__)) if not isinstance(__builtins__, dict) else set(__builtins__)
    def _map(self, name, is_fn=False):
        if name in self.keep or name.startswith("__"): return name
        if name not in self.names:
            if is_fn: self.names[name] = f"f{self.fn}"; self.fn += 1
            else: self.names[name] = f"v{self.vn}"; self.vn += 1
        return self.names[name]
    def visit_FunctionDef(self, node):
        node.name = self._map(node.name, True); self.generic_visit(node); return node
    def visit_Name(self, node):
        node.id = self._map(node.id); return node
    def visit_arg(self, node):
        node.arg = self._map(node.arg); return node
    def visit_Import(self, node): return node          # keep module names
    def visit_ImportFrom(self, node): return node
    def visit_alias(self, node):
        if node.asname: node.asname = self._map(node.asname)
        return node

def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return tree

ok = fail = 0
with open(sys.argv[2], "w") as out:
    for l in open(sys.argv[1]):
        d = json.loads(l)
        try:
            t = ast.parse(d["code"])
            t = strip_docstrings(t)
            t = Norm().visit(t)
            ast.fix_missing_locations(t)
            d["code"] = ast.unparse(t)
            ok += 1
        except Exception:
            fail += 1                      # keep original
        out.write(json.dumps(d) + "\n")
print(f"[normalize] ok={ok} kept-original={fail}")
