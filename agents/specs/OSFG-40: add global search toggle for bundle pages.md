*Spec: Add global search toggle when a bundle is selected (OSFG-40)*

== PRODUCT ==

*Summary:* When a bundle is selected in linkding, the search bar scopes results to that bundle. Users who use a bundle (e.g. "favorites") as their homepage cannot search globally without navigating away from the bundle — losing their place. This spec adds a "Search all bookmarks" toggle link that appears near the search bar when a bundle is active and a search query is entered. Clicking the toggle searches across all bookmarks while keeping the bundle context visible in the URL and UI. Clicking it again returns to bundle-scoped search.

*Key design choices:*
1. **Option B (backend `global_search` param) over Option A (pure drop-bundle link):** Option B keeps the bundle selected in the URL (`bundle=<id>` stays) while bypassing the bundle filter, so users can switch back to bundle-scoped search without re-selecting their bundle — directly addressing the "my homepage is a bundle" use case.
2. **UI pattern is a small contextual link** near the search bar — appears only when both a bundle and a non-empty query are present. Non-intrusive and reversible.
3. **`global_search=1` as a URL param** preserves the bundle param and all other search state (sort, unread, shared) in the URL as the user toggles.

*Behavior* (numbered, testable invariants from the user's view):

1. **Default — no change:** When no bundle is selected, or when a bundle is selected but the search query is empty, the search bar and results behave exactly as before. No toggle is rendered. Existing within-bundle search is unchanged.

2. **Toggle appears on bundle + query:** When a bundle is selected (`bundle=<id>`) **and** a non-empty search query is present (`q=<term>`), a "Search all bookmarks" link is rendered near the search bar.

3. **"Search all bookmarks" click:** Navigates to `?bundle=<id>&q=<term>&global_search=1`. Results include all matching bookmarks across the user's account — not restricted to the selected bundle. The bundle panel continues to highlight the active bundle (bundle param is still present).

4. **Global search mode — toggle flips:** When `global_search=1` is in the URL with `bundle` and `q`, the "Search all bookmarks" link is replaced by a "Search in [bundle name]" link. Clicking it navigates to `?bundle=<id>&q=<term>` (removing `global_search`) to restore bundle-scoped search.

5. **Works on archived bookmarks view:** The same toggle behavior and global-search bypass apply on the `/bookmarks/archived` page.

6. **Strictly additive:** Without `global_search=1` (or with `global_search=0`), bundle filtering is entirely unchanged. The feature is a strict opt-in superset of existing behavior.

7. **Unauthenticated/shared views:** Unaffected — the shared bookmarks view does not use bundle filtering.

== TECH ==

*Context:* (all references @ commit `30510d3463237f0653ea8c1cdbd889c070062566`)

- `bookmarks/models.py:224` — `BookmarkSearch` class. Its `params` list (`["q", "user", "bundle", "sort", "shared", "unread", "modified_since", "added_since"]`) drives hidden-field generation in `BookmarkSearchForm`; `from_request` parses URL query params into a `BookmarkSearch` instance; `query_params` property returns a dict of modified (non-default) params used for redirect URL construction.
- `bookmarks/queries.py:268-270` — `_base_bookmarks_query` calls `_filter_bundle(query_set, search.bundle)` when `search.bundle` is set. `_filter_bundle` (line 176) applies bundle-level filters: search terms, any/all/excluded tags, unread flag, shared flag.
- `bookmarks/forms.py:248` — `BookmarkSearchForm` mirrors `BookmarkSearch.params` as form fields; non-editable modified params become `HiddenInput` so the search form preserves state across submissions.
- `bookmarks/templates/bookmarks/search.html:1` — the search bar partial; rendered in both active and archived bookmark page templates. The form loops over `search_form.hidden_fields` to preserve non-editable params.
- `bookmarks/views/bookmarks.py:44` (active) and `bookmarks/views/bookmarks.py:84` (archived) — both build a `BookmarkSearch` from request, pass it to context as `search`, and render templates that include `search.html`.

*Design alternatives:*

- **Option A — pure template link (drop bundle param):** Show a link to `?q=<term>` (removing `bundle`) when bundle + q are active. Pros: zero backend changes. Cons: the bundle is deselected — users on a "homepage bundle" must re-select it to return to their bundle after a global search. Directly contradicts the stated use case. Rejected.
- **Option B — `global_search` URL param with backend bypass (selected):** New `global_search` bool on `BookmarkSearch`; when True, `_base_bookmarks_query` skips `_filter_bundle`. The `bundle` param stays in the URL so the toggle is fully reversible. Correct for the homepage-bundle scenario.
- **Persistent user preference toggle:** A saved preference that always searches globally when a bundle is selected. Rejected: silently breaks the expected behavior of bundle-scoped search for all searches, removing intentional bundle filtering without per-query control.

*Proposed changes:*

**1. `bookmarks/models.py` — `BookmarkSearch`:**
- Add `"global_search"` to the `params` list (e.g., after `"unread"`).
- Add `"global_search": False` to `defaults`.
- Add `global_search: bool = None` to `__init__` parameters; set `self.global_search = global_search if global_search is not None else self.defaults["global_search"]`.
- In `from_request`: add a special case for `"global_search"` (parallel to the `"bundle"` case): `initial_values["global_search"] = True` when `query_dict.get("global_search")` is truthy (any non-empty string such as `"1"`).
- In `query_params` property: handle the boolean — emit `"1"` when `value is True`; since `global_search=False` is the default, `is_modified` will never include it in `modified_params` when False, so no special "don't emit False" logic is needed.

**2. `bookmarks/queries.py` — `_base_bookmarks_query` (line 268):**
- Change: `if search.bundle:` → `if search.bundle and not search.global_search:`
  This is the only backend change; all three query entry points (`query_bookmarks`, `query_archived_bookmarks`, `query_shared_bookmarks`) flow through `_base_bookmarks_query`.

**3. `bookmarks/forms.py` — `BookmarkSearchForm`:**
- Add field: `global_search = forms.BooleanField(required=False)`.
  The existing loop over `search.params` will render it as a `HiddenInput` automatically when modified (i.e., when `global_search=True`), preserving state across search form submissions.

**4. `bookmarks/templates/bookmarks/search.html`:**
- After the closing `</div>` of the `search-container`, add:
  ```html
  {% if search.bundle and search.q %}
    <div class="global-search-hint">
      {% if search.global_search %}
        <a href="?bundle={{ search.bundle.id }}&q={{ search.q|urlencode }}">Search in {{ search.bundle.name }}</a>
      {% else %}
        <a href="?bundle={{ search.bundle.id }}&q={{ search.q|urlencode }}&global_search=1">Search all bookmarks</a>
      {% endif %}
    </div>
  {% endif %}
  ```
  *Note:* This simplified URL includes `bundle`, `q`, and (when toggling on) `global_search`, but drops other modified params (sort, shared, unread). This is acceptable for the initial implementation since the toggle's primary use case is a simple bundle+query session. Preserving all params is a straightforward follow-up if desired (pass a pre-built toggle URL from the view context).

*Open questions resolved:*

- *Option A vs B?* → B. Preserves bundle context so users can return to bundle-scoped search in one click, directly addressing the homepage-bundle use case.
- *When does the toggle appear?* → Only when both `bundle` and a non-empty `q` are present — avoids clutter when browsing a bundle without a search term.
- *Bundle panel highlighting during global search?* → Unchanged — `bundle` param remains in the URL, so the selected bundle continues to be highlighted in the side panel.
- *Archived view coverage?* → Yes — `_base_bookmarks_query` backs both `query_bookmarks` and `query_archived_bookmarks`; the `search.html` partial is shared.
- *REST API impact?* → None — `BookmarkSearch.from_request` is the parse path for the HTML views only; the REST API search does not use the `bundle` param.
- *Preserving sort/unread/shared in the toggle URL?* → Dropped in the initial template implementation (see note in Proposed Changes). Acceptable as a first cut.

*Risks / blast radius:* Low. The query change is behind a new param that defaults to False and is only activated by an explicit `global_search=1` in the URL. The template change is additive. The form field is `required=False`. No database migrations needed.

*Validation & verification criteria* (must ALL pass before merge):

1. **Global search bypasses bundle filter:** `test_global_search_ignores_bundle_filter` in `bookmarks/tests/test_bookmark_index_view.py` — create a bookmark outside a bundle that matches a query `q`; confirm it appears when `global_search=1` is added but not in the plain `?bundle=<id>&q=<term>` request. Command: `uv run pytest bookmarks/tests/test_bookmark_index_view.py -k "global_search" -v`

2. **Bundle-scoped search unchanged by default:** Existing test `test_should_list_bookmarks_matching_bundle` in `test_bookmark_index_view.py` continues to pass — a plain `?bundle=<id>` search still restricts results to the bundle. Command: `uv run pytest bookmarks/tests/test_bookmark_index_view.py::BookmarkIndexViewTest::test_should_list_bookmarks_matching_bundle -v`

3. **Toggle link renders when bundle + query are both present:** Request `?bundle=<id>&q=foo` on the active bookmarks view; assert response HTML contains an `<a>` element linking to `...global_search=1`. Covered by `test_global_search_ignores_bundle_filter` in the same file.

4. **"Search in bundle" link renders when global_search=1:** Request `?bundle=<id>&q=foo&global_search=1`; assert response HTML contains an `<a>` element without `global_search=1` in its href. Covered by the same test.

5. **No toggle when bundle is absent:** `?q=foo` (no bundle selected) — response HTML contains no `.global-search-hint` element. Add assertion to `test_global_search_ignores_bundle_filter`.

6. **No toggle when query is empty:** `?bundle=<id>` (bundle but empty q) — response HTML contains no `.global-search-hint` element. Add assertion to `test_global_search_ignores_bundle_filter`.

7. **Archived view: global search works:** `uv run pytest bookmarks/tests/test_bookmark_archived_view.py -k "global_search" -v` — same link behavior and bundle-bypass on `/bookmarks/archived`. Add `test_global_search_ignores_bundle_filter` in `test_bookmark_archived_view.py`.

8. **`BookmarkSearch.from_request` parses `global_search=1`:** `test_from_request_global_search` in `bookmarks/tests/test_bookmark_search_model.py` — assert a `QueryDict("global_search=1")` produces `BookmarkSearch` with `global_search=True`; assert `QueryDict("")` produces `global_search=False`. Command: `uv run pytest bookmarks/tests/test_bookmark_search_model.py -k "global_search" -v`

9. **`BookmarkSearch.query_params` serializes correctly:** `test_query_params_global_search` in `test_bookmark_search_model.py` — assert `BookmarkSearch(global_search=True).query_params` returns `{"global_search": "1"}` and `BookmarkSearch().query_params` does not include `"global_search"`.

10. **Validation gate:** `make lint && make test` passes with no new failures.

11. **Visual proof (user-facing change):** With the app running (`make init && uv run manage.py runserver 8000`), computer_use captures:
    (a) A bundle selected in the side panel with a search query entered — the "Search all bookmarks" link is visible near the search bar.
    (b) Clicking the link — results include bookmarks outside the bundle that match the query.
    (c) The "Search in [bundle name]" link visible in global-search mode.
    (d) Clicking "Search in [bundle name]" — results revert to bundle-scoped search.
    Screenshot proof must be attached to the task record and the PR body.

Co-Authored-By: Oz <oz-agent@warp.dev>
