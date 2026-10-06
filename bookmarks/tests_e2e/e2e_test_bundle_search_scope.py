import re
from urllib.parse import parse_qs, urlencode, urlsplit

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class BundleSearchScopeE2ETestCase(LinkdingE2ETestCase):
    views = (
        ("linkding:bookmarks.index", False),
        ("linkding:bookmarks.archived", True),
    )

    def setup_scope(self, archived=False, name="Books"):
        tag = self.setup_tag(name=f"book{int(archived)}")
        inside = self.setup_bookmark(
            title="History inside", tags=[tag], is_archived=archived
        )
        outside = self.setup_bookmark(
            title="History outside", tags=[tag], is_archived=archived
        )
        bundle = self.setup_bundle(name=name, search="inside")
        return bundle, inside, outside, tag

    def search_input(self):
        return self.page.locator('#search input[name="q"]')

    def chip(self, bundle):
        return self.page.get_by_role(
            "button",
            name=f"Search all bookmarks, remove bundle filter: {bundle.name}",
            exact=True,
        )

    def assert_query(self, **expected):
        self.assertEqual(
            parse_qs(urlsplit(self.page.url).query),
            {key: [str(value)] for key, value in expected.items()},
        )

    def assert_global(self):
        query = parse_qs(urlsplit(self.page.url).query)
        self.assertNotIn("bundle", query)
        self.assertNotIn("search_scope", query)
        expect(self.page.locator(".search-scope-chip")).to_have_count(0)
        expect(self.page.locator(".bundle-menu-item.selected")).to_have_count(0)

    def visit_scope(self, route, bundle, **params):
        url = reverse(route) + "?" + urlencode({"bundle": bundle.id, **params})
        if self.page:
            self.page.goto(self.live_server_url + url)
        else:
            self.open(url)
        expect(self.chip(bundle)).to_be_visible()

    def test_enter_remains_bundle_scoped(self):
        for route, archived in self.views:
            with self.subTest(archived=archived):
                bundle, inside, outside, _ = self.setup_scope(archived)
                self.visit_scope(route, bundle)
                self.search_input().fill("History")
                self.search_input().press("Escape")
                self.search_input().press("Enter")
                expect(self.page).to_have_url(re.compile(r"q=History"))
                self.assert_query(q="History", bundle=bundle.id)
                expect(self.chip(bundle)).to_be_visible()
                expect(self.locate_bookmark(inside.title)).to_be_visible()
                expect(self.locate_bookmark(outside.title)).to_have_count(0)

    def test_chip_submits_live_query_globally(self):
        for route, archived in self.views:
            with self.subTest(archived=archived):
                bundle, inside, outside, tag = self.setup_scope(archived)
                self.visit_scope(route, bundle, q="old")
                self.search_input().fill(f"History #{tag.name[:-1]}")
                suggestion = self.page.locator("#search .menu").get_by_text(
                    f"#{tag.name}", exact=True
                )
                expect(suggestion).to_be_visible()
                suggestion.click()
                expect(self.search_input()).to_have_value(f"History #{tag.name} ")
                self.chip(bundle).click()
                expect(self.locate_bookmark(outside.title)).to_be_visible()
                self.assert_query(q=f"History #{tag.name} ")
                self.assertEqual(urlsplit(self.page.url).path, reverse(route))
                self.assert_global()
                expect(self.locate_bookmark(inside.title)).to_be_visible()
                expect(self.page.locator("main:focus")).to_be_visible()

    def test_scope_chip_keyboard_activation(self):
        bundle, inside, outside, tag = self.setup_scope()
        for key in ("Enter", "Space"):
            with self.subTest(key=key):
                self.visit_scope("linkding:bookmarks.index", bundle)
                self.assertEqual(
                    self.page.evaluate("document.activeElement.tagName"), "BODY"
                )
                # Existing arrows and selected-suggestion Enter complete a tag, not a search.
                self.search_input().fill(f"#{tag.name[:-1]}")
                expect(
                    self.page.locator("#search .menu").get_by_text(
                        f"#{tag.name}", exact=True
                    )
                ).to_be_visible()
                self.search_input().press("ArrowDown")
                expect(self.page.locator("#search .menu .selected")).to_be_visible()
                self.search_input().press("Enter")
                expect(self.search_input()).to_have_value(f"#{tag.name} ")
                self.assert_query(bundle=bundle.id)
                self.search_input().fill("History")
                expect(
                    self.page.locator("#search .menu").get_by_text(
                        inside.title, exact=True
                    )
                ).to_be_visible()
                self.search_input().press("Escape")
                expect(self.page.locator("#search .menu")).to_be_hidden()
                # Tab from the input back to the preceding chip.
                self.search_input().press("Shift+Tab")
                expect(self.chip(bundle)).to_be_focused()
                self.assertNotEqual(
                    self.chip(bundle).evaluate(
                        "el => getComputedStyle(el).outlineStyle"
                    ),
                    "none",
                )
                self.chip(bundle).press(key)
                expect(self.locate_bookmark(outside.title)).to_be_visible()
                self.assert_query(q="History")
                self.assert_global()
        # Selected bookmark suggestions still open the bookmark without submitting.
        self.visit_scope("linkding:bookmarks.index", bundle)
        self.search_input().fill("History inside")
        expect(
            self.page.locator("#search .menu").get_by_text(inside.title, exact=True)
        ).to_be_visible()
        self.search_input().press("ArrowDown")
        with self.page.expect_popup() as popup:
            self.search_input().press("Tab")
        popup.value.close()
        self.assert_query(bundle=bundle.id)

    def test_suggestions_follow_bundle_scope(self):
        for route, archived in self.views:
            with self.subTest(archived=archived):
                bundle, inside, outside, _ = self.setup_scope(archived)
                endpoint = "/api/bookmarks/archived/" if archived else "/api/bookmarks/"
                self.visit_scope(
                    route, bundle, unread="no", shared="no", user=self.user.username
                )
                with self.page.expect_response(
                    lambda response, endpoint=endpoint: urlsplit(response.url).path
                    == endpoint
                ) as response:
                    self.search_input().fill("History")
                params = parse_qs(urlsplit(response.value.url).query)
                self.assertEqual(params["bundle"], [str(bundle.id)])
                self.assertEqual(params["unread"], ["no"])
                self.assertEqual(params["shared"], ["no"])
                self.assertEqual(params["user"], [self.user.username])
                self.assertEqual(
                    [item["id"] for item in response.value.json()["results"]],
                    [inside.id],
                )
                expect(
                    self.page.locator("#search .menu").get_by_text(
                        inside.title, exact=True
                    )
                ).to_be_visible()
                expect(
                    self.page.locator("#search .menu").get_by_text(
                        outside.title, exact=True
                    )
                ).to_have_count(0)
                self.chip(bundle).click()
                expect(self.locate_bookmark(outside.title)).to_be_visible()
                self.assert_global()
                self.search_input().fill("")
                with self.page.expect_response(
                    lambda response, endpoint=endpoint: urlsplit(response.url).path
                    == endpoint
                ) as response:
                    self.search_input().fill("History")
                params = parse_qs(urlsplit(response.value.url).query)
                self.assertNotIn("bundle", params)
                self.assertEqual(params["unread"], ["no"])
                self.assertEqual(params["shared"], ["no"])
                self.assertEqual(params["user"], [self.user.username])
                self.assertCountEqual(
                    [item["id"] for item in response.value.json()["results"]],
                    [inside.id, outside.id],
                )
                expect(
                    self.page.locator("#search .menu").get_by_text(
                        outside.title, exact=True
                    )
                ).to_be_visible()

    def test_global_navigation_and_back(self):
        profile = self.user.profile
        profile.items_per_page = 10
        profile.save()
        for route, archived in self.views:
            with self.subTest(archived=archived):
                bundle, _, _, tag = self.setup_scope(archived)
                bookmarks = self.setup_numbered_bookmarks(
                    10, prefix="History extra", archived=archived
                )
                for bookmark in bookmarks:
                    bookmark.tags.add(tag)
                self.visit_scope(route, bundle)
                self.search_input().fill("History")
                self.chip(bundle).click()
                expect(self.page.locator(".search-scope-chip")).to_have_count(0)
                self.assert_global()
                self.page.go_back()
                expect(self.chip(bundle)).to_be_visible()
                self.assert_query(bundle=bundle.id)
                expect(self.page.locator(".search-scope-chip")).to_have_count(1)
                self.page.go_forward()
                expect(self.page.locator(".search-scope-chip")).to_have_count(0)
                self.assert_global()
                self.page.locator(".bookmark-list .tags a").first.click()
                expect(self.search_input()).to_have_value(f"History #{tag.name}")
                self.assert_global()
                self.page.locator('.pagination a[href*="page=2"]').first.click()
                expect(self.page).to_have_url(re.compile("page=2"))
                self.assert_global()
                self.page.locator(".side-panel .selected-tags a").click()
                expect(self.search_input()).to_have_value("History")
                self.assertNotIn("page", parse_qs(urlsplit(self.page.url).query))
                self.assert_global()
                self.page.get_by_role("button", name="Search preferences").click()
                self.page.locator(
                    '#search_preferences select[name="sort"]'
                ).select_option("title_asc")
                self.page.get_by_role("button", name="Apply", exact=True).click()
                expect(self.page).to_have_url(re.compile("sort=title_asc"))
                self.assert_global()
                self.page.locator(
                    f'.bookmark-list li[data-bookmark-id="{bookmarks[0].id}"] a.view-action'
                ).click()
                modal = self.locate_details_modal()
                expect(modal).to_be_visible()
                self.assertNotIn(
                    "bundle",
                    parse_qs(urlsplit(modal.get_attribute("data-close-url")).query),
                )
                modal.get_by_role("link", name="Edit", exact=True).click()
                expect(self.page.get_by_role("link", name="Cancel")).to_be_visible()
                self.page.get_by_role("link", name="Cancel").click()
                expect(self.locate_details_modal()).to_be_visible()
                self.locate_details_modal().locator("button.close").click()
                expect(self.locate_details_modal()).to_be_hidden()
                self.assert_global()
                self.page.locator(
                    f'.side-panel .bundle-menu a[href="?bundle={bundle.id}"]'
                ).click()
                expect(self.chip(bundle)).to_be_visible()
                self.assert_query(bundle=bundle.id)
                self.assertEqual(urlsplit(self.page.url).path, reverse(route))
                expect(self.page.locator(".search-scope-chip")).to_have_count(1)

    def test_scope_chip_layout(self):
        name = ('Books <&" ' + "very long name " * 20)[:256]
        bundle, _, _, _ = self.setup_scope(name=name)
        for theme in ("light", "dark"):
            for settings in ({}, {"hide_bundles": True}, {"collapse_side_panel": True}):
                profile = self.user.profile
                profile.theme = theme
                profile.hide_bundles = settings.get("hide_bundles", False)
                profile.collapse_side_panel = settings.get("collapse_side_panel", False)
                profile.save()
                for width in (1280, 375):
                    with self.subTest(theme=theme, settings=settings, width=width):
                        self.visit_scope("linkding:bookmarks.index", bundle)
                        self.page.set_viewport_size({"width": width, "height": 812})
                        chip = self.chip(bundle)
                        expect(chip).to_be_visible()
                        expect(chip).to_have_attribute("title", name)
                        expect(chip.locator(".bundle-name")).to_have_text(name)
                        self.assertFalse(
                            chip.locator(".bundle-name").evaluate(
                                "el => el.children.length > 0"
                            )
                        )
                        self.assertLessEqual(
                            self.page.evaluate("document.documentElement.scrollWidth"),
                            width,
                        )
                        box = chip.bounding_box()
                        self.assertGreaterEqual(box["width"], 24)
                        self.assertGreaterEqual(box["height"], 24)
                        shell = self.page.locator(
                            "#search .form-autocomplete-input"
                        ).bounding_box()
                        self.assertLessEqual(box["width"], shell["width"] * 0.45 + 1)
                        self.assertTrue(
                            chip.locator(".bundle-name").evaluate(
                                "el => el.scrollWidth > el.clientWidth"
                            )
                        )
                        expect(self.search_input()).to_be_visible()
                        self.assertGreater(
                            self.search_input().bounding_box()["width"], 50
                        )
                        self.search_input().fill("editable")
                        expect(self.search_input()).to_have_value("editable")
                        self.page.get_by_role(
                            "button", name="Search preferences"
                        ).click()
                        expect(
                            self.page.get_by_role("button", name="Apply", exact=True)
                        ).to_be_visible()
                        self.page.keyboard.press("Escape")
                        if width == 375 or profile.collapse_side_panel:
                            self.page.locator(".main").get_by_role(
                                "button", name="Filters", exact=True
                            ).click()
                            expect(
                                self.page.locator("ld-filter-drawer")
                            ).to_be_visible()
                            self.page.locator("ld-filter-drawer button.close").click()
