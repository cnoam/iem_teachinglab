# test_serverless_enforcement.py
# SCIM block/restore lever (plan 2.5). requests is fully mocked -- no
# network calls.

from unittest.mock import patch, MagicMock

from dbr_admin.resource_manager.serverless_enforcement import (
    find_group_id, block_group, restore_group, ALL_STUDENT_GROUPS_NAME,
)

MOD = 'dbr_admin.resource_manager.serverless_enforcement'


def _groups_get_response(group_id):
    resp = MagicMock()
    resp.json.return_value = {'Resources': [{'id': group_id}]} if group_id else {'Resources': []}
    resp.raise_for_status = MagicMock()
    return resp


@patch(f'{MOD}.requests.get')
def test_find_group_id_found(mock_get):
    mock_get.return_value = _groups_get_response('gid123')
    assert find_group_id('host', 'token', 'group_01') == 'gid123'


@patch(f'{MOD}.requests.get')
def test_find_group_id_not_found(mock_get):
    mock_get.return_value = _groups_get_response(None)
    assert find_group_id('host', 'token', 'nonexistent') is None


@patch(f'{MOD}.requests.patch')
@patch(f'{MOD}.find_group_id')
def test_block_group_removes_member(mock_find, mock_patch):
    mock_find.side_effect = ['parent-id', 'member-id']  # parent then member lookup order
    mock_patch.return_value = MagicMock(raise_for_status=MagicMock())

    result = block_group('host', 'token', 'group_01', MagicMock())

    assert result is True
    url, kwargs = mock_patch.call_args.args[0], mock_patch.call_args.kwargs
    assert 'parent-id' in url
    ops = kwargs['json']['Operations']
    assert ops[0]['op'] == 'remove'
    assert 'member-id' in ops[0]['path']


@patch(f'{MOD}.requests.patch')
@patch(f'{MOD}.find_group_id')
def test_restore_group_adds_member(mock_find, mock_patch):
    mock_find.side_effect = ['parent-id', 'member-id']
    mock_patch.return_value = MagicMock(raise_for_status=MagicMock())

    result = restore_group('host', 'token', 'group_01', MagicMock())

    assert result is True
    ops = mock_patch.call_args.kwargs['json']['Operations']
    assert ops[0]['op'] == 'add'
    assert ops[0]['value'] == [{'value': 'member-id'}]


@patch(f'{MOD}.requests.patch')
@patch(f'{MOD}.find_group_id')
def test_block_group_fails_gracefully_when_group_id_missing(mock_find, mock_patch):
    mock_find.side_effect = [None, 'member-id']  # parent group not found
    logger = MagicMock()

    result = block_group('host', 'token', 'group_01', logger)

    assert result is False
    mock_patch.assert_not_called()
    logger.error.assert_called_once()
