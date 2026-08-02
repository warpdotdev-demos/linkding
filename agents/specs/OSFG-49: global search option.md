# Spec: Global search option from bundle-scoped search

## PRODUCT

**Summary:** Users viewing a bundle, including a favorites bundle used as their homepage, need to search all of their bookmarks without navigating away first. Add an explicit global-search state and control that switches results from the selected bundle's scope to the user's full active bookmark collection while retaining the current search and filter context.

**Key design choices:**

- Represent global scope as request-backed `BookmarkSearch` state, not as a persistent user preference, because it is an intent for one navigation/search result rather than a new default.
- Preserve the selected bundle in the URL while global scope is active so the user can return to that exact bundle scope in one action.
- Bypass only the bundle predicate; existing ownership, active/archived, text, tag, unread, shared, sort, and pagination semantics must remain unchanged.

**Behavior:**

1. With no selected bundle, bookmark search remains global and no bundle-scope toggle is rendered.
2. With a selected bundle and no global-search state, submitted searches continue to return only bookmarks matching both the user's search/filter criteria and that bundle's criteria.
3. With a selected bundle and global-search state active, submitted searches return every active bookmark owned by the user that matches the normal search/filter criteria, including matches outside the bundle; the selected bundle remains available in the URL/context.
4. The active bundle UI exposes a clear action to enter global search. Activating it preserves the entered query and non-scope search parameters, resets stale pagination, and produces a shareable URL with the explicit global-search state.
5. While global-search state is active, the UI clearly communicates that results are global and exposes the inverse action. Returning to bundle scope preserves the query and non-scope search parameters, removes global-search state, resets stale pagination, and again constrains results to the selected bundle.
6. Existing bundle navigation, search controls, tag-cloud links, bookmark action return URLs, and autocomplete/search submissions preserve the intended scope state instead of silently dropping it.

## TECH

**Context:** At commit `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`, `BookmarkSearch` is the URL/state model for `q`, `bundle`, and other filters in `bookmarks/models.py:226-342`. `BookmarkSearch.from_request()` resolves a `bundle` only if it belongs to the requester and `query_params` serializes only modified state. The active bookmarks view builds this model from GET parameters in `bookmarks/views/bookmarks.py:34-43`. The common query path in `bookmarks/queries.py:235-301` applies normal search criteria, then applies `_filter_bundle()` whenever `search.bundle` is set. `bookmarks/templates/bookmarks/search.html:2-14` submits the search input and hidden non-editable state, while `bookmarks/templatetags/bookmarks.py:9-28` controls which state is exposed to that template. `RequestContext` in `bookmarks/views/contexts.py:24-67` is the existing utility for preserving/removing URL parameters.

**Design alternatives:**

- **Selected: explicit `global_search` flag on `BookmarkSearch`.** Add a false-by-default boolean request parameter, include it in parsing/serialization, and skip `_filter_bundle()` only when both a bundle and the flag are present. This cleanly separates scope intent from bundle identity, keeps back/forward and copied URLs reproducible, and permits a direct inverse action.
- **Remove `bundle` when searching globally.** This is simpler for the query but loses the selected bundle needed for an easy return to scoped results and changes side-panel selection; reject it.
- **Store the choice in `UserProfile.search_preferences`.** This would make a one-off global search unexpectedly alter later searches/homepage behavior; reject it.
- **Create a separate global-search route.** It duplicates bookmark-list/search handling and makes preserving existing filter state harder; reject it.

**Proposed changes:**

1. Extend `BookmarkSearch` in `bookmarks/models.py` with a false-by-default `global_search` boolean, include it in `params`, parse a truthy request representation in `from_request()`, and serialize active state in `query_params` as the documented URL value (for example `global_search=1`). Do not add it to persistent preferences.
2. Update `bookmarks/forms.py` and `bookmarks/templatetags/bookmarks.py` so the state survives search form submissions as a hidden non-editable field while retaining the current editable `q` behavior.
3. Change `bookmarks/queries.py` so `_filter_bundle()` runs only for a selected bundle when `global_search` is false. Keep all prior query, ownership, archive, unread, shared, sorting, and tag-query behavior intact.
4. In `bookmarks/views/contexts.py`, derive URLs for entering global search and returning to the bundle scope from current request parameters. Preserve the selected `bundle`, `q`, sort, unread/shared, and relevant filters; add/remove only `global_search`; remove `page` for both scope transitions.
5. In `bookmarks/templates/bookmarks/search.html`, render an accessible scope-status/control only when a bundle is selected: scoped mode offers the action to search globally; global mode indicates the broader scope and offers the action to return to the selected bundle. Use the context-generated URLs rather than hand-assembling query strings.
6. Add focused tests next to existing search-model, query, and bookmark-index view coverage. Test global-state parsing/serialization, query and tag scopes, rendered toggle states, URL preservation, and returned bookmark visibility.

**Open questions resolved:** The ticket's proposed direction explicitly calls for a search-state flag and UI toggle. Use `global_search=1` as the non-default URL representation and retain `bundle` while global is active so the toggle can restore the exact selected bundle. The scope control belongs next to the existing search form because it is a search-state transition, not a bundle configuration preference.

**Risks / blast radius:** `BookmarkSearch` state feeds rendered list URLs, forms, tag actions, turbo updates, and bookmark actions, so omitting the new flag from any state-preserving path can silently revert scope. Retaining `bundle` with global scope could be misinterpreted by unrelated code; restrict the bypass to the single common bundle-filter condition and cover both list and tag queries. The control changes a user-facing page, so implementation must supply visual evidence in addition to deterministic tests.

## Validation & verification criteria

1. Reproduce the current scoped behavior before the change using a user-owned bundle and two active bookmarks matching the same query—one inside the bundle and one outside it—then request `/bookmarks?q=<query>&bundle=<id>` and confirm only the inside-bundle bookmark is rendered. Record the observed before state in the implementation evidence.
2. Add a failing-then-passing `BookmarkSearch` model regression test in `bookmarks/tests/test_bookmark_search_model.py` that verifies `global_search=1` is parsed as active and serialized with the selected bundle and query; verify default/absent state remains false and does not appear in serialized parameters.
3. Add failing-then-passing query regression tests in `bookmarks/tests/test_queries.py` proving a normal bundle search returns only in-bundle matches, while the same `BookmarkSearch` with global state returns both in-bundle and out-of-bundle matches. Add coverage proving tag-query results use the same widened scope so the tag cloud does not reflect stale bundle-only results.
4. Add failing-then-passing rendered-view tests in `bookmarks/tests/test_bookmark_index_view.py` using the same fixture data: assert global scope displays both matching bookmarks, scoped mode displays only the bundle match, no toggle is rendered without a selected bundle, and each selected-bundle state renders the correct accessible enter/return control and URL.
5. Assert toggle URLs retain `bundle`, `q`, sort, shared/unread, and other active non-page filters, add/remove only `global_search`, and remove `page`; verify following the return URL restores bundle-scoped results without losing the query.
6. Run the focused test files with `uv run pytest bookmarks/tests/test_bookmark_search_model.py bookmarks/tests/test_queries.py bookmarks/tests/test_bookmark_index_view.py -n auto`; they must pass after the implementation.
7. Run the unconditional repository validation gate from the target repo root: `make lint && make test`; it must pass.
8. Exercise the running application with computer use after the deterministic checks: select a bundle, search for a term that has an outside-bundle match, activate global search, observe both matches and the global indicator/control, then return to bundle scope and observe only the bundle match. Capture screenshot evidence for both scoped and global states, attach it to OSFG-49, and embed it in the shared implementation PR.
