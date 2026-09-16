# test_group_map.py
from unittest.mock import MagicMock

from databricks.resource_manager.group_map import build_email_to_group_map, GROUP_NAME_PATTERN


def _stub_groups_api(groups: dict):
    """groups: {group_name: [email, ...]}"""
    api = MagicMock()
    api.list_groups.return_value = list(groups.keys())
    api.get_group_members.side_effect = lambda name: [{'user_name': e} for e in groups[name]]
    return api


def test_maps_emails_to_matching_groups_only():
    api = _stub_groups_api({
        'group_01': ['a@test.com', 'b@test.com'],
        'group_02': ['c@test.com'],
        'all_student_groups': ['group_01', 'group_02'],  # not a group_NN name -- skipped
        'admins': ['staff@test.com'],
    })
    mapping = build_email_to_group_map(api)

    assert mapping == {'a@test.com': 'group_01', 'b@test.com': 'group_01', 'c@test.com': 'group_02'}


def test_group_name_pattern():
    assert GROUP_NAME_PATTERN.match('group_01')
    assert GROUP_NAME_PATTERN.match('group_123')
    assert not GROUP_NAME_PATTERN.match('all_student_groups')
    assert not GROUP_NAME_PATTERN.match('admins')
    assert not GROUP_NAME_PATTERN.match('group_')


def test_member_with_no_user_name_is_skipped():
    api = MagicMock()
    api.list_groups.return_value = ['group_01']
    api.get_group_members.return_value = [{'not_user_name': 'x'}]
    assert build_email_to_group_map(api) == {}


def test_user_in_two_groups_keeps_first_and_warns():
    # Shouldn't happen in practice, but ingest must not crash on it.
    api = _stub_groups_api({'group_01': ['a@test.com'], 'group_02': ['a@test.com']})
    logger = MagicMock()
    mapping = build_email_to_group_map(api, logger)

    assert mapping['a@test.com'] == 'group_01'  # first one seen wins
    logger.warning.assert_called_once()
