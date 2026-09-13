"""Source completion only. The prior four fits/results are not rerun or changed."""
from inventory_legacy_validity_20260914 import main

if __name__=='__main__':
    main(group_names=(
        'user_yzyang4_issue_deepseek_mcts_t0',
        'user_yzyang4_issue_deepseek_mcts_t0_nomad',
        'user_yzyang4_issue_deepseek_smoke',
        'user_yzyang4_issue_deepseek_pilot',
        'user_yzyang4_issue_deepseek_pilot2',
        'user_yzyang4_issue_deepseek_guard',
        'user_yzyang4_issue_deepseek_guard2',
        'user_yzyang4_issue_deepseek_guard3',
        'user_yzyang4_issue_deepseek_guard4'),
        output_prefix='forets-early-space-validity-20260914-',required_task='spaceship-titanic')
