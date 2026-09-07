from kater.branch_lifecycle import DELETE_BRANCH_ON_MERGE, delete_branch_on_merge_enabled


def test_delete_branch_on_merge_documented_true() -> None:
    assert DELETE_BRANCH_ON_MERGE is True
    assert delete_branch_on_merge_enabled() is True
    assert delete_branch_on_merge_enabled.__doc__ is not None
    assert "never call" in delete_branch_on_merge_enabled.__doc__.lower()
