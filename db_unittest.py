import time
import unittest

# Import the module under test.
# Assumes the original code is saved as persona_db.py.
from persona_db.helper_func import _split_uid_list, _join_uid_list
from persona_db.PersonaDatabase import (
    Persona, DiscordUser, ChatInteraction, PersonaMemories,
    PersonaVisibility,
    PersonaDatabase,
    main_test,
)

class TestHelperFunctions(unittest.TestCase):
    def test_split_uid_list_empty(self):
        self.assertEqual(_split_uid_list(""), [])
        self.assertEqual(_split_uid_list(" "), [])

    def test_split_uid_list_single(self):
        self.assertEqual(_split_uid_list("1"), [1])
        self.assertEqual(_split_uid_list(" 42 "), [42])

    def test_split_uid_list_multiple(self):
        self.assertEqual(_split_uid_list("1,2,3"), [1, 2, 3])
        self.assertEqual(_split_uid_list("10, 20,30"), [10, 20, 30])

    def test_join_uid_list(self):
        self.assertEqual(_join_uid_list([1, 2, 3]), "1,2,3")
        self.assertEqual(_join_uid_list([]), "")
        self.assertEqual(_join_uid_list([42]), "42")


class TestDataModels(unittest.TestCase):
    def test_persona_permission_check_private_owner(self):
        p = Persona(uid=1, persona_name="Test", content="", owner_uid=100,
                    is_public=False, allowed_role_ids=set(), created_at="", updated_at="")
        self.assertTrue(p.permission_shallow(100, set()))
        self.assertFalse(p.permission_shallow(200, set()))

    def test_persona_permission_check_public(self):
        p = Persona(uid=1, persona_name="Test", content="", owner_uid=100,
                    is_public=True, allowed_role_ids=set(), created_at="", updated_at="")
        self.assertTrue(p.permission_shallow(100, set()))
        self.assertTrue(p.permission_shallow(200, set()))

    def test_discord_user_balance(self):
        u = DiscordUser(user_uid=1, selected_persona_uid=0)
        u.set_balance(50)
        self.assertEqual(u.balance, 50)

    def test_discord_user_adjust_balance_positive(self):
        u = DiscordUser(user_uid=1, selected_persona_uid=0, balance=100)
        u.adjust_balance(20)
        self.assertEqual(u.balance, 120)

    def test_discord_user_adjust_balance_negative_enough(self):
        u = DiscordUser(user_uid=1, selected_persona_uid=0, balance=100)
        u.adjust_balance(-30)
        self.assertEqual(u.balance, 70)

    def test_discord_user_adjust_balance_insufficient(self):
        u = DiscordUser(user_uid=1, selected_persona_uid=0, balance=10)
        with self.assertRaises(ValueError):
            u.adjust_balance(-20)
        self.assertEqual(u.balance, 10)  # unchanged

    def test_persona_str(self):
        p = Persona(uid=1, persona_name="Alice", content="", owner_uid=1,
                    is_public=True, allowed_role_ids=set(), created_at="", updated_at="")
        s = str(p)
        self.assertIn("uid=  1", s)
        self.assertIn("persona=Alice", s)

    def test_discord_user_str(self):
        u = DiscordUser(user_uid=42, selected_persona_uid=5, balance=99)
        s = str(u)
        self.assertIn("user_uid=42", s)
        self.assertIn("balance=99", s)


class BaseTestWithDB(unittest.TestCase):
    """Base class that provides a fresh in-memory PersonaDatabase for each test."""
    def setUp(self):
        self.db = PersonaDatabase(":memory:")
        # Ensure a test user exists
        self.db.create_discord_user(100)

    def tearDown(self):
        # No explicit cleanup needed – the in‑memory DB is dropped automatically.
        pass


class TestPersonaRepository(BaseTestWithDB):
    def setUp(self):
        super().setUp()
        self.repo = self.db.personas

    def test_create_and_fetch(self):
        uid = self.repo.create("Bot1", "Hello", 100, PersonaVisibility.PUBLIC)
        self.assertIsNotNone(uid)
        p = self.repo.fetch_by_uid(uid)
        self.assertIsNotNone(p)
        self.assertEqual(p.persona_name, "Bot1")
        self.assertEqual(p.owner_uid, 100)
        self.assertEqual(p.is_public, True)

    def test_fetch_nonexistent(self):
        self.assertIsNone(self.repo.fetch_by_uid(999))

    def test_count_by_owner(self):
        self.assertEqual(self.repo.count_by_owner(100), 0)
        self.repo.create("A", "", 100, PersonaVisibility.PRIVATE)
        self.assertEqual(self.repo.count_by_owner(100), 1)
        self.repo.create("B", "", 100, PersonaVisibility.PRIVATE)
        self.assertEqual(self.repo.count_by_owner(100), 2)

    def test_list_visible_for_user(self):
        uid1 = self.repo.create("Private", "", 100, PersonaVisibility.PRIVATE)
        uid2 = self.repo.create("Public", "", 200, PersonaVisibility.PUBLIC)
        # User 100 sees own private + public
        visible = self.repo.list_visible_for_user(100, [])
        # print("\nVisible personas for user 100:")
        # for p in visible:
        #     print(f"  - {p.persona_name} (is_public={p.is_public})")
        self.assertEqual(len(visible), 2)
        uids = {p.uid for p in visible}
        self.assertIn(uid1, uids)
        self.assertIn(uid2, uids)

        # User 200 sees only public (own persona not created yet)
        visible = self.repo.list_visible_for_user(200, [])
        # print("\nVisible personas for user 200:")
        # for p in visible:
        #     print(f"  - {p.persona_name}")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0].uid, uid2)

    def test_update_success(self):
        uid = self.repo.create("Old", "", 100, PersonaVisibility.PRIVATE)
        result = self.repo.update(uid, 100, persona_name="New", is_public=True)
        self.assertTrue(result)
        p = self.repo.fetch_by_uid(uid)
        self.assertEqual(p.persona_name, "New")
        self.assertEqual(p.is_public, True)

    def test_update_wrong_owner(self):
        uid = self.repo.create("Test", "", 100, PersonaVisibility.PRIVATE)
        result = self.repo.update(uid, 200, persona_name="Hack")
        self.assertFalse(result)
        p = self.repo.fetch_by_uid(uid)
        self.assertEqual(p.persona_name, "Test")  # unchanged

    def test_update_invalid_field(self):
        uid = self.repo.create("Test", "", 100, PersonaVisibility.PRIVATE)
        with self.assertRaises(ValueError):
            self.repo.update(uid, 100, invalid_field=123)

    def test_delete_success(self):
        uid = self.repo.create("DeleteMe", "", 100, PersonaVisibility.PRIVATE)
        result = self.repo.delete(uid, 100)
        self.assertTrue(result)
        self.assertIsNone(self.repo.fetch_by_uid(uid))

    def test_delete_wrong_owner(self):
        uid = self.repo.create("DeleteMe", "", 100, PersonaVisibility.PRIVATE)
        result = self.repo.delete(uid, 200)
        self.assertFalse(result)
        self.assertIsNotNone(self.repo.fetch_by_uid(uid))


class TestDiscordUserRepository(BaseTestWithDB):
    def setUp(self):
        super().setUp()
        self.repo = self.db.users

    def test_create_if_missing(self):
        # User 100 already created in BaseTestWithDB -> should not raise
        self.repo.create_if_missing(100)
        # New user
        self.repo.create_if_missing(999)
        u = self.repo.fetch_by_uid(999)
        self.assertIsNotNone(u)
        self.assertEqual(u.user_uid, 999)
        self.assertEqual(u.balance, 0)

    def test_fetch_existing(self):
        u = self.repo.fetch_by_uid(100)
        self.assertIsNotNone(u)
        self.assertEqual(u.user_uid, 100)
        self.assertEqual(u.balance, 0)

    def test_fetch_nonexistent(self):
        self.assertIsNone(self.repo.fetch_by_uid(12345))

    def test_update(self):
        result = self.repo.update(100, balance=42, interaction_count=5)
        self.assertTrue(result)
        u = self.repo.fetch_by_uid(100)
        self.assertEqual(u.balance, 42)
        self.assertEqual(u.interaction_count, 5)

    def test_update_no_fields(self):
        result = self.repo.update(100)
        self.assertFalse(result)

    def test_update_invalid_field(self):
        with self.assertRaises(ValueError):
            self.repo.update(100, fake="data")

    def test_upsert_selected_persona_new_user(self):
        self.repo.upsert_selected_persona(200, 5)
        self.assertEqual(self.repo.get_selected_persona_uid(200), 5)

    def test_upsert_selected_persona_existing(self):
        self.repo.upsert_selected_persona(100, 10)
        self.assertEqual(self.repo.get_selected_persona_uid(100), 10)
        self.repo.upsert_selected_persona(100, 20)
        self.assertEqual(self.repo.get_selected_persona_uid(100), 20)

    def test_get_selected_persona_uid_default(self):
        # New user without selection returns -1
        self.repo.create_if_missing(300)
        self.assertEqual(self.repo.get_selected_persona_uid(300), -1)

    def test_clear_selected_persona(self):
        self.repo.upsert_selected_persona(100, 7)
        self.repo.clear_selected_persona(100)
        self.assertEqual(self.repo.get_selected_persona_uid(100), -1)

    def test_clear_persona_selection(self):
        # Set same persona for multiple users
        self.repo.upsert_selected_persona(100, 42)
        self.repo.upsert_selected_persona(200, 42)
        self.repo.clear_persona_selection(42)
        self.assertEqual(self.repo.get_selected_persona_uid(100), -1)
        self.assertEqual(self.repo.get_selected_persona_uid(200), -1)


class TestInteractionRepository(BaseTestWithDB):
    def setUp(self):
        super().setUp()
        self.repo = self.db.interactions
        # Create personas to interact with
        self.p1 = self.db.personas.create("BotA", "", 100, PersonaVisibility.PUBLIC)
        self.p2 = self.db.personas.create("BotB", "", 100, PersonaVisibility.PRIVATE)
        self.user_id = 100

    def test_increment_interaction_count_updates_persona(self):
        self.repo.increment_interaction_count(self.p1, self.user_id)
        p = self.db.personas.fetch_by_uid(self.p1)
        self.assertEqual(p.interaction_count, 1)
        self.assertIsNotNone(p.last_interaction_recv_at)

    def test_increment_interaction_count_updates_discord_user(self):
        self.repo.increment_interaction_count(self.p1, self.user_id)
        u = self.db.users.fetch_by_uid(self.user_id)
        self.assertEqual(u.interaction_count, 1)
        self.assertIsNotNone(u.last_interaction_send_at)

    def test_increment_multiple_times(self):
        for _ in range(3):
            self.repo.increment_interaction_count(self.p1, self.user_id)
        p = self.db.personas.fetch_by_uid(self.p1)
        u = self.db.users.fetch_by_uid(self.user_id)
        self.assertEqual(p.interaction_count, 3)
        self.assertEqual(u.interaction_count, 3)

    def test_get_user_interaction_stats_empty(self):
        stats = self.repo.get_user_interaction_stats(999)
        self.assertIsNone(stats)

    def test_get_user_interaction_stats(self):
        self.repo.increment_interaction_count(self.p1, self.user_id)
        self.repo.increment_interaction_count(self.p1, self.user_id)
        self.repo.increment_interaction_count(self.p2, self.user_id)

        stats = self.repo.get_user_interaction_stats(self.user_id)
        assert stats is not None
        self.assertEqual(stats["total_interactions"], 3)
        # Most interacted should be p1
        self.assertEqual(stats["most_interacted_persona_uid"], self.p1)
        self.assertEqual(stats["most_interacted_persona_name"], "BotA")
        self.assertEqual(stats["most_interacted_count"], 2)

    def test_get_top_users(self):
        user2 = 200
        self.db.create_discord_user(user2)
        self.repo.increment_interaction_count(self.p1, self.user_id)
        self.repo.increment_interaction_count(self.p1, user2)
        self.repo.increment_interaction_count(self.p1, user2)

        top = self.repo.get_top_users(limit=2)
        self.assertEqual(len(top), 2)
        # user2 has 2 interactions, user1 has 1
        self.assertEqual(top[0][0], user2)
        self.assertEqual(top[0][1], 2)
        self.assertEqual(top[1][0], self.user_id)
        self.assertEqual(top[1][1], 1)


class TestChatInteractionRepository(BaseTestWithDB):
    def setUp(self):
        super().setUp()
        self.repo = self.db.chat_interactions
        
        self.persona_uid = self.db.personas.create("TestPersona", "", 100, PersonaVisibility.PUBLIC)

    def test_create_and_fetch(self):
        msg_id = 12345
        ok = self.repo.create(msg_id, 100, self.persona_uid, "Hello world")
        self.assertTrue(ok)
        ci = self.repo.fetch_by_msg_uid(msg_id)
        self.assertIsNotNone(ci)
        self.assertEqual(ci.msg_uid, msg_id)
        self.assertEqual(ci.main_content, "Hello world")
        self.assertFalse(ci.is_memorized)

    def test_fetch_nonexistent(self):
        self.assertIsNone(self.repo.fetch_by_msg_uid(99999))

    def test_list_by_persona_uid(self):
        self.repo.create(1, 100, self.persona_uid, "Msg1")
        time.sleep(0.01)  # ensure different timestamps
        self.repo.create(2, 100, self.persona_uid, "Msg2")
        time.sleep(0.01)  # ensure different timestamps
        self.repo.create(3, 200, self.persona_uid, "Msg3")
        results = self.repo.list_by_persona_uid(self.persona_uid)
        # print("\n".join([f"Msg UID: {ci.msg_uid}, Content: {ci.main_content}, created_at: {ci.created_at}" for ci in results]))
        self.assertEqual(len(results), 3)
        # order by created_at DESC, so latest first
        self.assertEqual(results[0].msg_uid, 3)

    def test_list_by_persona_uid_with_limit(self):
        self.repo.create(1, 100, self.persona_uid, "Msg1")
        self.repo.create(2, 100, self.persona_uid, "Msg2")
        results = self.repo.list_by_persona_uid(self.persona_uid, limit=1)
        self.assertEqual(len(results), 1)

    def test_list_by_user_uid(self):
        self.repo.create(1, 100, self.persona_uid, "User1-1")
        time.sleep(0.01)  # ensure different timestamps
        self.repo.create(2, 200, self.persona_uid, "User2-1")
        time.sleep(0.01)  # ensure different timestamps
        self.repo.create(3, 100, self.persona_uid, "User1-2")
        results = self.repo.list_by_user_uid(100)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].msg_uid, 3)  # latest

    def test_update(self):
        msg_id = 1
        self.repo.create(msg_id, 100, self.persona_uid, "original")
        ok = self.repo.update(msg_id, main_content="updated", is_memorized=True)
        self.assertTrue(ok)
        ci = self.repo.fetch_by_msg_uid(msg_id)
        self.assertEqual(ci.main_content, "updated")
        self.assertTrue(ci.is_memorized)

    def test_update_invalid_field(self):
        msg_id = 1
        self.repo.create(msg_id, 100, self.persona_uid, "test")
        with self.assertRaises(ValueError):
            self.repo.update(msg_id, fake="bad")

    def test_mark_memorized(self):
        msg_id = 1
        self.repo.create(msg_id, 100, self.persona_uid, "remember me")
        ok = self.repo.mark_memorized(msg_id, summary="sum")
        self.assertTrue(ok)
        ci = self.repo.fetch_by_msg_uid(msg_id)
        self.assertTrue(ci.is_memorized)
        self.assertEqual(ci.summary, "sum")

    def test_mark_memorized_no_summary(self):
        msg_id = 1
        self.repo.create(msg_id, 100, self.persona_uid, "text")
        self.repo.mark_memorized(msg_id)  # no summary
        ci = self.repo.fetch_by_msg_uid(msg_id)
        self.assertTrue(ci.is_memorized)
        self.assertIsNone(ci.summary)

    def test_delete(self):
        msg_id = 1
        self.repo.create(msg_id, 100, self.persona_uid, "del")
        self.assertTrue(self.repo.delete(msg_id))
        self.assertIsNone(self.repo.fetch_by_msg_uid(msg_id))

    def test_delete_nonexistent(self):
        self.assertFalse(self.repo.delete(99999))


class TestPersonaMemoriesRepository(BaseTestWithDB):
    def setUp(self):
        super().setUp()
        self.repo = self.db.persona_memories
        self.persona_uid = self.db.personas.create("MemBot", "", 100, PersonaVisibility.PUBLIC)

    def test_create_and_fetch(self):
        mid = self.repo.create("Memory1", self.persona_uid, "1,2,3")
        mem = self.repo.fetch_by_uid(mid)
        self.assertIsNotNone(mem)
        self.assertEqual(mem.memory_content, "Memory1")
        self.assertEqual(mem.source_msg_uids, "1,2,3")

    def test_fetch_nonexistent(self):
        self.assertIsNone(self.repo.fetch_by_uid(9999))

    def test_list_by_persona_uid(self):
        m1 = self.repo.create("M1", self.persona_uid, "1")
        m2 = self.repo.create("M2", self.persona_uid, "2")
        results = self.repo.list_by_persona_uid(self.persona_uid)
        self.assertEqual(len(results), 2)
        uids = {m.memory_uid for m in results}
        self.assertIn(m1, uids)
        self.assertIn(m2, uids)

    def test_update(self):
        mid = self.repo.create("Old", self.persona_uid, "1")
        ok = self.repo.update(mid, memory_content="New")
        self.assertTrue(ok)
        mem = self.repo.fetch_by_uid(mid)
        self.assertEqual(mem.memory_content, "New")

    def test_update_invalid_field(self):
        mid = self.repo.create("Test", self.persona_uid, "1")
        with self.assertRaises(ValueError):
            self.repo.update(mid, not_allowed=True)

    def test_delete(self):
        mid = self.repo.create("Delete", self.persona_uid, "1")
        self.assertTrue(self.repo.delete(mid))
        self.assertIsNone(self.repo.fetch_by_uid(mid))


# class TestUserGroupsRepository(BaseTestWithDB):
#     def setUp(self):
#         super().setUp()
#         self.repo = self.db.user_groups

#     def test_create_and_fetch(self):
#         gid = self.repo.create("Group1", [100, 200])
#         group = self.repo.fetch_by_uid(gid)
#         self.assertEqual(group.group_name, "Group1")
#         self.assertEqual(_split_uid_list(group.member_uids), [100, 200])

#     def test_create_no_members(self):
#         gid = self.repo.create("Empty")
#         group = self.repo.fetch_by_uid(gid)
#         self.assertEqual(group.member_uids, "")

#     def test_list_all(self):
#         g1 = self.repo.create("G1")
#         g2 = self.repo.create("G2")
#         all_groups = self.repo.list_all()
#         self.assertEqual(len(all_groups), 2)
#         self.assertIn(g1, [g.group_uid for g in all_groups])
#         self.assertIn(g2, [g.group_uid for g in all_groups])

#     def test_update(self):
#         gid = self.repo.create("OldName", [100])
#         ok = self.repo.update(gid, group_name="NewName", member_uids=[100, 200])
#         self.assertTrue(ok)
#         group = self.repo.fetch_by_uid(gid)
#         self.assertEqual(group.group_name, "NewName")
#         self.assertEqual(_split_uid_list(group.member_uids), [100, 200])

#     def test_update_no_fields(self):
#         gid = self.repo.create("G")
#         self.assertFalse(self.repo.update(gid))

#     def test_update_invalid_field(self):
#         gid = self.repo.create("G")
#         with self.assertRaises(ValueError):
#             self.repo.update(gid, wrong="field")

#     def test_delete(self):
#         gid = self.repo.create("Del")
#         self.assertTrue(self.repo.delete(gid))
#         self.assertIsNone(self.repo.fetch_by_uid(gid))

#     def test_get_member_uids(self):
#         gid = self.repo.create("Members", [1, 2, 3])
#         self.assertEqual(self.repo.get_member_uids(gid), [1, 2, 3])

#     def test_add_member(self):
#         gid = self.repo.create("Group", [100])
#         self.assertTrue(self.repo.add_member(gid, 200))
#         self.assertEqual(self.repo.get_member_uids(gid), [100, 200])

#     def test_add_duplicate_member(self):
#         gid = self.repo.create("Group", [100])
#         self.assertTrue(self.repo.add_member(gid, 100))  # no error
#         self.assertEqual(self.repo.get_member_uids(gid), [100])

#     def test_remove_member(self):
#         gid = self.repo.create("Group", [100, 200, 300])
#         self.assertTrue(self.repo.remove_member(gid, 200))
#         self.assertEqual(self.repo.get_member_uids(gid), [100, 300])

#     def test_remove_nonexistent_member(self):
#         gid = self.repo.create("Group", [100])
#         self.assertTrue(self.repo.remove_member(gid, 999))  # just does nothing
#         self.assertEqual(self.repo.get_member_uids(gid), [100])

#     def test_is_member(self):
#         gid = self.repo.create("Group", [100])
#         self.assertTrue(self.repo.is_member(gid, 100))
#         self.assertFalse(self.repo.is_member(gid, 200))


# class TestPersonaGroupAccessRepository(BaseTestWithDB):
#     def setUp(self):
#         super().setUp()
#         self.repo = self.db.persona_group_access
#         self.g1 = self.db.user_groups.create("G1")
#         self.g2 = self.db.user_groups.create("G2")
#         self.p1 = self.db.personas.create("P1", "", 100, PersonaVisibility.PRIVATE)
#         self.p2 = self.db.personas.create("P2", "", 100, PersonaVisibility.PRIVATE)

#     def test_grant_and_check(self):
#         self.assertTrue(self.repo.grant_access(self.g1, self.p1))
#         self.assertTrue(self.repo.has_access(self.g1, self.p1))
#         self.assertFalse(self.repo.has_access(self.g1, self.p2))

#     def test_grant_duplicate(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.assertFalse(self.repo.grant_access(self.g1, self.p1))  # INSERT OR IGNORE

#     def test_revoke(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.assertTrue(self.repo.revoke_access(self.g1, self.p1))
#         self.assertFalse(self.repo.has_access(self.g1, self.p1))

#     def test_list_access_by_group(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.repo.grant_access(self.g1, self.p2)
#         access_list = self.repo.list_access_by_group(self.g1)
#         self.assertEqual(len(access_list), 2)
#         uids = [a.persona_uid for a in access_list]
#         self.assertIn(self.p1, uids)
#         self.assertIn(self.p2, uids)

#     def test_list_access_by_persona(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.repo.grant_access(self.g2, self.p1)
#         access_list = self.repo.list_access_by_persona(self.p1)
#         self.assertEqual(len(access_list), 2)
#         uids = [a.group_uid for a in access_list]
#         self.assertIn(self.g1, uids)
#         self.assertIn(self.g2, uids)

#     def test_list_persona_uids_for_group(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.repo.grant_access(self.g1, self.p2)
#         pids = self.repo.list_persona_uids_for_group(self.g1)
#         self.assertEqual(pids, [self.p1, self.p2])

#     def test_list_group_uids_for_persona(self):
#         self.repo.grant_access(self.g1, self.p1)
#         self.repo.grant_access(self.g2, self.p1)
#         gids = self.repo.list_group_uids_for_persona(self.p1)
#         self.assertEqual(gids, [self.g1, self.g2])


# class TestPersonaDatabaseIntegration(BaseTestWithDB):
#     def setUp(self):
#         super().setUp()
#         self.user = 100
#         self.other_user = 200
#         self.db.create_discord_user(self.other_user)

#     def test_create_persona_within_limit(self):
#         for i in range(5):
#             uid = self.db.create_persona(f"Bot{i}", "", self.user, PersonaVisibility.PRIVATE)
#             self.assertGreater(uid, 0)
#         self.assertEqual(self.db.personas.count_by_owner(self.user), 5)

#     def test_create_persona_exceeds_limit(self):
#         for i in range(5):
#             self.db.create_persona(f"Bot{i}", "", self.user, PersonaVisibility.PRIVATE)
#         # 6th should fail and return -1
#         uid = self.db.create_persona("Extra", "", self.user, PersonaVisibility.PRIVATE)
#         self.assertEqual(uid, -1)

#     def test_get_persona_with_permission(self):
#         pid = self.db.create_persona("Private", "", self.user, PersonaVisibility.PRIVATE)
#         p = self.db.get_persona(pid, self.user)
#         self.assertIsNotNone(p)
#         # Another user should not see it
#         self.assertIsNone(self.db.get_persona(pid, self.other_user))

#     def test_set_selected_persona(self):
#         pid = self.db.create_persona("Public", "", self.user, PersonaVisibility.PUBLIC)
#         self.assertTrue(self.db.set_selected_persona(self.user, pid))
#         sel = self.db.get_selected_persona(self.user)
#         self.assertIsNotNone(sel)
#         self.assertEqual(sel.uid, pid)

#     def test_set_selected_persona_no_permission(self):
#         pid = self.db.create_persona("Private", "", self.user, PersonaVisibility.PRIVATE)
#         self.assertFalse(self.db.set_selected_persona(self.other_user, pid))

#     def test_clear_selected_persona(self):
#         pid = self.db.create_persona("P", "", self.user, PersonaVisibility.PUBLIC)
#         self.db.set_selected_persona(self.user, pid)
#         self.db.clear_selected_persona(self.user)
#         self.assertIsNone(self.db.get_selected_persona(self.user))

#     def test_delete_persona_clears_selection(self):
#         pid = self.db.create_persona("ToDelete", "", self.user, PersonaVisibility.PUBLIC)
#         self.db.set_selected_persona(self.user, pid)
#         self.db.delete_persona(pid, self.user)
#         self.assertIsNone(self.db.personas.fetch_by_uid(pid))
#         self.assertEqual(self.db.users.get_selected_persona_uid(self.user), -1)

#     def test_user_can_access_persona_via_group(self):
#         gid = self.db.create_user_group("Friends", [self.other_user])
#         pid = self.db.create_persona("Shared", "", self.user, PersonaVisibility.PRIVATE)
#         self.db.grant_persona_group_access(gid, pid)
#         # owner can always access, but other_user should now have group access
#         self.assertTrue(self.db.user_can_access_persona_via_group(self.other_user, pid))

#     def test_list_personas_accessible_via_group(self):
#         gid = self.db.create_user_group("Fans", [self.other_user])
#         pid1 = self.db.create_persona("Hidden1", "", self.user, PersonaVisibility.PRIVATE)
#         pid2 = self.db.create_persona("Hidden2", "", self.user, PersonaVisibility.PRIVATE)
#         self.db.grant_persona_group_access(gid, pid1)
#         self.db.grant_persona_group_access(gid, pid2)
#         personas = self.db.list_personas_accessible_via_group(self.other_user)
#         self.assertEqual(len(personas), 2)
#         self.assertIn(pid1, [p.uid for p in personas])

#     def test_get_selected_persona_after_permission_loss(self):
#         # Create a private persona and set it for user, then change visibility to public? Actually
#         # permission_check depends on current visibility, so if it becomes private for another user
#         # they lose access. But we can test that if user is removed from group that granted access,
#         # selected persona becomes inaccessible.
#         gid = self.db.create_user_group("Temp", [self.other_user])
#         pid = self.db.create_persona("GroupOnly", "", self.user, PersonaVisibility.PRIVATE)
#         self.db.grant_persona_group_access(gid, pid)
#         # other_user sets it as selected
#         self.assertTrue(self.db.set_selected_persona(self.other_user, pid))
#         self.assertIsNotNone(self.db.get_selected_persona(self.other_user))
#         # Now remove group membership
#         self.db.remove_user_from_group(gid, self.other_user)
#         # The permission check in get_selected_persona will fail because other_user is no longer owner
#         # and not in group, so it should return None.
#         res = self.db.get_selected_persona(self.other_user)
#         print(f"Selected persona for other_user after group removal: {res}")
#         self.assertIsNone(self.db.get_selected_persona(self.other_user))

#     def test_increment_interaction_count_and_stats(self):
#         pid = self.db.create_persona("Interactive", "", self.user, PersonaVisibility.PUBLIC)
#         self.db.increment_interaction_count(pid, self.user)
#         self.db.increment_interaction_count(pid, self.other_user)
#         self.db.increment_interaction_count(pid, self.other_user)
#         stats = self.db.get_user_interaction_stats(self.other_user)
#         assert stats is not None
#         self.assertEqual(stats["total_interactions"], 2)
#         top = self.db.get_top_users()
#         self.assertEqual(top[0][0], self.other_user)  # 2 > 1

#     def test_chat_interaction_flow(self):
#         pid = self.db.create_persona("Chatty", "", self.user, PersonaVisibility.PUBLIC)
#         msg = 1001
#         self.assertTrue(self.db.create_chat_interaction(msg, self.user, pid, "Hello"))
#         ci = self.db.get_chat_interaction(msg)
#         self.assertEqual(ci.main_content, "Hello")
#         self.assertFalse(ci.is_memorized)
#         self.db.mark_chat_interaction_memorized(msg, "Greeting")
#         ci = self.db.get_chat_interaction(msg)
#         self.assertTrue(ci.is_memorized)
#         self.assertEqual(ci.summary, "Greeting")

#     def test_user_balance_through_database(self):
#         self.db.update_discord_user(self.user, balance=50)
#         u = self.db.get_discord_user(self.user)
#         self.assertEqual(u.balance, 50)


if __name__ == '__main__':
    unittest.main()
    # main_test()