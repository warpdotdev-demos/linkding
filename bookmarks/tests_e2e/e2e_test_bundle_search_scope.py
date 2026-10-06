from urllib.parse import parse_qs, urlsplit

from django.urls import reverse
from playwright.sync_api import expect

from bookmarks.tests_e2e.helpers import LinkdingE2ETestCase


class BundleSearchScopeE2ETest(LinkdingE2ETestCase):
    def setUp(self):
        super().setUp()
        self.bundle = self.setup_bundle(name="Reading", all_tags="reading")
        tag = self.setup_tag(name="reading")
        self.inside = self.setup_bookmark(
            title="Python inside", tags=[tag], unread=True
        )
        self.outside = self.setup_bookmark(title="Python outside", unread=True)
        self.setup_bookmark(title="Unrelated")
        self.setup_bookmark(title="Python foreign", user=self.setup_user(), unread=True)
        self.setup_bookmark(
            title="Python inside archived", tags=[tag], is_archived=True, unread=True
        )
        self.setup_bookmark(
            title="Python outside archived", is_archived=True, unread=True
        )

    def input(self):
        return self.page.locator("form#search input[name=q]")

    def params(self):
        return parse_qs(urlsplit(self.page.url).query)

    def assert_scope(self, bundled, archived=False):
        if bundled:
            expect(self.page.locator(".search-scope-name")).to_have_text("In: Reading")
            self.assertEqual(self.params()["bundle"], [str(self.bundle.id)])
            self.assertNotIn("return_bundle", self.params())
        else:
            label = "All archived bookmarks" if archived else "All bookmarks"
            expect(self.page.locator(".search-scope-row > span")).to_have_text(label)
            expect(
                self.page.get_by_role("link", name="Back to Reading")
            ).to_be_visible()
            self.assertEqual(self.params()["return_bundle"], [str(self.bundle.id)])
            self.assertNotIn("bundle", self.params())
        selected = self.page.locator(".bundle-menu .selected")
        expect(selected).to_have_text("Reading" if bundled else "All bookmarks")

    def test_chip_uses_unsent_query_and_back_keeps_current_query(self):
        self.open(reverse("linkding:bookmarks.index") + f"?bundle={self.bundle.id}")
        for archived in (False, True):
            route = reverse(
                "linkding:bookmarks.archived"
                if archived
                else "linkding:bookmarks.index"
            )
            self.page.goto(self.live_server_url + route + f"?bundle={self.bundle.id}")
            self.input().fill("outside")
            self.assertNotIn("q", self.params())
            name = (
                "Search all archived bookmarks" if archived else "Search all bookmarks"
            )
            self.page.get_by_role("button", name=name, exact=True).click()
            self.assert_scope(False, archived)
            self.assertEqual(self.params()["q"], ["outside"])
            expect(self.locate_bookmark("Python outside")).to_be_visible()
            expect(self.locate_bookmark("Python inside")).to_have_count(0)
            self.input().fill("Python")
            self.input().press("Enter")
            expect(self.locate_bookmark("Python inside")).to_be_visible()
            self.assert_scope(False, archived)
            self.input().fill("inside")
            expect(self.page.locator("ld-search-autocomplete .menu")).to_contain_text(
                "Python inside"
            )
            back = self.page.get_by_role("link", name="Back to Reading")
            self.assertTrue(
                back.evaluate("""element => {
                const box = element.getBoundingClientRect();
                return element.contains(document.elementFromPoint(
                    box.x + box.width / 2, box.y + box.height / 2));
            }""")
            )
            back.click()
            self.assert_scope(True, archived)
            self.assertEqual(self.params()["q"], ["inside"])
            expect(self.locate_bookmark("Python inside")).to_be_visible()
            expect(self.locate_bookmark("Python outside")).to_have_count(0)

    def test_scope_survives_clear_navigation_and_history(self):
        user = self.get_or_create_test_user()
        user.profile.items_per_page = 1
        user.profile.save()
        self.open(
            reverse("linkding:bookmarks.index") + f"?bundle={self.bundle.id}&q=Python"
        )
        self.page.get_by_role("button", name="Search all bookmarks", exact=True).click()
        self.assert_scope(False)
        self.input().fill("")
        self.input().press("Enter")
        self.page.wait_for_url(lambda url: "q" not in parse_qs(urlsplit(url).query))
        self.assert_scope(False)
        self.assertNotIn("q", self.params())
        self.page.locator(".pagination a").filter(has_text="2").click()
        self.page.wait_for_url(
            lambda url: parse_qs(urlsplit(url).query).get("page") == ["2"]
        )
        self.assert_scope(False)
        self.assertEqual(self.params()["page"], ["2"])
        self.page.locator(".unselected-tags a").filter(has_text="reading").click()
        expect(self.input()).to_have_value("#reading")
        self.assert_scope(False)
        self.assertNotIn("page", self.params())
        self.page.locator(".selected-tags a").click()
        expect(self.input()).to_have_value("")
        self.assert_scope(False)
        self.page.locator("a.view-action").first.click()
        expect(self.locate_details_modal()).to_be_visible()
        self.assert_scope(False)
        self.page.keyboard.press("Escape")
        expect(self.locate_details_modal()).not_to_be_visible()
        self.assert_scope(False)
        self.page.get_by_role("button", name="Search preferences").click()
        self.page.locator("select[name=sort]").select_option("title_asc")
        self.page.get_by_role("button", name="Apply", exact=True).click()
        self.page.wait_for_url(
            lambda url: parse_qs(urlsplit(url).query).get("sort") == ["title_asc"]
        )
        self.assert_scope(False)
        self.page.get_by_role("link", name="Back to Reading").click()
        self.assert_scope(True)
        self.page.go_back()
        self.assert_scope(False)
        self.page.go_forward()
        self.assert_scope(True)

    def test_autocomplete_follows_scope(self):
        user = self.get_or_create_test_user()
        user.profile.search_preferences = {"unread": "yes", "sort": "title_asc"}
        user.profile.save()
        self.setup_bookmark(title="Python read", tags=[self.setup_tag(name="extra")])
        self.open(reverse("linkding:bookmarks.index") + f"?bundle={self.bundle.id}")
        for archived in (False, True):
            route = reverse(
                "linkding:bookmarks.archived"
                if archived
                else "linkding:bookmarks.index"
            )
            self.page.goto(self.live_server_url + route + f"?bundle={self.bundle.id}")
            with self.page.expect_request(
                lambda request: "/api/bookmarks" in request.url
            ) as info:
                self.input().fill("Python")
            params = parse_qs(urlsplit(info.value.url).query)
            self.assertEqual(params["bundle"], [str(self.bundle.id)])
            self.assertEqual(params["unread"], ["yes"])
            self.assertEqual(params["sort"], ["title_asc"])
            self.assertEqual(params["limit"], ["5"])
            self.assertNotIn("return_bundle", params)
            self.assertEqual("/archived/" in info.value.url, archived)
            expect(self.page.locator("ld-search-autocomplete .menu")).to_contain_text(
                "Python inside"
            )
            expect(
                self.page.locator("ld-search-autocomplete .menu")
            ).not_to_contain_text("Python outside")
            name = (
                "Search all archived bookmarks" if archived else "Search all bookmarks"
            )
            self.page.get_by_role("button", name=name, exact=True).click()
            self.assert_scope(False, archived)
            with self.page.expect_request(
                lambda request: "/api/bookmarks" in request.url
            ) as info:
                self.input().press("ArrowDown")
            self.assertNotIn("bundle", parse_qs(urlsplit(info.value.url).query))
            expect(self.page.locator("ld-search-autocomplete .menu")).to_contain_text(
                "Python outside"
            )
            expect(
                self.page.locator("ld-search-autocomplete .menu")
            ).not_to_contain_text("Python foreign")
            expect(
                self.page.locator("ld-search-autocomplete .menu")
            ).not_to_contain_text("Python read")
            self.page.go_back()
            self.assert_scope(True, archived)
            expect(self.page.locator("ld-search-autocomplete .menu")).not_to_have_class(
                "menu open"
            )
        # Hold a real suggestion response, change the input, and deliver it late.
        pending = []
        self.page.route("**/api/bookmarks/**", lambda route: pending.append(route))
        self.input().fill("Python")
        self.page.wait_for_timeout(400)
        self.assertTrue(pending)
        self.input().fill("")
        for held in pending:
            held.fulfill(response=held.fetch())
        expect(self.page.locator("ld-search-autocomplete .menu")).not_to_contain_text(
            "Python inside"
        )

    def test_scope_control_without_sidebar(self):
        user = self.get_or_create_test_user()
        self.bundle.name = "Reading " + "long bundle name " * 10
        self.bundle.save()
        self.open(reverse("linkding:bookmarks.index") + f"?bundle={self.bundle.id}")
        for theme in ("light", "dark"):
            user.profile.theme = theme
            user.profile.hide_bundles = True
            user.profile.collapse_side_panel = True
            user.profile.save()
            self.page.set_viewport_size({"width": 375, "height": 812})
            self.page.goto(
                self.live_server_url
                + reverse("linkding:bookmarks.index")
                + f"?bundle={self.bundle.id}"
            )
            button = self.page.get_by_role(
                "button", name="Search all bookmarks", exact=True
            )
            expect(button).to_be_visible()
            expect(self.input()).to_be_visible()
            expect(
                self.page.get_by_role("button", name="Search preferences")
            ).to_be_visible()
            expect(
                self.page.get_by_role("button", name="Filters", exact=True)
            ).to_be_visible()
            expect(self.page.locator("#bundles-heading")).to_have_count(0)
            self.assertEqual(
                self.page.locator(".search-scope-name").get_attribute("title"),
                self.bundle.name,
            )
            self.input().focus()
            self.page.keyboard.press("Shift+Tab")
            expect(button).to_be_focused()
            self.assertIn("bundle", self.params())
            self.page.keyboard.press("Enter")
            expect(self.page.locator(".search-scope-row")).to_be_visible()
            back = self.page.get_by_role("link", name="Back to " + self.bundle.name)
            expect(back).to_be_visible()
            self.assertEqual(back.get_attribute("title"), "Back to " + self.bundle.name)
            self.assertLess(
                self.page.locator("main > .section-header").bounding_box()["height"],
                350,
            )
            expect(self.locate_bookmark("Python inside")).to_be_in_viewport()
            back.focus()
            self.page.keyboard.press("Enter")
            expect(button).to_be_visible()
            boxes = [
                locator.bounding_box()
                for locator in (
                    button,
                    self.input(),
                    self.page.get_by_role("button", name="Search preferences"),
                    self.page.get_by_role("button", name="Filters", exact=True),
                )
            ]
            for box in boxes:
                self.assertGreater(box["width"], 0)
                self.assertGreaterEqual(box["x"], 0)
                self.assertLessEqual(box["x"] + box["width"], 375)
            self.assertLessEqual(boxes[0]["x"] + boxes[0]["width"], boxes[1]["x"])
            self.assertLessEqual(boxes[1]["x"] + boxes[1]["width"], boxes[2]["x"])
