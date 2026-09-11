from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class SettingsIntegrationsE2ETestCase(LinkdingE2ETestCase):
    def read_clipboard(self):
        return self.page.evaluate("navigator.clipboard.readText()")

    def test_create_api_token(self):
        self.open(reverse("linkding:settings.integrations"))
        api_section = self.page.locator("#api-section")

        # Click create API token button
        api_section.get_by_text("Create API token").click()

        # Wait for modal to appear
        modal = self.page.locator(".modal")
        expect(modal).to_be_visible()

        # Enter custom token name
        token_name_input = modal.locator("#token-name")
        token_name_input.fill("")
        token_name_input.fill("My Test Token")

        # Confirm the dialog
        modal.page.get_by_role("button", name="Create Token").click()

        # Verify the API token key is shown in the input
        new_token_input = self.page.locator("#new-token-key")
        expect(new_token_input).to_be_visible()
        token_value = new_token_input.input_value()
        self.assertTrue(len(token_value) > 0)

        # Verify the API token is now listed in the table
        token_table = api_section.locator("table.crud-table")
        expect(token_table).to_be_visible()
        expect(token_table.get_by_text("My Test Token")).to_be_visible()

        # Verify the dialog is gone
        expect(modal).to_be_hidden()

        # Reload the page to verify the API token key is only shown once
        self.page.reload()

        # Token key input should no longer be visible
        expect(new_token_input).not_to_be_visible()

        # But the token should still be listed in the table
        expect(token_table.get_by_text("My Test Token")).to_be_visible()

    def test_delete_api_token(self):
        self.setup_api_token(name="Token To Delete")

        self.open(reverse("linkding:settings.integrations"))
        api_section = self.page.locator("#api-section")

        token_table = api_section.locator("table.crud-table")
        expect(token_table.get_by_text("Token To Delete")).to_be_visible()

        # Click delete button for the token
        token_row = token_table.locator("tr").filter(has_text="Token To Delete")
        token_row.get_by_role("button", name="Delete").click()

        # Confirm deletion
        self.locate_confirm_dialog().get_by_text("Confirm").click()

        # Verify the token row is removed from the table (scoped to the
        # table, since the API section has no success toast that would
        # otherwise also match the deleted token's name)
        expect(token_table.get_by_text("Token To Delete")).not_to_be_visible()

    def test_create_feed_token(self):
        self.open(reverse("linkding:settings.integrations"))
        feed_section = self.page.locator("#feed-section")

        # Click create feed token button
        feed_section.get_by_text("Create feed token").click()

        # Wait for modal to appear
        modal = self.page.locator(".modal")
        expect(modal).to_be_visible()

        # Enter custom token name
        token_name_input = modal.locator("#feed-token-name")
        token_name_input.fill("")
        token_name_input.fill("My Feed Token")

        # Confirm the dialog
        modal.page.get_by_role("button", name="Create Token").click()

        # Verify the dialog is gone
        expect(modal).to_be_hidden()

        # Verify the feed token is now listed in the table, along with its
        # RSS and Atom feed links
        feed_token_row = feed_section.locator("tr").filter(has_text="My Feed Token")
        expect(feed_token_row).to_be_visible()
        expect(feed_token_row.get_by_role("link", name="RSS").first).to_be_visible()
        expect(feed_token_row.get_by_role("link", name="Atom").first).to_be_visible()

    def test_delete_feed_token(self):
        self.setup_feed_token(name="Feed Token To Delete")

        self.open(reverse("linkding:settings.integrations"))
        feed_section = self.page.locator("#feed-section")

        token_table = feed_section.locator("table.crud-table")
        expect(token_table.get_by_text("Feed Token To Delete")).to_be_visible()

        # Click delete button for the token
        token_row = token_table.locator("tr").filter(has_text="Feed Token To Delete")
        token_row.get_by_role("button", name="Delete").click()

        # Confirm deletion
        self.locate_confirm_dialog().get_by_text("Confirm").click()

        # Verify the token row is removed from the table. Scoped to the
        # table rather than the whole feed section, since the success toast
        # deliberately still mentions the deleted token's name.
        expect(token_table.get_by_text("Feed Token To Delete")).not_to_be_visible()

    def test_copy_feed_url(self):
        token = self.setup_feed_token(name="My Feed Token")

        self.open(reverse("linkding:settings.integrations"))
        feed_section = self.page.locator("#feed-section")
        feed_token_row = feed_section.locator("tr").filter(has_text="My Feed Token")

        copy_button = feed_token_row.get_by_role(
            "button", name="Copy All bookmarks RSS URL"
        )
        copy_button.click()

        expected_url = self.live_server_url + reverse(
            "linkding:feeds.all", args=[token.key]
        )
        self.assertEqual(self.read_clipboard(), expected_url)

        # Button gives feedback, then reverts to its original label
        expect(copy_button).to_have_text("Copied!")
        expect(copy_button).to_have_text("Copy", timeout=3000)
