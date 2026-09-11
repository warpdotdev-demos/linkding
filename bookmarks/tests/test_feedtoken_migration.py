from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FeedTokenMigrationTestCase(TransactionTestCase):
    """
    Verifies that the 0055_feedtoken_name_and_more migration, which changes
    FeedToken.user from a OneToOneField to a ForeignKey and adds a required
    name field, preserves every existing token unchanged and names it
    "Default feed token".
    """

    migrate_from = "0054_bookmarkbundle_filter_shared_and_more"
    migrate_to = "0055_feedtoken_name_and_more"

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([("bookmarks", self.migrate_from)])

        old_apps = self.executor.loader.project_state(
            [("bookmarks", self.migrate_from)]
        ).apps
        OldUser = old_apps.get_model("auth", "User")
        OldFeedToken = old_apps.get_model("bookmarks", "FeedToken")

        self.username = "migrationtestuser"
        old_user = OldUser.objects.create(username=self.username)
        self.old_token = OldFeedToken.objects.create(user=old_user, key="a" * 40)

        # Reapply the migration under test
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([("bookmarks", self.migrate_to)])
        self.executor.loader.build_graph()

    def tearDown(self):
        # Make sure the database ends up back on the latest migration state
        # for subsequent tests.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_token_is_preserved(self):
        user = User.objects.get(username=self.username)
        from bookmarks.models import FeedToken

        token = FeedToken.objects.get(pk=self.old_token.key)
        self.assertEqual(token.key, self.old_token.key)
        self.assertEqual(token.user_id, user.id)
        self.assertEqual(token.created, self.old_token.created)
        self.assertEqual(token.name, "Default feed token")

    def test_existing_token_url_still_resolves(self):
        from django.urls import reverse

        url = reverse("linkding:feeds.all", args=[self.old_token.key])
        self.assertEqual(url, f"/feeds/{self.old_token.key}/all")
