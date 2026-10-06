from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.urls import reverse
from django.utils import timezone

from bookmarks.models import BookmarkBundle


class BundleSearchScopeTestMixin:
    """Run the same scope contract against both owned bookmark views."""

    def scope_bookmark(self, **kwargs):
        return self.setup_bookmark(is_archived=self.scope_archived, **kwargs)

    def global_search(self, bundle=None, **params):
        params = {"search_scope": "all", **params}
        if bundle:
            params["bundle"] = bundle.id
        response = self.client.get(reverse(self.scope_view), params, follow=True)
        self.assertEqual(len(response.redirect_chain), 1)
        url, status = response.redirect_chain[0]
        self.assertEqual(status, 302)
        self.assertEqual(urlsplit(url).path, reverse(self.scope_view))
        query = parse_qs(urlsplit(url).query)
        for key in ("bundle", "search_scope", "page", "details"):
            self.assertNotIn(key, query)
        self.assertEqual(response.status_code, 200)
        return response, query

    def test_scope_control_attributes(self):
        bundle = self.setup_bundle(name='Books <&" stories')
        response = self.client.get(reverse(self.scope_view), {"bundle": bundle.id})
        soup = self.make_soup(response.content.decode())
        form = soup.select_one("form#search")
        component = form.select_one("ld-search-autocomplete")
        self.assertEqual(component["bundle"], str(bundle.id))
        self.assertEqual(component["bundle-name"], bundle.name)
        self.assertEqual(
            form.select_one('input[name="bundle"]')["value"], str(bundle.id)
        )
        self.assertIsNone(soup.select_one('input[name="search_scope"]'))
        children = list(form.find_all(recursive=False))
        self.assertLess(
            children.index(form.select_one('input[type="submit"]')),
            children.index(component),
        )

    def test_scope_control_visibility(self):
        bundle = self.setup_bundle()
        foreign_bundle = self.setup_bundle(user=self.setup_user())
        for profile_settings in (
            {},
            {"hide_bundles": True},
            {"collapse_side_panel": True},
        ):
            profile = self.user.profile
            profile.hide_bundles = profile_settings.get("hide_bundles", False)
            profile.collapse_side_panel = profile_settings.get(
                "collapse_side_panel", False
            )
            profile.save()
            for bundle_id in (
                None,
                bundle.id,
                bundle.id + foreign_bundle.id + 100,
                foreign_bundle.id,
            ):
                with self.subTest(settings=profile_settings, bundle=bundle_id):
                    params = {"bundle": bundle_id} if bundle_id else {}
                    response = self.client.get(reverse(self.scope_view), params)
                    component = self.make_soup(response.content.decode()).select_one(
                        "ld-search-autocomplete"
                    )
                    self.assertEqual(
                        "bundle" in component.attrs, bundle_id == bundle.id
                    )
                    self.assertEqual(
                        "bundle-name" in component.attrs, bundle_id == bundle.id
                    )

    def test_search_all_canonical_redirect(self):
        inside = self.scope_bookmark(title="History inside")
        outside = self.scope_bookmark(title="History outside")
        invisible = [
            self.scope_bookmark(title="History foreign", user=self.setup_user()),
            self.setup_bookmark(
                title="History opposite view", is_archived=not self.scope_archived
            ),
        ]
        bundle = self.setup_bundle(search="inside")
        scoped = self.client.get(
            reverse(self.scope_view), {"bundle": bundle.id, "q": "History"}
        )
        self.assertVisibleBookmarks(scoped, [inside])
        response, query = self.global_search(
            bundle, q="History", page=3, details=inside.id, unknown="discard"
        )
        self.assertEqual(query, {"q": ["History"]})
        self.assertVisibleBookmarks(response, [inside, outside])
        self.assertInvisibleBookmarks(response, invisible)
        soup = self.make_soup(response.content.decode())
        self.assertIsNone(soup.select_one(".bundle-menu-item.selected"))
        self.assertIsNone(soup.select_one("ld-search-autocomplete[bundle]"))

    def test_search_all_preserves_independent_filters(self):
        profile = self.user.profile
        profile.search_preferences = {
            "sort": "title_desc",
            "unread": "yes",
            "shared": "yes",
        }
        profile.save()
        tag = self.setup_tag(name="book")
        now = timezone.now()
        common = {
            "unread": False,
            "shared": False,
            "tags": [tag],
            "added": now,
            "modified": now,
        }
        first = self.scope_bookmark(title="History A", **common)
        second = self.scope_bookmark(title="History Z", **common)
        invisible = [
            self.scope_bookmark(
                title="History read filter", **{**common, "unread": True}
            ),
            self.scope_bookmark(
                title="History shared filter", **{**common, "shared": True}
            ),
            self.scope_bookmark(title="History wrong tag", **{**common, "tags": []}),
            self.scope_bookmark(
                title="History old added",
                **{**common, "added": now - timedelta(days=3)},
            ),
            self.scope_bookmark(
                title="History old modified",
                **{**common, "modified": now - timedelta(days=3)},
            ),
        ]
        bundle = self.setup_bundle(search="missing")
        params = {
            "q": "History #book",
            "sort": "title_asc",
            "unread": "no",
            "shared": "no",
            "added_since": (now - timedelta(days=1)).isoformat(),
            "modified_since": (now - timedelta(days=1)).isoformat(),
            "user": self.user.username,
        }
        response, query = self.global_search(bundle, **params)
        self.assertEqual(query, {key: [value] for key, value in params.items()})
        self.assertVisibleBookmarks(response, [first, second])
        self.assertInvisibleBookmarks(response, invisible)
        self.assertEqual(
            [item.id for item in response.context["bookmark_list"].items],
            [first.id, second.id],
        )
        search = response.context["bookmark_list"].search
        for key, value in params.items():
            self.assertEqual(getattr(search, key), value)
        # Saved preferences still apply when omitted; values equal to those defaults normalize away.
        preferred = self.scope_bookmark(
            title="History preferred", unread=True, shared=True
        )
        response, query = self.global_search(
            bundle, sort="title_desc", unread="yes", shared="yes"
        )
        self.assertEqual(query, {})
        self.assertVisibleBookmarks(response, [preferred])
        self.assertEqual(
            response.context["bookmark_list"].search.preferences_dict,
            profile.search_preferences,
        )
        profile.refresh_from_db()
        self.assertEqual(
            profile.search_preferences,
            {"sort": "title_desc", "unread": "yes", "shared": "yes"},
        )

    def test_search_all_removes_bundle_rules(self):
        keep = self.setup_tag(name="keep")
        any_tag = self.setup_tag(name="any")
        all_tag = self.setup_tag(name="all")
        excluded = self.setup_tag(name="excluded")
        inside = self.scope_bookmark(
            title="History inside",
            tags=[keep, any_tag, all_tag],
            unread=True,
            shared=True,
        )
        outside = self.scope_bookmark(title="History outside", tags=[keep, excluded])
        other = self.scope_bookmark(title="History no independent tag")
        rules = [
            {"search": "inside"},
            {"any_tags": "any"},
            {"all_tags": "all"},
            {"excluded_tags": "excluded"},
            {"filter_unread": BookmarkBundle.FILTER_STATE_YES},
            {"filter_shared": BookmarkBundle.FILTER_STATE_YES},
        ]
        for rule in rules:
            with self.subTest(rule=rule):
                bundle = self.setup_bundle(**rule)
                scoped = self.client.get(
                    reverse(self.scope_view),
                    {"bundle": bundle.id, "q": "History #keep"},
                )
                self.assertVisibleBookmarks(scoped, [inside])
                response, query = self.global_search(bundle, q="History #keep")
                self.assertEqual(query, {"q": ["History #keep"]})
                self.assertVisibleBookmarks(response, [inside, outside])
                self.assertInvisibleBookmarks(response, [other])

    def test_search_all_empty_and_invalid_query(self):
        bookmark = self.scope_bookmark(
            title="History", tags=[self.setup_tag(name="book")]
        )
        bundle = self.setup_bundle(search="missing")
        response, query = self.global_search(bundle, q="")
        self.assertEqual(query, {})
        self.assertVisibleBookmarks(response, [bookmark])
        response, query = self.global_search(bundle, q="", unread="yes")
        self.assertEqual(query, {"unread": ["yes"]})
        self.assertContains(response, "You have no bookmarks yet")
        response, query = self.global_search(bundle, q="(")
        self.assertEqual(query, {"q": ["("]})
        self.assertContains(response, "Invalid search query")
        profile = self.user.profile
        profile.legacy_search = True
        profile.save()
        response, query = self.global_search(bundle, q="History #book")
        self.assertEqual(query, {"q": ["History #book"]})
        self.assertVisibleBookmarks(response, [bookmark])

    def assert_global_url(self, url):
        params = parse_qs(urlsplit(url).query)
        self.assertNotIn("bundle", params)
        self.assertNotIn("search_scope", params)
        if "return_url" in params:
            self.assert_global_url(params["return_url"][0])
        return params

    def test_search_all_navigation_stays_global(self):
        tag = self.setup_tag(name="book")
        bookmarks = self.setup_numbered_bookmarks(
            11, prefix="History", archived=self.scope_archived
        )
        for bookmark in bookmarks:
            bookmark.tags.add(tag)
        profile = self.user.profile
        profile.items_per_page = 10
        profile.save()
        bundle = self.setup_bundle(search="missing")
        response, query = self.global_search(bundle, q="History")
        self.assertEqual(query, {"q": ["History"]})
        soup = self.make_soup(response.content.decode())
        tag_link = soup.select_one(".tags a")
        params = self.assert_global_url(tag_link["href"])
        self.assertNotIn("page", params)
        self.assertEqual(params["q"], ["History #book"])
        self.assert_global_url(soup.select_one("form.bookmark-actions")["action"])
        self.assert_global_url(soup.select_one("a.view-action")["href"])
        edit_link = next(
            link for link in soup.select(".actions a") if link.text.strip() == "Edit"
        )
        self.assert_global_url(edit_link["href"])
        page_link = next(
            link
            for link in soup.select(".pagination a")
            if parse_qs(urlsplit(link["href"]).query).get("page") == ["2"]
        )
        self.assert_global_url(page_link["href"])
        paged = self.client.get(page_link["href"])
        self.assertEqual(paged.context["bookmark_list"].bookmarks_page.number, 2)
        tagged = self.client.get(
            reverse(self.scope_view), {**query, "q": "History #book", "page": 2}
        )
        selected = self.make_soup(tagged.content.decode()).select_one(
            ".selected-tags a"
        )
        self.assertNotIn("page", self.assert_global_url(selected["href"]))
        details = self.client.get(
            reverse(self.scope_view), {"q": "History", "details": bookmarks[0].id}
        )
        context = details.context["details"]
        for url in (
            context.close_url,
            context.edit_return_url,
            context.action_url,
            context.delete_url,
        ):
            self.assert_global_url(url)

    def test_search_action_preserves_current_scope(self):
        bundle = self.setup_bundle()
        for action in ("apply", "save"):
            for scoped in (True, False):
                with self.subTest(action=action, scoped=scoped):
                    params = {"q": "History", "sort": "title_asc", action: ""}
                    if scoped:
                        params["bundle"] = bundle.id
                    else:
                        response, query = self.global_search(
                            bundle, q="History", sort="title_asc"
                        )
                        params = {
                            **{key: values[0] for key, values in query.items()},
                            action: "",
                        }
                    response = self.client.post(reverse(self.scope_view), params)
                    query = parse_qs(urlsplit(response.url).query)
                    self.assertEqual(
                        query.get("bundle"), [str(bundle.id)] if scoped else None
                    )
                    self.assertNotIn("search_scope", query)
                    profile = self.user.profile
                    profile.refresh_from_db()
                    self.assertNotIn("bundle", profile.search_preferences)
                    self.assertNotIn("search_scope", profile.search_preferences)

    def test_search_all_intent_is_idempotent(self):
        inside = self.scope_bookmark(title="History inside")
        outside = self.scope_bookmark(title="History outside")
        bundle = self.setup_bundle(search="inside")
        response, query = self.global_search(q="History")
        self.assertEqual(query, {"q": ["History"]})
        self.assertVisibleBookmarks(response, [inside, outside])
        response = self.client.get(
            reverse(self.scope_view),
            {"bundle": bundle.id, "search_scope": "unknown", "q": "History"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertVisibleBookmarks(response, [inside])
        self.assertEqual(response.context["bookmark_list"].search.bundle, bundle)
