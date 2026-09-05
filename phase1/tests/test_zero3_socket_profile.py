import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


def test_fixed_aggregate_budget_uses_terminal_actual_costs():
    a=json.loads((BASE/'manifests/zero3_3090_socket_approval_20260906.json').read_text())
    assert a['prior_actual_gpu_seconds']==2*1+1*5+2*73==153
    assert a['gpu_seconds_upper_bound']==2*(1080+300+60)==2880
    assert a['aggregate_conservative_upper_bound']==153+2880==3033<=a['aggregate_cap_gpu_seconds']==3120
    assert a['automatic_retries']==0


def test_only_new_communication_and_diagnostic_profile_differs():
    previous=(BASE/'scripts/zero3_3090_private_20260906.sbatch').read_text()
    new=(BASE/'scripts/zero3_3090_socket_20260906.sbatch').read_text()
    expected=previous.replace('critic_zero3_private','critic_zero3_socket').replace('NCCL_DEBUG=WARN','NCCL_DEBUG=INFO')
    expected=expected.replace('export SLURM_CONF=','export NCCL_IB_DISABLE=1 NCCL_NET=Socket\nexport PYTHONFAULTHANDLER=1\nexport SLURM_CONF=')
    assert new==expected


def test_matrix_and_budget_are_not_method_changes():
    old=json.loads((BASE/'manifests/zero3_3090_private_approval_20260906.json').read_text())
    new=json.loads((BASE/'manifests/zero3_3090_socket_approval_20260906.json').read_text())
    for k in ('seed','parameters','trajectories','gpu_count','gpu_model','node','wall_seconds','existing_12535',
              'real_corpus_or_external_model_reads','private_cuda128_manifest_sha256'):
        assert old[k]==new[k]
