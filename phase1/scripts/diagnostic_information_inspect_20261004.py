"""Closed-all, source-bound semantic inspection; no label/prediction export."""
import hashlib
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
P = B/'opportunity-information-20261003-v2'
R = B/'diagnostic-information-20261004-v1'
OLD = '6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'


def main():
    # The published source is separately hash-bound by the preparation caller.
    import json
    frozen = json.loads((R/'inspection-freeze.json').read_bytes())
    source = R/'analysis_templates/inspect-template.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == frozen['template_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == frozen['script_sha256']
    assert frozen['plan_sha256'] == PLAN
    code = source.read_text()
    assert code.count(str(P)) == 1 and code.count(OLD) == 1
    code = code.replace(str(P), str(R)).replace(OLD, PLAN)
    namespace = dict(__name__='closed_inspection', __file__=str(Path(__file__).resolve()))
    exec(compile(code, 'frozen_closed_inspection', 'exec'), namespace)
    namespace['main']()


if __name__ == '__main__':
    main()
