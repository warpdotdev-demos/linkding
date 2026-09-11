from django.test import TestCase
from django.urls import reverse

from bookmarks.models import ApiToken, FeedToken
from bookmarks.tests.helpers import BookmarkFactoryMixin, HtmlTestMixin


class SettingsIntegrationsViewTestCase(TestCase, BookmarkFactoryMixin, HtmlTestMixin):
    def setUp(self) -> None:
        user = self.get_or_create_test_user()
        self.client.force_login(user)

    def test_should_render_successfully(self):
        response = self.client.get(reverse("linkding:settings.integrations"))

        self.assertEqual(response.status_code, 200)

    def test_should_check_authentication(self):
        self.client.logout()
        response = self.client.get(
            reverse("linkding:settings.integrations"), follow=True
        )

        self.assertRedirects(
            response,
            reverse("login") + "?next=" + reverse("linkding:settings.integrations"),
        )

    def test_create_api_token(self):
        response = self.client.post(
            reverse("linkding:settings.integrations.create_api_token"),
            {"name": "My Test Token"},
        )

        self.assertRedirects(response, reverse("linkding:settings.integrations"))
        self.assertEqual(ApiToken.objects.count(), 1)
        token = ApiToken.objects.first()
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.name, "My Test Token")

    def test_create_api_token_with_empty_name(self):
        self.client.post(
            reverse("linkding:settings.integrations.create_api_token"),
            {"name": ""},
        )

        self.assertEqual(ApiToken.objects.count(), 1)
        token = ApiToken.objects.first()
        self.assertEqual(token.name, "API Token")

    def test_create_api_token_shows_key_once(self):
        self.client.post(
            reverse("linkding:settings.integrations.create_api_token"),
            {"name": "My Token"},
        )

        # First load should show the token
        response = self.client.get(reverse("linkding:settings.integrations"))
        token = ApiToken.objects.first()
        self.assertContains(response, token.key)

        # Second load should not show the token
        response = self.client.get(reverse("linkding:settings.integrations"))
        self.assertNotContains(response, token.key)

    def test_delete_api_token(self):
        token = self.setup_api_token(name="To Delete")

        response = self.client.post(
            reverse("linkding:settings.integrations.delete_api_token"),
            {"token_id": token.id},
        )

        self.assertRedirects(response, reverse("linkding:settings.integrations"))
        self.assertEqual(ApiToken.objects.count(), 0)

    def test_delete_api_token_wrong_user(self):
        other_user = self.setup_user(name="other")
        token = self.setup_api_token(user=other_user, name="Other's Token")

        response = self.client.post(
            reverse("linkding:settings.integrations.delete_api_token"),
            {"token_id": token.id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ApiToken.objects.count(), 1)

    def test_list_api_tokens(self):
        self.setup_api_token(name="Token 1")
        self.setup_api_token(name="Token 2")

        other_user = self.setup_user(name="other")
        self.setup_api_token(user=other_user, name="Other's Token")

        response = self.client.get(reverse("linkding:settings.integrations"))
        soup = self.make_soup(response.content.decode())

        section = soup.find("turbo-frame", id="api-section")
        table = section.find("table")
        rows = table.find_all("tr")

        self.assertEqual(len(rows), 3)

        first_row_cells = rows[1].find_all("td")
        self.assertEqual(first_row_cells[0].get_text(strip=True), "Token 2")
        self.assertIsNotNone(first_row_cells[1].get_text(strip=True))

        second_row_cells = rows[2].find_all("td")
        self.assertEqual(second_row_cells[0].get_text(strip=True), "Token 1")
        self.assertIsNotNone(second_row_cells[1].get_text(strip=True))

    def test_should_generate_default_feed_token_if_not_exists(self):
        self.assertEqual(FeedToken.objects.count(), 0)

        self.client.get(reverse("linkding:settings.integrations"))

        self.assertEqual(FeedToken.objects.count(), 1)
        token = FeedToken.objects.first()
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.name, "Default feed token")

    def test_should_not_generate_feed_token_if_exists(self):
        self.setup_feed_token(name="Existing token")
        self.assertEqual(FeedToken.objects.count(), 1)

        self.client.get(reverse("linkding:settings.integrations"))

        self.assertEqual(FeedToken.objects.count(), 1)

    def test_should_display_feed_urls_for_each_token(self):
        token = self.setup_feed_token(name="My Feed Token")

        response = self.client.get(reverse("linkding:settings.integrations"))
        html = response.content.decode()

        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/all">RSS</a>',
            html,
        )
        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/all.atom">Atom</a>',
            html,
        )
        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/unread">RSS</a>',
            html,
        )
        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/unread.atom">Atom</a>',
            html,
        )
        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/shared">RSS</a>',
            html,
        )
        self.assertInHTML(
            f'<a target="_blank" href="/feeds/{token.key}/shared.atom">Atom</a>',
            html,
        )

    def test_should_display_public_shared_feed_urls(self):
        response = self.client.get(reverse("linkding:settings.integrations"))
        html = response.content.decode()

        self.assertInHTML(
            '<a target="_blank" href="/feeds/shared">RSS</a>',
            html,
        )
        self.assertInHTML(
            '<a target="_blank" href="/feeds/shared.atom">Atom</a>',
            html,
        )

    def test_create_feed_token(self):
        response = self.client.post(
            reverse("linkding:settings.integrations.create_feed_token"),
            {"name": "My Feed Token"},
        )

        self.assertRedirects(response, reverse("linkding:settings.integrations"))
        self.assertEqual(FeedToken.objects.count(), 1)
        token = FeedToken.objects.first()
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.name, "My Feed Token")

    def test_create_feed_token_with_empty_name(self):
        self.client.post(
            reverse("linkding:settings.integrations.create_feed_token"),
            {"name": ""},
        )

        self.assertEqual(FeedToken.objects.count(), 1)
        token = FeedToken.objects.first()
        self.assertEqual(token.name, "Feed token")

    def test_create_second_feed_token_keeps_first(self):
        first_token = self.setup_feed_token(name="First token")

        self.client.post(
            reverse("linkding:settings.integrations.create_feed_token"),
            {"name": "Second token"},
        )

        self.assertEqual(FeedToken.objects.count(), 2)
        self.assertTrue(FeedToken.objects.filter(pk=first_token.key).exists())

        # Both tokens must independently serve their own feed URLs
        second_token = FeedToken.objects.exclude(pk=first_token.key).get()
        response = self.client.get(
            reverse("linkding:feeds.all", args=[first_token.key])
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse("linkding:feeds.all", args=[second_token.key])
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_feed_token(self):
        token = self.setup_feed_token(name="To Delete")

        response = self.client.post(
            reverse("linkding:settings.integrations.delete_feed_token"),
            {"token_key": token.key},
        )

        self.assertRedirects(response, reverse("linkding:settings.integrations"))
        self.assertFalse(FeedToken.objects.filter(pk=token.key).exists())

    def test_delete_feed_token_invalidates_only_that_token(self):
        token_a = self.setup_feed_token(name="Token A")
        token_b = self.setup_feed_token(name="Token B")

        self.client.post(
            reverse("linkding:settings.integrations.delete_feed_token"),
            {"token_key": token_a.key},
        )

        response = self.client.get(reverse("linkding:feeds.all", args=[token_a.key]))
        self.assertEqual(response.status_code, 404)

        response = self.client.get(reverse("linkding:feeds.all", args=[token_b.key]))
        self.assertEqual(response.status_code, 200)

    def test_delete_feed_token_wrong_user(self):
        other_user = self.setup_user(name="other")
        token = self.setup_feed_token(user=other_user, name="Other's Token")

        response = self.client.post(
            reverse("linkding:settings.integrations.delete_feed_token"),
            {"token_key": token.key},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(FeedToken.objects.count(), 1)

    def test_list_feed_tokens_only_for_current_user(self):
        self.setup_feed_token(name="Token 1")
        self.setup_feed_token(name="Token 2")

        other_user = self.setup_user(name="other")
        self.setup_feed_token(user=other_user, name="Other's Token")

        response = self.client.get(reverse("linkding:settings.integrations"))
        soup = self.make_soup(response.content.decode())

        section = soup.find("turbo-frame", id="feed-section")
        table = section.find("table")
        rows = table.find_all("tr")

        # header row + 2 own tokens, not the other user's token
        self.assertEqual(len(rows), 3)
        table_text = table.get_text()
        self.assertIn("Token 1", table_text)
        self.assertIn("Token 2", table_text)
        self.assertNotIn("Other's Token", table_text)
