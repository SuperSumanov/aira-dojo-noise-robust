import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


def test_budget_uses_all_terminal_actuals():
    a=json.loads((BASE/'manifests/zero3_3090_consumed_approval_20260906.json').read_text())
    assert a['prior_actual_gpu_seconds']==2+5+146+266==419
    assert a['gpu_seconds_upper_bound']==2*(900+300+60)==2520
    assert a['aggregate_conservative_upper_bound']==419+2520==2939<=a['aggregate_cap_gpu_seconds']==3120
    assert a['automatic_retries']==0 and a['jobs_initial']==1


def test_launcher_changes_only_job_identity_and_reduced_time_cap():
    old=(BASE/'scripts/zero3_3090_socket_20260906.sbatch').read_text()
    new=(BASE/'scripts/zero3_3090_consumed_20260906.sbatch').read_text()
    assert new==old.replace('critic_zero3_socket','critic_zero3_consumed').replace('00:18:00','00:15:00').replace('900s','720s')


def test_scientific_fixture_and_communication_unchanged():
    old=json.loads((BASE/'manifests/zero3_3090_socket_approval_20260906.json').read_text())
    new=json.loads((BASE/'manifests/zero3_3090_consumed_approval_20260906.json').read_text())
    for k in ('seed','parameters','trajectories','gpu_count','gpu_model','node','existing_12535',
              'real_corpus_or_external_model_reads','private_cuda128_manifest_sha256','communication_profile'):
        assert old[k]==new[k]
