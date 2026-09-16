# test_serverless_enforcement.py
# SCIM block/restore lever (plan 2.5), against a mocked SDK client -- no
# network calls.

from unittest.mock import MagicMock

from databricks.sdk.errors import PermissionDenied
from databricks.sdk.service.iam import Group, PatchOp

from dbr_admin.resource_manager.serverless_enforcement import (
    find_group_id, block_group, restore_group, ALL_STUDENT_GROUPS_NAME,
)


def _client_with_groups(**id_by_name):
    """A mock WorkspaceClient whose groups.list(filter=...) resolves a
    displayName filter to the matching group's id, or an empty iterator."""
    client = MagicMock()

    def list_side_effect(filter=None, **kwargs):
        for name, group_id in id_by_name.items():
            if filter == f'displayName eq "{name}"':
                return iter([Group(id=group_id, display_name=name)])
        return iter([])

    client.groups.list.side_effect = list_side_effect
    return client


def test_find_group_id_found():
    client = _client_with_groups(group_01='gid123')
    assert find_group_id(client, 'group_01') == 'gid123'


def test_find_group_id_not_found():
    client = _client_with_groups()
    assert find_group_id(client, 'nonexistent') is None


def test_block_group_removes_member():
    client = _client_with_groups(**{ALL_STUDENT_GROUPS_NAME: 'parent-id', 'group_01': 'member-id'})

    result = block_group(client, 'group_01', MagicMock())

    assert result is True
    client.groups.patch.assert_called_once()
    call = client.groups.patch.call_args
    assert call.args[0] == 'parent-id'
    ops = call.kwargs['operations']
    assert ops[0].op == PatchOp.REMOVE
    assert 'member-id' in ops[0].path


def test_restore_group_adds_member():
    client = _client_with_groups(**{ALL_STUDENT_GROUPS_NAME: 'parent-id', 'group_01': 'member-id'})

    result = restore_group(client, 'group_01', MagicMock())

    assert result is True
    call = client.groups.patch.call_args
    assert call.args[0] == 'parent-id'
    ops = call.kwargs['operations']
    assert ops[0].op == PatchOp.ADD
    assert ops[0].value == [{'value': 'member-id'}]


def test_block_group_fails_gracefully_when_group_id_missing():
    client = _client_with_groups(**{'group_01': 'member-id'})  # all_student_groups not found
    logger = MagicMock()

    result = block_group(client, 'group_01', logger)

    assert result is False
    client.groups.patch.assert_not_called()
    logger.error.assert_called_once()


def test_block_group_fails_gracefully_when_patch_raises():
    client = _client_with_groups(**{ALL_STUDENT_GROUPS_NAME: 'parent-id', 'group_01': 'member-id'})
    client.groups.patch.side_effect = PermissionDenied("nope")
    logger = MagicMock()

    result = block_group(client, 'group_01', logger)

    assert result is False
    logger.error.assert_called_once()


def test_restore_group_fails_gracefully_when_patch_raises():
    client = _client_with_groups(**{ALL_STUDENT_GROUPS_NAME: 'parent-id', 'group_01': 'member-id'})
    client.groups.patch.side_effect = PermissionDenied("nope")
    logger = MagicMock()

    result = restore_group(client, 'group_01', logger)

    assert result is False
    logger.error.assert_called_once()
