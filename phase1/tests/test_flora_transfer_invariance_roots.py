from phase1.flora_transfer_invariance import endpoint_from_row


def test_unscoped_v11_root_may_have_null_parent() -> None:
    row = {
        "id": "root",
        "task": "task",
        "run_id": "run",
        "code": "print(1)",
        "lineage": {
            "parent_id": None,
            "op": "Draft",
            "depth": 0,
            "step": 0,
            "n_siblings": 0,
        },
    }
    assert endpoint_from_row(row, prospective=False)["parent"] is None
