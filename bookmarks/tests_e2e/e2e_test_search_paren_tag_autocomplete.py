import re

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class SearchParenTagAutocompleteE2ETestCase(LinkdingE2ETestCase):
    """Interaction lock-in: accept a parenthesized tag from search autocomplete."""

    def setUp(self) -> None:
        super().setUp()
        self.paren_tag = self.setup_tag(name="hello(world)")
        self.python_tag = self.setup_tag(name="python")
        self.paren_bookmark = self.setup_bookmark(
            title="Paren Tag Bookmark", tags=[self.paren_tag]
        )
        self.both_bookmark = self.setup_bookmark(
            title="Both Tags Bookmark", tags=[self.paren_tag, self.python_tag]
        )
        self.python_bookmark = self.setup_bookmark(
            title="Python Bookmark", tags=[self.python_tag]
        )

    def test_selecting_parenthesized_tag_from_autocomplete_filters_index(self):
        page = self.open(reverse("linkding:bookmarks.index"))
        search = page.get_by_placeholder("Search for words or #tags")
        search.click()
        search.fill("#hello")

        suggestion = page.locator("ld-search-autocomplete .menu.open a").filter(
            has_text="#hello(world)"
        )
        expect(suggestion).to_be_visible()
        suggestion.click()

        # completeSuggestion replaces the current word with "#hello(world) "
        expect(search).to_have_value("#hello(world) ")

        page.locator("form#search").evaluate("form => form.requestSubmit()")

        expect(page).to_have_url(
            re.compile(r".*[?&]q=.*hello.*world.*", re.IGNORECASE)
        )
        expect(self.locate_bookmark("Paren Tag Bookmark")).to_be_visible()
        expect(self.locate_bookmark("Both Tags Bookmark")).to_be_visible()
        expect(self.locate_bookmark("Python Bookmark")).to_have_count(0)
        expect(page.locator("p.selected-tags")).to_contain_text("hello(world)")
