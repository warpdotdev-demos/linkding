from urllib.parse import parse_qs, urlsplit

from django.test import RequestFactory, TestCase
from django.urls import reverse

from bookmarks import queries
from bookmarks.models import Bookmark, BookmarkSearch
from bookmarks.services.search_scope import SearchScope
from bookmarks.tests.helpers import BookmarkFactoryMixin


class SearchScopeTest(TestCase, BookmarkFactoryMixin):
    def scope(self, params, mode=""):
        request = RequestFactory().get("/", params)
        request.user = self.get_or_create_test_user()
        return SearchScope(request, request.GET, mode)

    def test_bundle_scope_urls(self):
        bundle = self.setup_bundle()
        for mode, route in (("", "index"), ("archived", "archived")):
            with self.subTest(mode=mode):
                params = {
                    "bundle": bundle.id,
                    "q": '#"tag & name" python + café',
                    "sort": "title_asc",
                    "unread": "off",
                    "shared": "no",
                    "modified_since": "2025-01-01",
                    "added_since": "2024-01-01",
                    "page": "3",
                    "details": "7",
                }
                scope = self.scope(params, mode)
                parts = urlsplit(scope.unbundle_url)
                self.assertEqual(parts.path, reverse(f"linkding:bookmarks.{route}"))
                unbundled = parse_qs(parts.query)
                expected = {
                    key: [str(value)]
                    for key, value in params.items()
                    if key not in ("bundle", "page", "details")
                }
                expected["return_bundle"] = [str(bundle.id)]
                self.assertEqual(unbundled, expected)
                current = {key: value[0] for key, value in unbundled.items()}
                current["q"] = "changed #tag"
                back = parse_qs(urlsplit(self.scope(current, mode).return_url).query)
                self.assertEqual(back["q"], ["changed #tag"])
                self.assertEqual(back["bundle"], [str(bundle.id)])
                self.assertNotIn("return_bundle", back)
                self.assertEqual(back["unread"], ["off"])

    def test_return_bundle_validation(self):
        bundle = self.setup_bundle()
        foreign = self.setup_bundle(user=self.setup_user(), name="Private bundle")
        deleted = self.setup_bundle()
        deleted_id = deleted.id
        deleted.delete()
        for value in (
            "",
            "wat",
            "1.5",
            "-1",
            "0",
            "9" * 5000,
            str(2**63),
            foreign.id,
            deleted_id,
            999999,
            "١",
        ):
            with self.subTest(value=str(value)[:30]):
                scope = self.scope({"return_bundle": value})
                self.assertIsNone(scope.origin)
                self.assertEqual(scope.return_url, "")
                self.assertNotIn("return_bundle", scope.unbundle_url)
        conflicting = self.setup_bundle()
        scope = self.scope({"bundle": bundle.id, "return_bundle": conflicting.id})
        self.assertEqual(scope.bundle, bundle)
        self.assertIsNone(scope.origin)
        self.assertEqual(
            parse_qs(urlsplit(scope.unbundle_url).query)["return_bundle"],
            [str(bundle.id)],
        )
        self.assertEqual(self.scope({"return_bundle": bundle.id}).origin, bundle)
        self.assertIsNone(self.scope({"return_bundle": bundle.id}, "shared").origin)

    def test_return_bundle_is_navigation_only(self):
        user = self.get_or_create_test_user()
        self.client.force_login(user)
        tag = self.setup_tag(name="python")
        inside = self.setup_bookmark(title="inside match", tags=[tag], unread=True)
        outside = self.setup_bookmark(title="outside match", unread=True)
        nonmatch = self.setup_bookmark(title="irrelevant")
        self.setup_bookmark(title="other match", user=self.setup_user(), unread=True)
        self.setup_bookmark(title="archive match", is_archived=True, unread=True)
        bundle = self.setup_bundle(search="inside")
        for legacy in (False, True):
            user.profile.legacy_search = legacy
            user.profile.save()
            for origin in ("", str(bundle.id)):
                request = RequestFactory().get(
                    "/", {"q": "match", "return_bundle": origin}
                )
                request.user = user
                search = BookmarkSearch.from_request(request, request.GET)
                results = queries.query_bookmarks(user, user.profile, search)
                self.assertEqual(
                    set(results.values_list("id", flat=True)), {inside.id, outside.id}
                )
                self.assertEqual(results.count(), 2)
                self.assertEqual(
                    list(queries.query_bookmark_tags(user, user.profile, search)), [tag]
                )
                self.assertNotIn("return_bundle", search.query_params)
                Bookmark.objects.filter(id__in=[inside.id, outside.id]).update(
                    unread=False
                )
                self.client.post(
                    reverse("linkding:bookmarks.index.action"),
                    {
                        "bulk_execute": "",
                        "bulk_select_across": "on",
                        "bulk_action": "bulk_unread",
                    },
                    QUERY_STRING=f"q=match&return_bundle={origin}",
                )
                self.assertEqual(
                    set(
                        Bookmark.objects.filter(
                            owner=user, unread=True, is_archived=False
                        ).values_list("id", flat=True)
                    ),
                    {
                        inside.id,
                        outside.id,
                    },
                )
                nonmatch.refresh_from_db()
                self.assertFalse(nonmatch.unread)
