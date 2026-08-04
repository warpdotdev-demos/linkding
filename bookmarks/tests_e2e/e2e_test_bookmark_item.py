from unittest import skip

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class BookmarkItemE2ETestCase(LinkdingE2ETestCase):
    def test_unread_chip_should_render_next_to_title(self):
        bookmark = self.setup_bookmark(title="Unread bookmark", unread=True)

        self.open(reverse("linkding:bookmarks.index"))

        bookmark_item = self.locate_bookmark(bookmark.title)
        title_text = bookmark_item.locator(".title a span")
        chip = bookmark_item.locator(".title .unread-chip")
        expect(chip).to_be_visible()

        # The chip must sit immediately after the title text, not somewhere
        # else in the row - the title anchor must not consume the free space.
        title_box = title_text.bounding_box()
        chip_box = chip.bounding_box()
        gap = chip_box["x"] - (title_box["x"] + title_box["width"])

        self.assertGreaterEqual(gap, 0)
        self.assertLess(gap, 16)

    def test_unread_chip_should_not_render_for_read_bookmark(self):
        bookmark = self.setup_bookmark(title="Read bookmark", unread=False)

        self.open(reverse("linkding:bookmarks.index"))

        bookmark_item = self.locate_bookmark(bookmark.title)
        expect(bookmark_item.locator(".title .unread-chip")).not_to_be_visible()

    @skip("Fails in CI, needs investigation")
    def test_toggle_notes_should_show_hide_notes(self):
        bookmark = self.setup_bookmark(notes="Test notes")

        page = self.open(reverse("linkding:bookmarks.index"))

        notes = self.locate_bookmark(bookmark.title).locator(".notes")
        expect(notes).to_be_hidden()

        toggle_notes = page.locator("li button.toggle-notes")
        toggle_notes.click()
        expect(notes).to_be_visible()

        toggle_notes.click()
        expect(notes).to_be_hidden()
