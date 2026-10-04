"""Frozen reuse of paired query sensitivity; never changes the C expansion gate."""
import argparse
import hashlib
import json
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
P = B/'opportunity-information-20261003-v2'
R = B/'diagnostic-information-20261004-v1'
OLD = '6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'analyze'])
    args = parser.parse_args()
    assert sha(R/'plan.json') == PLAN
    source = P/'opportunity_information_sensitivity_20261003.py'
    receipt = json.loads((P/'sensitivity-freeze.json').read_bytes())
    assert receipt['plan_sha256'] == OLD and sha(source) == receipt['script_sha256']
    original = source.read_text()
    assert original.count(str(P)) == 1 and original.count(OLD) == 1
    modified = original.replace(str(P), str(R)).replace(OLD, PLAN).replace('104050', '107050')
    namespace = dict(__file__=str(Path(__file__).resolve()), __name__='frozen_sensitivity')
    exec(compile(modified, 'source_bound_paired_sensitivity', 'exec'), namespace)
    namespace[args.mode]()


if __name__ == '__main__':
    main()
