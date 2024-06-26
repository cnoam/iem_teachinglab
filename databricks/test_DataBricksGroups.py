# Minimalist test suite of the DataBricksGroups class
# Noam 2024-06-26

import unittest, os
from .DataBricksGroups import DataBricksGroups
from dotenv import load_dotenv

load_dotenv()


def http_ok( code:int) -> bool:
    return code >=200 and code < 400

class DatabricksGroupsTests(unittest.TestCase):
    def setUp(self):
        self.host = os.getenv('DATABRICKS_HOST')
        assert self.host.startswith("adb-")
        self.host = "https://" + self.host
        self.token = os.getenv('DATABRICKS_TOKEN')
        self.api = DataBricksGroups(host=self.host, token=self.token)

    def test_list_users(self):
        users = self.api.list_users()
        # Assert that users is a list and has at least one user
        self.assertIsInstance(users, list)
        self.assertEqual(len(users), 0)

    def test_create_user(self):
        n = self.api.create_users(["tester00@nono.com"])
        self.assertEqual(1,n)

    # Test to create a group using the actual API call
    def test_create_group(self):
        group_name = "test_group"

        # Create the group
        response = self.api.create_group(group_name)

        # Assert successful response status code
        self.assertTrue(http_ok(response.status_code))

        # Cleanup - Delete the created group
        code = self.api.delete_group(group_name)
        self.assertTrue(http_ok(code))

    def test_delete_nonexistant_group(self):
        code = self.api.delete_group("noname 25234")
        self.assertEqual(404,code)

    # Test to add a user to a group using the actual API call
    def test_add_member_to_group_user(self):
        user_name = "user1@example.com"
        group_name = "my_group"

        self.assertTrue(http_ok(self.api.create_group(group_name).status_code))
        # Add user to group
        response = self.api.add_member_to_group(user_name, group_name, is_user=True)

        # Assert successful response status code
        self.assertEqual(200,response.status_code)

    # Test to add a group to a group using the actual API call
    def test_add_group_group(self):
        response = self.api.create_group("test_g1")
        response = self.api.create_group("test_g2")
        # Add group to group
        response = self.api.add_member_to_group("test_g1", "test_g2", is_user=False)

        # Assert successful response status code
        self.assertTrue( http_ok(response.status_code))



    # Test to delete users using the actual API call
    def test_delete_users(self):
        # Replace with a list of user IDs you want to delete (for testing)
        user_ids = [1]

        # Delete users
        users_deleted = self.api.delete_users(user_ids)

        # Assert that the number of deleted users matches the list size
        self.assertEqual(users_deleted, len(user_ids))

    # Test to get group members using the actual API call
    def test_get_group_members(self):
        group_name = "my_group"

        # Get group members
        members = self.api.get_group_members(group_name)

        # Assert that members is a list
        self.assertIsInstance(members, list)

