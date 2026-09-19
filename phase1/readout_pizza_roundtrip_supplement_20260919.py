"""Separate supplemental readout: preserve the failed original claim and grades."""
import argparse
import readout_comparison_pizza_online_20260919 as pizza

def configure():
    pizza.configure();shared=pizza.shared
    old=shared.safe(shared.ROOT/'readout-claim.json')
    if old['reader_commit']!='e7d969f1102a589cc2d887df9eb02cf48dad9047':raise ValueError('original reader identity')
    if (shared.ROOT/'summary.json').exists():raise ValueError('unexpected original summary')
    shared.OUTPUT_ROOT=shared.ROOT/'readout-roundtrip-v1'
    shared.READOUT_CONTEXT=dict(original_failed_claim_sha256=shared.rt.sha(shared.ROOT/'readout-claim.json'),
        reason='Independent verifier previously used default pandas float parsing; MLE-bench uses round_trip. No submission, policy, official metric, or experimental data changed.',
        original_failed_reader_preserved=True,official_grade_not_redefined=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True);args=parser.parse_args()
    configure();pizza.shared.main(args.reader_commit)
