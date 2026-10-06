from urllib.parse import parse_qs, urlsplit

from django.urls import reverse


class SearchScopeViewTestMixin:
    """Run the identical navigation contract on active and archived routes."""

    scope_mode = ""

    def scope_url(self):
        route = "archived" if self.scope_mode else "index"
        return reverse(f"linkding:bookmarks.{route}")

    def test_bundle_global_search_navigation(self):
        archived = bool(self.scope_mode)
        tag = self.setup_tag(name="reading")
        focus_tag = self.setup_tag(name="focus")
        blocked_tag = self.setup_tag(name="blocked")
        inside = self.setup_bookmark(
            title="inside python",
            tags=[tag, focus_tag],
            is_archived=archived,
            unread=True,
        )
        outside = self.setup_bookmark(
            title="outside python",
            tags=[tag, blocked_tag],
            is_archived=archived,
            shared=True,
        )
        excluded = [
            self.setup_bookmark(title="unrelated", is_archived=archived),
            self.setup_bookmark(title="python opposite", is_archived=not archived),
            self.setup_bookmark(
                title="python other", is_archived=archived, user=self.setup_user()
            ),
        ]
        bundle = self.setup_bundle(
            search="inside",
            any_tags="focus",
            all_tags="reading",
            excluded_tags="blocked",
            filter_unread="yes",
            filter_shared="no",
        )
        url = self.scope_url()
        for legacy in (False, True):
            self.user.profile.legacy_search = legacy
            self.user.profile.save()
            response = self.client.get(url, {"bundle": bundle.id, "q": "python"})
            self.assertVisibleBookmarks(response, [inside])
            control = self.make_soup(response.content.decode()).select_one(
                "ld-search-autocomplete"
            )
            response = self.client.get(control["unbundle-url"])
            self.assertVisibleBookmarks(response, [inside, outside])
            self.assertInvisibleBookmarks(response, excluded)
            for query, expected in (
                ("outside", [outside]),
                ("", [inside, outside, excluded[0]]),
            ):
                response = self.client.get(
                    url, {"return_bundle": bundle.id, "q": query}
                )
                self.assertVisibleBookmarks(response, expected)
                control = self.make_soup(response.content.decode()).select_one(
                    "ld-search-autocomplete"
                )
                self.assertEqual(control["return-name"], bundle.name)
            response = self.client.get(url, {"return_bundle": bundle.id, "q": "python"})
            soup = self.make_soup(response.content.decode())
            tag_url = next(
                link["href"]
                for link in soup.select("a[data-is-tag-item]")
                if link.get_text(strip=True).lower() == "reading"
            )
            self.assertEqual(
                parse_qs(urlsplit(tag_url).query)["return_bundle"], [str(bundle.id)]
            )
            self.assertNotIn("bundle", parse_qs(urlsplit(tag_url).query))
            response = self.client.get(url + tag_url)
            self.assertVisibleBookmarks(response, [inside, outside])
            item = response.context["bookmark_list"].items[0]
            details_url = item.details_url
            response = self.client.get(details_url)
            details = response.context["details"]
            for target in (
                details.close_url,
                details.edit_return_url,
                details.action_url,
            ):
                params = parse_qs(urlsplit(target).query)
                self.assertEqual(params["return_bundle"], [str(bundle.id)])
                self.assertNotIn("bundle", params)
            response = self.client.post(details.delete_url, {})
            self.assertEqual(
                parse_qs(urlsplit(response.url).query)["return_bundle"],
                [str(bundle.id)],
            )
        self.user.profile.items_per_page = 1
        self.user.profile.save()
        response = self.client.get(url, {"q": "python", "return_bundle": bundle.id})
        soup = self.make_soup(response.content.decode())
        page_links = soup.select('.pagination a[href]:not([href="#"])')
        self.assertTrue(page_links)
        for link in page_links:
            params = parse_qs(urlsplit(link["href"]).query)
            self.assertEqual(params["return_bundle"], [str(bundle.id)])
            self.assertNotIn("bundle", params)

    def test_scope_preferences_preserve_origin_only_in_url(self):
        bundle = self.setup_bundle()
        url = self.scope_url()
        self.user.profile.search_preferences = {"unread": "yes", "shared": "yes"}
        self.user.profile.save()
        for action in ("apply", "save"):
            response = self.client.post(
                url,
                {
                    action: "",
                    "q": "python",
                    "return_bundle": bundle.id,
                    "sort": "title_asc",
                    "unread": "off",
                    "shared": "off",
                    "modified_since": "2024-01-01",
                    "added_since": "2023-01-01",
                    "page": 3,
                    "details": 5,
                },
            )
            self.assertEqual(response.status_code, 302)
            params = parse_qs(urlsplit(response.url).query)
            self.assertEqual(params["return_bundle"], [str(bundle.id)])
            self.assertNotIn("page", params)
            self.assertNotIn("details", params)
            self.assertNotIn("bundle", params)
            self.assertEqual(params["modified_since"], ["2024-01-01"])
            page = self.client.get(response.url)
            self.assertEqual(page.context["bookmark_list"].search.unread, "off")
            self.assertEqual(page.context["bookmark_list"].search.shared, "off")
        self.user.profile.refresh_from_db()
        self.assertEqual(
            self.user.profile.search_preferences,
            {"sort": "title_asc", "shared": "off", "unread": "off"},
        )
        for value in (
            "bad",
            "-1",
            str(2**63),
            self.setup_bundle(user=self.setup_user()).id,
        ):
            response = self.client.post(url, {"return_bundle": value, "apply": ""})
            self.assertNotIn("return_bundle", response.url)

    def test_all_bookmarks_bundle_entry(self):
        url = self.scope_url()
        response = self.client.get(url)
        soup = self.make_soup(response.content.decode())
        entries = soup.select(".bundle-menu > li")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get_text(strip=True), "All bookmarks")
        self.assertIn("selected", entries[0]["class"])
        bundle = self.setup_bundle(name="Work")
        foreign = self.setup_bundle(user=self.setup_user(), name="Private")
        response = self.client.get(
            url,
            {
                "bundle": bundle.id,
                "q": "python",
                "unread": "off",
                "shared": "no",
                "sort": "title_asc",
                "page": 2,
                "details": 123,
            },
        )
        soup = self.make_soup(response.content.decode())
        entries = soup.select(".bundle-menu > li")
        self.assertEqual(
            [item.get_text(strip=True) for item in entries],
            ["All bookmarks", bundle.name],
        )
        self.assertNotIn("selected", entries[0]["class"])
        self.assertIn("selected", entries[1]["class"])
        target = entries[0].select_one("a")["href"]
        self.assertEqual(urlsplit(target).path, url)
        self.assertEqual(
            parse_qs(urlsplit(target).query),
            {
                "q": ["python"],
                "unread": ["off"],
                "shared": ["no"],
                "sort": ["title_asc"],
                "return_bundle": [str(bundle.id)],
            },
        )
        response = self.client.get(url, {"bundle": foreign.id})
        self.assertIn(
            "selected",
            self.make_soup(response.content.decode()).select_one(".bundle-menu > li")[
                "class"
            ],
        )
        self.assertNotContains(response, foreign.name)
