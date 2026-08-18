from django.http import QueryDict
from django.test import TestCase

from bookmarks.models import BookmarkSearch
from bookmarks.tests.helpers import BookmarkFactoryMixin


class MockRequest:
    def __init__(self, user):
        self.user = user


class BookmarkSearchModelTest(TestCase, BookmarkFactoryMixin):
    def test_from_request(self):
        # no params
        query_dict = QueryDict()

        search = BookmarkSearch.from_request(None, query_dict)
        self.assertEqual(search.q, "")
        self.assertEqual(search.user, "")
        self.assertEqual(search.bundle, None)
        self.assertEqual(search.sort, BookmarkSearch.SORT_ADDED_DESC)
        self.assertEqual(search.shared, BookmarkSearch.FILTER_SHARED_OFF)
        self.assertEqual(search.unread, BookmarkSearch.FILTER_UNREAD_OFF)

        # some params
        query_dict = QueryDict("q=search query&user=user123")

        bookmark_search = BookmarkSearch.from_request(None, query_dict)
        self.assertEqual(bookmark_search.q, "search query")
        self.assertEqual(bookmark_search.user, "user123")
        self.assertEqual(bookmark_search.sort, BookmarkSearch.SORT_ADDED_DESC)
        self.assertEqual(search.shared, BookmarkSearch.FILTER_SHARED_OFF)
        self.assertEqual(search.unread, BookmarkSearch.FILTER_UNREAD_OFF)

        # all params
        bundle = self.setup_bundle()
        request = MockRequest(self.get_or_create_test_user())
        query_dict = QueryDict(
            f"q=search query&sort=title_asc&user=user123&bundle={bundle.id}&shared=yes&unread=yes"
        )

        search = BookmarkSearch.from_request(request, query_dict)
        self.assertEqual(search.q, "search query")
        self.assertEqual(search.user, "user123")
        self.assertEqual(search.bundle, bundle)
        self.assertEqual(search.sort, BookmarkSearch.SORT_TITLE_ASC)
        self.assertEqual(search.shared, BookmarkSearch.FILTER_SHARED_SHARED)
        self.assertEqual(search.unread, BookmarkSearch.FILTER_UNREAD_YES)

        # respects preferences
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        query_dict = QueryDict("q=search query")

        search = BookmarkSearch.from_request(None, query_dict, preferences)
        self.assertEqual(search.q, "search query")
        self.assertEqual(search.user, "")
        self.assertEqual(search.sort, BookmarkSearch.SORT_TITLE_ASC)
        self.assertEqual(search.shared, BookmarkSearch.FILTER_SHARED_OFF)
        self.assertEqual(search.unread, BookmarkSearch.FILTER_UNREAD_YES)

        # query overrides preferences
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "shared": BookmarkSearch.FILTER_SHARED_SHARED,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        query_dict = QueryDict("sort=title_desc&shared=no&unread=off")

        search = BookmarkSearch.from_request(None, query_dict, preferences)
        self.assertEqual(search.q, "")
        self.assertEqual(search.user, "")
        self.assertEqual(search.sort, BookmarkSearch.SORT_TITLE_DESC)
        self.assertEqual(search.shared, BookmarkSearch.FILTER_SHARED_UNSHARED)
        self.assertEqual(search.unread, BookmarkSearch.FILTER_UNREAD_OFF)

    def test_from_request_ignores_invalid_bundle_param(self):
        self.setup_bundle()

        # bundle does not exist
        request = MockRequest(self.get_or_create_test_user())
        query_dict = QueryDict("bundle=99999")
        search = BookmarkSearch.from_request(request, query_dict)
        self.assertIsNone(search.bundle)

        # bundle belongs to another user
        other_user = self.setup_user()
        bundle = self.setup_bundle(user=other_user)
        query_dict = QueryDict(f"bundle={bundle.id}")
        search = BookmarkSearch.from_request(request, query_dict)
        self.assertIsNone(search.bundle)

    def test_query_params(self):
        # no params
        search = BookmarkSearch()
        self.assertEqual(search.query_params, {})

        # params are default values
        search = BookmarkSearch(
            q="", sort=BookmarkSearch.SORT_ADDED_DESC, user="", bundle=None, shared=""
        )
        self.assertEqual(search.query_params, {})

        # some modified params
        search = BookmarkSearch(q="search query", sort=BookmarkSearch.SORT_ADDED_ASC)
        self.assertEqual(
            search.query_params,
            {"q": "search query", "sort": BookmarkSearch.SORT_ADDED_ASC},
        )

        # all modified params
        bundle = self.setup_bundle()
        search = BookmarkSearch(
            q="search query",
            sort=BookmarkSearch.SORT_ADDED_ASC,
            user="user123",
            bundle=bundle,
            shared=BookmarkSearch.FILTER_SHARED_SHARED,
            unread=BookmarkSearch.FILTER_UNREAD_YES,
        )
        self.assertEqual(
            search.query_params,
            {
                "q": "search query",
                "sort": BookmarkSearch.SORT_ADDED_ASC,
                "user": "user123",
                "bundle": bundle.id,
                "shared": BookmarkSearch.FILTER_SHARED_SHARED,
                "unread": BookmarkSearch.FILTER_UNREAD_YES,
            },
        )

        # preferences are not query params if they match default
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        search = BookmarkSearch(preferences=preferences)
        self.assertEqual(search.query_params, {})

        # param is not a query param if it matches the preference
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        search = BookmarkSearch(
            sort=BookmarkSearch.SORT_TITLE_ASC,
            unread=BookmarkSearch.FILTER_UNREAD_YES,
            preferences=preferences,
        )
        self.assertEqual(search.query_params, {})

        # overriding preferences is a query param
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "shared": BookmarkSearch.FILTER_SHARED_SHARED,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        search = BookmarkSearch(
            sort=BookmarkSearch.SORT_TITLE_DESC,
            shared=BookmarkSearch.FILTER_SHARED_UNSHARED,
            unread=BookmarkSearch.FILTER_UNREAD_OFF,
            preferences=preferences,
        )
        self.assertEqual(
            search.query_params,
            {
                "sort": BookmarkSearch.SORT_TITLE_DESC,
                "shared": BookmarkSearch.FILTER_SHARED_UNSHARED,
                "unread": BookmarkSearch.FILTER_UNREAD_OFF,
            },
        )

    def test_modified_params(self):
        # no params
        bookmark_search = BookmarkSearch()
        modified_params = bookmark_search.modified_params
        self.assertEqual(len(modified_params), 0)

        # params are default values
        bookmark_search = BookmarkSearch(
            q="", sort=BookmarkSearch.SORT_ADDED_DESC, user="", shared=""
        )
        modified_params = bookmark_search.modified_params
        self.assertEqual(len(modified_params), 0)

        # some modified params
        bookmark_search = BookmarkSearch(
            q="search query", sort=BookmarkSearch.SORT_ADDED_ASC
        )
        modified_params = bookmark_search.modified_params
        self.assertCountEqual(modified_params, ["q", "sort"])

        # all modified params
        bundle = self.setup_bundle()
        bookmark_search = BookmarkSearch(
            q="search query",
            sort=BookmarkSearch.SORT_ADDED_ASC,
            user="user123",
            bundle=bundle,
            shared=BookmarkSearch.FILTER_SHARED_SHARED,
            unread=BookmarkSearch.FILTER_UNREAD_YES,
        )
        modified_params = bookmark_search.modified_params
        self.assertCountEqual(
            modified_params, ["q", "sort", "user", "bundle", "shared", "unread"]
        )

        # preferences are not modified params
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        bookmark_search = BookmarkSearch(preferences=preferences)
        modified_params = bookmark_search.modified_params
        self.assertEqual(len(modified_params), 0)

        # param is not modified if it matches the preference
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        bookmark_search = BookmarkSearch(
            sort=BookmarkSearch.SORT_TITLE_ASC,
            unread=BookmarkSearch.FILTER_UNREAD_YES,
            preferences=preferences,
        )
        modified_params = bookmark_search.modified_params
        self.assertEqual(len(modified_params), 0)

        # overriding preferences is a modified param
        preferences = {
            "sort": BookmarkSearch.SORT_TITLE_ASC,
            "shared": BookmarkSearch.FILTER_SHARED_SHARED,
            "unread": BookmarkSearch.FILTER_UNREAD_YES,
        }
        bookmark_search = BookmarkSearch(
            sort=BookmarkSearch.SORT_TITLE_DESC,
            shared=BookmarkSearch.FILTER_SHARED_UNSHARED,
            unread=BookmarkSearch.FILTER_UNREAD_OFF,
            preferences=preferences,
        )
        modified_params = bookmark_search.modified_params
        self.assertCountEqual(modified_params, ["sort", "shared", "unread"])

    def test_has_modifications(self):
        # no params
        bookmark_search = BookmarkSearch()
        self.assertFalse(bookmark_search.has_modifications)

        # params are default values
        bookmark_search = BookmarkSearch(
            q="", sort=BookmarkSearch.SORT_ADDED_DESC, user="", shared=""
        )
        self.assertFalse(bookmark_search.has_modifications)

        # modified params
        bookmark_search = BookmarkSearch(
            q="search query", sort=BookmarkSearch.SORT_ADDED_ASC
        )
        self.assertTrue(bookmark_search.has_modifications)

    def test_preferences_dict(self):
        # no params
        bookmark_search = BookmarkSearch()
        self.assertEqual(
            bookmark_search.preferences_dict,
            {
                "sort": BookmarkSearch.SORT_ADDED_DESC,
                "shared": BookmarkSearch.FILTER_SHARED_OFF,
                "unread": BookmarkSearch.FILTER_UNREAD_OFF,
            },
        )

        # with params
        bookmark_search = BookmarkSearch(
            sort=BookmarkSearch.SORT_TITLE_DESC, unread=BookmarkSearch.FILTER_UNREAD_YES
        )
        self.assertEqual(
            bookmark_search.preferences_dict,
            {
                "sort": BookmarkSearch.SORT_TITLE_DESC,
                "shared": BookmarkSearch.FILTER_SHARED_OFF,
                "unread": BookmarkSearch.FILTER_UNREAD_YES,
            },
        )

        # only returns preferences
        bundle = self.setup_bundle()
        bookmark_search = BookmarkSearch(
            q="search query", user="user123", bundle=bundle
        )
        self.assertEqual(
            bookmark_search.preferences_dict,
            {
                "sort": BookmarkSearch.SORT_ADDED_DESC,
                "shared": BookmarkSearch.FILTER_SHARED_OFF,
                "unread": BookmarkSearch.FILTER_UNREAD_OFF,
            },
        )

    def test_scope_defaults_to_bundle(self):
        search = BookmarkSearch()
        self.assertEqual(search.scope, BookmarkSearch.SCOPE_BUNDLE)
        self.assertFalse(search.is_modified("scope"))

        # without a bundle, the scope does not affect the query either way
        self.assertFalse(search.applies_bundle_filter)

    def test_scope_from_request(self):
        bundle = self.setup_bundle()
        request = MockRequest(self.get_or_create_test_user())

        # bundle scope by default
        query_dict = QueryDict(f"bundle={bundle.id}&q=search query")
        search = BookmarkSearch.from_request(request, query_dict)
        self.assertEqual(search.scope, BookmarkSearch.SCOPE_BUNDLE)
        self.assertTrue(search.applies_bundle_filter)

        # global scope keeps the bundle, but does not apply its filter
        query_dict = QueryDict(f"bundle={bundle.id}&q=search query&scope=all")
        search = BookmarkSearch.from_request(request, query_dict)
        self.assertEqual(search.scope, BookmarkSearch.SCOPE_ALL)
        self.assertEqual(search.bundle, bundle)
        self.assertFalse(search.applies_bundle_filter)

    def test_unknown_scope_falls_back_to_bundle(self):
        bundle = self.setup_bundle()
        request = MockRequest(self.get_or_create_test_user())
        query_dict = QueryDict(f"bundle={bundle.id}&scope=everything")

        search = BookmarkSearch.from_request(request, query_dict)
        self.assertEqual(search.scope, BookmarkSearch.SCOPE_BUNDLE)
        self.assertTrue(search.applies_bundle_filter)
        # invalid values never leak into generated URLs
        self.assertNotIn("scope", search.query_params)

    def test_query_params_include_scope_only_when_modified(self):
        search = BookmarkSearch(scope=BookmarkSearch.SCOPE_BUNDLE)
        self.assertNotIn("scope", search.query_params)

        search = BookmarkSearch(scope=BookmarkSearch.SCOPE_ALL)
        self.assertEqual(search.query_params["scope"], BookmarkSearch.SCOPE_ALL)

    def test_has_filters_ignores_sort_and_scope(self):
        # no params
        self.assertFalse(BookmarkSearch().has_filters)

        # sort and scope do not narrow down the result set
        self.assertFalse(BookmarkSearch(sort=BookmarkSearch.SORT_TITLE_ASC).has_filters)
        self.assertFalse(BookmarkSearch(scope=BookmarkSearch.SCOPE_ALL).has_filters)

        # every other param does
        bundle = self.setup_bundle()
        self.assertTrue(BookmarkSearch(q="search query").has_filters)
        self.assertTrue(BookmarkSearch(user="user123").has_filters)
        self.assertTrue(BookmarkSearch(bundle=bundle).has_filters)
        self.assertTrue(
            BookmarkSearch(shared=BookmarkSearch.FILTER_SHARED_SHARED).has_filters
        )
        self.assertTrue(
            BookmarkSearch(unread=BookmarkSearch.FILTER_UNREAD_YES).has_filters
        )
        self.assertTrue(
            BookmarkSearch(modified_since="2025-01-01T00:00:00Z").has_filters
        )
        self.assertTrue(BookmarkSearch(added_since="2025-01-01T00:00:00Z").has_filters)

    def test_scope_is_not_a_preference(self):
        self.assertNotIn("scope", BookmarkSearch.preferences)

        search = BookmarkSearch(scope=BookmarkSearch.SCOPE_ALL)
        self.assertNotIn("scope", search.preferences_dict)
        self.assertFalse(search.has_modified_preferences)

        # a scope preference cannot make global search the default
        search = BookmarkSearch(preferences={"scope": BookmarkSearch.SCOPE_ALL})
        self.assertNotIn("scope", search.preferences_dict)
