import json

from src.mle_policy.src.data.run_inventory import (
    collect_inventory,
    filter_records,
    group_records,
    list_tasks,
    read_run_record,
)


def write_run(root, date, run_name, clients, *, task="spaceship-titanic", with_journal=True):
    """Write one run with the given ``{operator: (base_url, model_id)}`` clients."""
    run_dir = root / date / run_name / (run_name + "_seed_1_id_abc")
    run_dir.mkdir(parents=True, exist_ok=True)
    operators = {
        operator: {"llm": {"client": {"provider": "openai", "model_id": model, "base_url": base_url}}}
        for operator, (base_url, model) in clients.items()
    }
    (run_dir / "dojo_config.json").write_text(
        json.dumps({"id": run_dir.name, "metadata": {"seed": 1}, "task": {"name": task}, "solver": {"operators": operators}}),
        encoding="utf-8",
    )
    if with_journal:
        checkpoint = run_dir / "checkpoint"
        checkpoint.mkdir(exist_ok=True)
        (checkpoint / "journal.jsonl").write_text("", encoding="utf-8")
    return run_dir


def test_collect_inventory_reads_clients_and_skips_comparison(tmp_path):
    write_run(
        tmp_path,
        "0814",
        "user_zzchen2_issue_tgs-salt-identification-challenge-8seeds",
        {"draft": ("https://api.deepseek.com", "deepseek-v4-flash")},
        task="tgs-salt-identification-challenge",
    )
    # A run under the skipped directory must not show up.
    write_run(
        tmp_path,
        "comparison/0930/tgs-salt-identification-challenge/200/some-model/openai",
        "user_zjchen_issue_ignore-me-1seed",
        {"draft": ("https://openrouter.ai/api/v1", "kimi")},
    )

    records = collect_inventory(tmp_path)
    assert len(records) == 1
    record = records[0]
    assert record.user == "zzchen2"
    assert record.issue == "tgs-salt-identification-challenge-8seeds"
    assert record.model_keys == (("https://api.deepseek.com", "deepseek-v4-flash"),)
    assert record.has_journal is True
    assert record.is_mixed is False


def test_mixed_run_lands_in_every_model_bucket(tmp_path):
    write_run(
        tmp_path,
        "0816",
        "user_zzchen2_issue_runs-4seeds",
        {
            "analyze": ("https://api.chatanywhere.org", "gpt-5.4-nano"),
            "draft": ("https://api.chatanywhere.org", "gpt-5.6-luna"),
        },
    )
    record = read_run_record(next((tmp_path).rglob("dojo_config.json")).parent, tmp_path)
    assert record.is_mixed is True

    buckets = group_records([record])["spaceship-titanic"]
    assert buckets["https://api.chatanywhere.org :: gpt-5.4-nano"] == [record]
    assert buckets["https://api.chatanywhere.org :: gpt-5.6-luna"] == [record]


def test_require_journal_drops_killed_runs_and_lists_tasks(tmp_path):
    write_run(tmp_path, "0814", "user_a_issue_alive-1seed", {"draft": ("", "m")})
    write_run(tmp_path, "0814", "user_a_issue_dead-1seed", {"draft": ("", "m")}, with_journal=False)

    assert list_tasks(collect_inventory(tmp_path)) == {"spaceship-titanic": 2}
    assert len(filter_records(collect_inventory(tmp_path), require_journal=True)) == 1
