from urllib.parse import parse_qs, urlencode, urlsplit

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class BundleSearchE2ETestCase(LinkdingE2ETestCase):
    def setUp(self):
        super().setUp()
        self.tag = self.setup_tag(name="topic")
        self.inside = self.setup_bookmark(title="Bundle guide", tags=[self.tag])
        self.outside = self.setup_bookmark(title="Outside guide", tags=[self.tag])
        self.setup_bookmark(title="Archived guide", is_archived=True)
        self.setup_bookmark(title="Other guide", user=self.setup_user())
        self.bundle = self.setup_bundle(name="Reading", search="Bundle")
        self.index_url = reverse("linkding:bookmarks.index")

    def scoped_url(self, **params):
        return self.index_url + "?" + urlencode({"bundle": self.bundle.id, **params})

    def search_input(self):
        return self.page.locator('#search input[name="q"]')

    def broaden_button(self):
        return self.page.get_by_role("button", name="Search all bookmarks", exact=True)

    def assert_params(self, expected):
        expected = {key: [str(value)] for key, value in expected.items()}
        self.page.wait_for_url(
            lambda url: parse_qs(urlsplit(url).query, keep_blank_values=True)
            == expected
        )
        self.assertEqual(
            parse_qs(urlsplit(self.page.url).query, keep_blank_values=True),
            expected,
        )

    def test_live_query_and_only_approved_filters_are_carried(self):
        profile = self.user.profile
        profile.search_preferences = {"sort": "title_desc", "unread": "no"}
        profile.save()
        query = '(guide OR "C++ & notes") #topic'
        self.setup_bookmark(title="C++ & notes", tags=[self.tag])
        filters = {
            "sort": "title_asc",
            "shared": "no",
            "unread": "off",
            "added_since": "2020-01-01T00:00:00Z",
            "modified_since": "2020-01-01T00:00:00Z",
        }
        self.open(
            self.scoped_url(
                q="no-match",
                page=2,
                details=999999,
                user="someone",
                return_url="//example.com",
                archive="1",
                unknown="discard",
                **filters,
            )
        )
        self.search_input().fill(query)
        expect(self.page.locator("ld-search-autocomplete .menu.open")).to_be_visible()
        self.broaden_button().click()
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "All bookmarks (not archived)"
        )
        self.assert_params({"q": query, **filters})
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        expect(self.locate_bookmark("C++ & notes")).to_be_visible()
        expect(self.locate_bookmark("Archived guide")).to_have_count(0)
        expect(self.locate_bookmark("Other guide")).to_have_count(0)
        expect(self.page.locator(".bundle-menu-item.selected")).to_have_count(0)
        profile.refresh_from_db()
        self.assertEqual(
            profile.search_preferences, {"sort": "title_desc", "unread": "no"}
        )

    def test_scope_history_repeat_reload_and_sidebar(self):
        self.open(self.scoped_url())
        self.search_input().fill("Outside")
        self.search_input().press("Escape")
        self.search_input().press("Enter")
        expect(self.broaden_button()).to_be_visible()
        expect(self.locate_bookmark(self.outside.title)).to_have_count(0)
        self.assert_params({"q": "Outside", "bundle": self.bundle.id})
        scoped_url = self.page.url
        self.broaden_button().click()
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        broadened_url = self.page.url

        self.page.go_back()
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "In bundle: Reading"
        )
        expect(self.locate_bookmark(self.outside.title)).to_have_count(0)
        self.assertEqual(self.page.url, scoped_url)
        self.page.go_forward()
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        self.assertEqual(self.page.url, broadened_url)
        self.page.reload()
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "All bookmarks (not archived)"
        )
        self.page.goto(broadened_url)
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        self.search_input().fill("guide")
        self.search_input().press("Escape")
        self.search_input().press("Enter")
        self.assert_params({"q": "guide"})
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "All bookmarks (not archived)"
        )
        self.search_input().fill("")
        self.search_input().press("Enter")
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        self.assert_params({"q": ""})
        self.page.locator(".bundle-menu").get_by_role("link", name="Reading").click()
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "In bundle: Reading"
        )
        expect(self.search_input()).to_have_value("")
        expect(self.locate_bookmark(self.outside.title)).to_have_count(0)
        self.assert_params({"bundle": self.bundle.id})

    def test_empty_and_invalid_queries_can_leave_the_bundle(self):
        self.open(self.scoped_url())
        self.search_input().press("Enter")
        expect(self.broaden_button()).to_be_visible()
        self.assert_params({"q": "", "bundle": self.bundle.id})
        self.search_input().fill("(")
        self.search_input().press("Escape")
        self.search_input().press("Enter")
        expect(self.broaden_button()).to_be_visible()
        self.broaden_button().click()
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "All bookmarks (not archived)"
        )
        self.assert_params({"q": "("})
        expect(self.page.locator(".bookmark-list > li")).to_have_count(0)
        self.page.goto(self.live_server_url + self.scoped_url(q="no-match"))
        self.search_input().fill("")
        self.broaden_button().click()
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        self.assert_params({"q": ""})

    def test_scope_and_filters_survive_pagination_tags_details_and_actions(self):
        self.setup_bookmark(title="Bundle second", tags=[self.tag])
        profile = self.user.profile
        profile.items_per_page = 1
        profile.save()
        self.open(self.scoped_url(q="guide OR second", sort="title_asc"))
        for scoped in [True, False]:
            with self.subTest(scoped=scoped):
                filters = {
                    "sort": "title_asc",
                    **({"bundle": self.bundle.id} if scoped else {}),
                }
                self.page.locator(".pagination").get_by_role(
                    "link", name="2", exact=True
                ).click()
                self.assert_params({"q": "guide OR second", "page": 2, **filters})
                expect(self.page.locator(".bookmark-list > li")).to_have_count(1)
                self.page.locator(".bookmark-list .tags a").first.click()
                self.assert_params({"q": "(guide OR second) #topic", **filters})
                expect(self.search_input()).to_have_value("(guide OR second) #topic")
                item = self.page.locator(".bookmark-list > li").first
                bookmark_id = item.get_attribute("data-bookmark-id")
                item.get_by_text("View", exact=True).click()
                modal = self.locate_details_modal()
                expect(modal).to_be_visible()
                self.assert_params(
                    {"q": "(guide OR second) #topic", "details": bookmark_id, **filters}
                )
                modal.locator("button.close").click()
                expect(modal).to_be_hidden()
                self.assert_params({"q": "(guide OR second) #topic", **filters})
                self.page.locator(".pagination").get_by_role(
                    "link", name="2", exact=True
                ).click()
                self.assert_params(
                    {"q": "(guide OR second) #topic", "page": 2, **filters}
                )
                self.search_input().fill("guide OR second")
                self.search_input().press("Escape")
                self.search_input().press("Enter")
                self.assert_params({"q": "guide OR second", **filters})
                item = self.page.locator(".bookmark-list > li").first
                bookmark_id = item.get_attribute("data-bookmark-id")
                item.get_by_role("button", name="Archive", exact=True).click()
                expect(
                    self.page.locator(
                        f'.bookmark-list > li[data-bookmark-id="{bookmark_id}"]'
                    )
                ).to_have_count(0)
                self.assert_params({"q": "guide OR second", **filters})
                if scoped:
                    self.broaden_button().click()
                    self.assert_params({"q": "guide OR second", "sort": "title_asc"})
                    expect(self.broaden_button()).to_have_count(0)

    def test_keyboard_and_mobile_with_hidden_sidebar(self):
        profile = self.user.profile
        profile.collapse_side_panel = True
        profile.save()
        self.open(self.scoped_url(q="Outside"))
        self.page.set_viewport_size({"width": 375, "height": 812})
        expect(self.page.locator(".search-scope-label")).to_have_text(
            "In bundle: Reading"
        )
        expect(self.broaden_button()).to_be_visible()
        expect(self.page.locator("ld-filter-drawer")).to_have_count(0)
        self.assertTrue(
            self.page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
        )
        self.search_input().focus()
        self.search_input().press("Escape")
        self.search_input().press("Tab")
        self.page.keyboard.press("Tab")
        expect(self.broaden_button()).to_be_focused()
        self.assertNotEqual(
            self.broaden_button().evaluate("el => getComputedStyle(el).outlineStyle"),
            "none",
        )
        self.page.keyboard.press("Space")
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()
        self.page.go_back()
        expect(self.broaden_button()).to_be_visible()
        self.broaden_button().focus()
        self.page.keyboard.press("Enter")
        expect(self.locate_bookmark(self.outside.title)).to_be_visible()

    def test_outside_suggestions_and_tag_and_recent_completion_keep_scope(self):
        self.open(self.scoped_url(q="guide"))
        self.context.route(
            "https://example.com/**", lambda route: route.fulfill(body="Bookmark")
        )
        self.search_input().fill("Outside")
        suggestion = self.page.locator("ld-search-autocomplete .menu").get_by_text(
            self.outside.title, exact=True
        )
        expect(suggestion).to_be_visible()
        scoped_url = self.page.url
        with self.page.expect_popup() as popup_info:
            suggestion.click()
        popup = popup_info.value
        popup.wait_for_load_state()
        self.assertEqual(popup.url, self.outside.url)
        popup.close()
        self.assertEqual(self.page.url, scoped_url)
        self.search_input().fill("#top")
        self.search_input().press("ArrowDown")
        expect(
            self.page.locator("ld-search-autocomplete .menu").get_by_text(
                "#topic", exact=True
            )
        ).to_be_visible()
        self.search_input().press("ArrowDown")
        self.search_input().press("Enter")
        expect(self.search_input()).to_have_value("#topic ")
        self.assertEqual(self.page.url, scoped_url)
        self.search_input().fill("gui")
        self.search_input().press("Escape")
        self.search_input().press("ArrowDown")
        expect(
            self.page.locator("ld-search-autocomplete .menu").get_by_text(
                "guide", exact=True
            )
        ).to_be_visible()
        self.search_input().press("ArrowDown")
        self.search_input().press("Enter")
        expect(self.search_input()).to_have_value("guide")
        self.assertEqual(self.page.url, scoped_url)
