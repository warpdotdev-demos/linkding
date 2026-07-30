*Spec: Add global search affordance when a bundle is active*

== PRODUCT ==
*Summary:* When a user has a bundle selected and types a search query, the results are silently scoped to that bundle. Many users set a bundle as their homepage, so searching from there is cumbersome — they must navigate back to the unfiltered view first. This feature adds a small, contextual "Search all bookmarks" link that appears only when both a bundle and a search query are active, letting users instantly run the same search across all their bookmarks without leaving the bundle context.

*Key design choices:*
1. The affordance lives in the search bar area (`search.html`), not the bundle sidebar — that is where user attention is during a search, making it immediately discoverable.
2. The URL is computed in Python (in the `bookmark_search` templatetag) by stripping `bundle` and `page` from the current GET params while preserving all other params (sort, shared, unread) — keeping user preferences intact.
3. Implemented as a plain inline anchor (matching existing `bundle_section.html` navigation links), not a button or chip — navigation, not action.

*Behavior* (numbered, testable invariants from the user's view):
1. When a bundle is selected AND a search query is active (`?bundle=<id>&q=<term>`), a "Search all bookmarks" link appears below the search form on both the active bookmarks view (`/bookmarks/`) and the archived bookmarks view (`/bookmarks/archived/`).
2. Clicking the link navigates to `?q=<term>` on the current page — preserving all other active search params (sort, shared, unread) but dropping `bundle` and resetting to page 1 — triggering a search across all bookmarks.
3. When only a bundle is selected with no query (`?bundle=<id>`), the link is hidden — no visual clutter in the default bundle-browsing state.
4. When a query is active but no bundle is selected (`?q=<term>`), the link is hidden — no relevance.
5. When neither a bundle nor a query is active, the link is hidden.
6. The bundle remains visible in the sidebar after clicking the link — the user can return to the bundle-scoped view at any time by clicking the bundle name.

== TECH ==
*Context:* The linkding bookmark list is rendered via `bookmark_page.html` (commit `fdd4234`), which calls the `{% bookmark_search %}` inclusion tag (defined in `bookmarks/templatetags/bookmarks.py:9 @ fdd4234`). That tag renders `bookmarks/templates/bookmarks/search.html` and passes `search` (a `BookmarkSearch` instance from `bookmarks/models.py:224 @ fdd4234`) plus `request` into the template context. The `BookmarkSearch` model holds `bundle` (a `BookmarkBundle` instance or `None`) and `q` (a string). The `RequestContext` class in `bookmarks/views/contexts.py:55 @ fdd4234` already provides a `get_url(view_url, remove=...)` helper that builds a URL by stripping named params while keeping others. `search.html` does not currently use `request` for URL construction; all hidden-field logic is driven by `search_form`.

The `BundlesContext` in `bookmarks/views/contexts.py:645 @ fdd4234` provides the sidebar bundle list for each view; the template in `bundle_section.html` already uses `bookmark_list.search.q` as a URL building block (line 18), confirming the pattern of computing contextual URLs inside templates/tags.

Both `bookmarks.index` and `bookmarks.archived` views create a `BundlesContext` and pass `bundles` to the template; both call `{% bookmark_search bookmark_list.search mode=bookmark_list.search_mode %}`, so a single change to `search.html` and the templatetag covers both views.

*Design alternatives:*
- **Placement: search bar vs. bundle sidebar** — Placing the affordance below the search form (`search.html`) makes it immediately visible as the user finishes typing. Placing it in `bundle_section.html` (sidebar) requires the user to look away from the search area. The search bar placement is chosen. An alternative would be an inline message in the search results area ("Showing results for bundle X — search all?"), but that would require modifying `bookmark_list.html` and would duplicate logic; the search bar is already the single authoritative location for search interaction.
- **URL construction: Python (templatetag) vs. pure template** — Computing the URL in the templatetag function is preferred: it is testable without rendering a full template and keeps templates free of Python string manipulation. The alternative is a custom filter like `|remove_bundle_param`, which adds a filter without gain over a simple Python function in the existing tag.
- **Visual treatment: link vs. button/chip vs. inline badge** — An anchor link is the idiomatic HTML element for "navigate here" and matches the `bundle_section.html` pattern (bare `<a>` inside a `<li>`). A button/chip would be semantically wrong (it's navigation, not action) and would require new CSS.

*Proposed changes:*
1. **`bookmarks/templatetags/bookmarks.py`** — In `bookmark_search`, compute a `global_search_url` value:
   - If `search.bundle is not None` and `search.q` is non-empty: copy `request.GET`, remove `bundle` and `page`, URL-encode the remainder, return as a relative `?<params>` string (falling back to `request.path` if no params remain).
   - Otherwise: `None`.
   - Pass `global_search_url` in the returned context dict.

2. **`bookmarks/templates/bookmarks/search.html`** — After the closing `</form>` tag of `#search` and before the `<ld-dropdown>`, add:
   ```html
   {% if global_search_url %}
     <a href="{{ global_search_url }}" class="search-all-link">Search all bookmarks</a>
   {% endif %}
   ```
   The outer `.search-container` already uses flex layout; this element will appear inline in the bar. Exact CSS class and positioning to be confirmed during implementation/UI verification.

*Open questions resolved:*
- **Should the archived view also show the affordance?** Yes — triage explicitly requested both active and archived views. A single `search.html` change achieves this because both views use the same templatetag.
- **Should other active search params (sort, shared, unread) be preserved?** Yes — dropping them would silently change the user's sort/filter preferences. Only `bundle` and `page` are removed.
- **Should we reset to page 1 when navigating to global search?** Yes — a new search scope always starts from page 1.

== VALIDATION & VERIFICATION CRITERIA ==
*(must ALL pass before merge)*

1. **Bundle + query → link visible with correct href** — Given `?bundle=<id>&q=foo`, the rendered HTML contains an `<a>` element with `href` that includes `q=foo` and does NOT include `bundle=`. Checked by: new unit test `test_global_search_link_with_bundle_and_query` in `bookmarks/tests/test_bookmark_search_tag.py`.

2. **Bundle + query + other params → other params preserved** — Given `?bundle=<id>&q=foo&sort=title_asc`, the `global_search_url` includes `sort=title_asc` and does NOT include `bundle=` or `page=`. Checked by: new unit test `test_global_search_link_preserves_other_params` in `bookmarks/tests/test_bookmark_search_tag.py`.

3. **Bundle, no query → link absent** — Given `?bundle=<id>` with no `q`, the link is NOT rendered. Checked by: new unit test `test_global_search_link_hidden_without_query` in `bookmarks/tests/test_bookmark_search_tag.py`.

4. **Query, no bundle → link absent** — Given `?q=foo` with no `bundle`, the link is NOT rendered. Checked by: new unit test `test_global_search_link_hidden_without_bundle` in `bookmarks/tests/test_bookmark_search_tag.py`.

5. **Neither → link absent** — No bundle, no query; the link is NOT rendered. Covered by the existing search form test in `test_bookmark_search_tag.py` (no regression).

6. **Validation gate passes** — `make lint && make test` passes with no new failures.

7. **UI proof (computer-use)** — Using `make serve-bg` on the running app: screenshot showing the "Search all bookmarks" link appears below the search bar when a bundle is selected and a query is typed; screenshot showing the link is absent when no bundle is selected (or no query entered). Both active and archived views verified. Proof attached to the spec PR.
