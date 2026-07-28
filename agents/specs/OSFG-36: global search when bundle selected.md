*Spec: Global search option when a bundle is selected (OSFG-36)*

## PRODUCT

*Summary:* Add a "Search all bookmarks" toggle that appears in the search UI whenever a bundle is active. Activating it searches across all bookmarks (ignoring the bundle filter) while keeping the query text and bundle context in the URL so the state is shareable/bookmarkable and the user can easily re-scope back to the bundle.

*Key design choices:*
1. `global_search` is a transient URL param (`?bundle=3&global_search=1&q=...`), not a saved preference — it's a per-session contextual override, not a user setting like sort order.
2. The `bundle` param stays in the URL when global search is active, so the sidebar still shows the bundle as selected and re-scoping is a single click on "Back to [bundle name]".
3. The UI control lives in `search.html`, computed via the `bookmark_search` templatetag so it has access to the request and can generate the correct toggle URLs.

*Behavior* (numbered, testable invariants from the user's/consumer's view):
1. When no bundle is selected, no global search control is shown in the search UI.
2. When a bundle is selected, a clearly labelled "Search all bookmarks" link/button appears in the search container area.
3. Clicking "Search all bookmarks" navigates to a URL with the bundle param preserved, `global_search=1` added, and the current query `q` preserved; search results show ALL of the user's bookmarks (not just bundle-scoped) matching `q`.
4. While global search is active, the bundle remains shown as selected in the sidebar; a "Back to [bundle name]" link replaces "Search all bookmarks" so the user can re-scope.
5. While global search is active, the tag cloud shows tags derived from ALL matching bookmarks (not bundle-scoped).
6. Clicking "Back to [bundle name]" removes `global_search` from the URL, restoring bundle-scoped search with the query text preserved.
7. Typing a new search query while global search is active (submitting the search form) keeps the global search state — `global_search` is preserved as a hidden field in the search form.
8. Existing bundle-scoped search behavior (no `global_search` param) is unchanged.

## TECH

*Context:* How bundle search works today:
- `bookmarks/models.py (224-343) @ 30510d3` — `BookmarkSearch` is a plain Python class (not a DB model). `params` lists all URL params accepted; `from_request` parses them from the query dict. `query_params` property returns only modified (non-default) params for URL generation.
- `bookmarks/queries.py (227-270) @ 30510d3` — `_base_bookmarks_query` applies `_filter_bundle()` unconditionally when `search.bundle` is set (lines 268-270). This is the single point of bundle filtering.
- `bookmarks/queries.py (308-315) @ 30510d3` — `query_bookmark_tags` (used by tag cloud) calls `query_bookmarks` which also goes through `_base_bookmarks_query`, so the tag cloud naturally follows the same bundle filter.
- `bookmarks/forms.py (248-303) @ 30510d3` — `BookmarkSearchForm` marks non-editable modified params as hidden fields; these are rendered in `search.html` to preserve all active search params across form submissions.
- `bookmarks/templatetags/bookmarks.py (9-27) @ 30510d3` — `bookmark_search` inclusion tag builds `search_form` / `preferences_form` and returns a context dict. This is the right place to compute toggle URLs since it has `request` access.
- `bookmarks/templates/bookmarks/search.html (1-78) @ 30510d3` — search container with search autocomplete input, hidden fields, and preferences dropdown. The global search toggle control will be added here.
- `bookmarks/views/contexts.py (645-662) @ 30510d3` — `BundlesContext` reads `bundle` from `request.GET` to resolve `selected_bundle`. No changes needed — the bundle param stays in the URL when global search is active, so the sidebar correctly highlights the selected bundle automatically.

*Design alternatives:*
- **Where to place the UI control**: Option A (chosen): in `search.html` via the `bookmark_search` templatetag — the templatetag already has `request` access and can cleanly generate toggle URLs without template-level URL manipulation. Option B: in `bundle_section.html` adjacent to the selected bundle list item — natural placement but requires threading additional variables through `BundlesContext` or computing URL strings in the template (messier, harder to test).
- **What happens to `bundle` param when "Search all" is clicked**: Option A (chosen): keep `bundle` in the URL and add `global_search=1`. Sidebar stays selected, easy to re-scope with one click, bundle context is preserved. Option B: remove `bundle` from the URL — sidebar deselects, context is lost, and "going back" is unclear.
- **`global_search` as preference vs. transient**: Transient URL param (chosen) — global search is a per-bundle-session override and saving it as a default (like sort order) would make all bundles always expand to global scope by default, which defeats the purpose of bundles. Jira ticket design question resolved this way.

*Proposed changes:*

**`bookmarks/models.py`** — `BookmarkSearch`:
- Add `"global_search"` to the `params` list.
- Add `"global_search": ""` to `defaults` (empty string = inactive, consistent with other string params).
- Add `global_search: str = None` to `__init__` signature.
- In `__init__`, set `self.global_search = global_search or self.defaults["global_search"]`.
- No changes needed to `from_request` — it reads the raw query param value as a string (e.g., `"1"`); since the default is `""`, a value of `"1"` is modified and will appear in `query_params` and hidden fields.

**`bookmarks/queries.py`** — `_base_bookmarks_query`:
- Change `if search.bundle:` (line 269) to `if search.bundle and not search.global_search:`. This is the single-line core of the feature.

**`bookmarks/forms.py`** — `BookmarkSearchForm`:
- Add `global_search = forms.CharField(required=False)` field so that when `global_search` is a modified param, `hidden_fields()` renders `<input type="hidden" name="global_search" value="1">` inside the search form — preserving global search state when the user submits a new query.

**`bookmarks/templatetags/bookmarks.py`** — `bookmark_search` tag:
- In `bookmark_search`, compute two additional context values:
  - `global_search_url`: current `request.GET` params with `global_search=1` added and `page` removed (so clicking "Search all" goes to page 1 of global results).
  - `bundle_search_url`: current `request.GET` params with `global_search` removed and `page` removed.
- Add both to the returned context dict so `search.html` can use them.

**`bookmarks/templates/bookmarks/search.html`**:
- Inside `<div class="search-container">`, add a conditional block after the search form and preferences dropdown:
  ```html
  {% if search.bundle %}
    {% if search.global_search %}
      <a href="{{ bundle_search_url }}" class="search-global-toggle">↩ {{ search.bundle.name }}</a>
    {% else %}
      <a href="{{ global_search_url }}" class="search-global-toggle">Search all bookmarks</a>
    {% endif %}
  {% endif %}
  ```

*Open questions resolved:*
- **Is `global_search` saveable?** No — transient URL param only. Not added to `BookmarkSearch.preferences`. Resolved from ticket design questions.
- **Bundle sidebar selection state while global search active?** Bundle stays selected automatically — the `bundle` param stays in the URL, so `BundlesContext.selected_bundle` still resolves it and the `selected` CSS class is applied. No extra code needed in `bundle_section.html` or `BundlesContext`.
- **Tag cloud behavior when global search active?** The tag cloud reflects global scope automatically — `query_bookmark_tags` goes through `_base_bookmarks_query`, and since `_filter_bundle()` is skipped when `global_search` is set, the tag cloud naturally shows tags from all matching bookmarks. No separate tag-cloud code change needed.

## Validation & verification criteria
(Must ALL pass before merge)

1. **BookmarkSearch model parses `global_search`** — `test_global_search_from_request` in `bookmarks/tests/test_bookmark_search_model.py`: verify `BookmarkSearch.from_request(request, QueryDict("bundle=<id>&global_search=1"))` sets `search.global_search = "1"` and `search.is_modified("global_search")` is True; verify `search.query_params` emits `{"global_search": "1"}` when active; verify `search.global_search == ""` and `is_modified` is False when not present.

2. **Global search bypasses bundle filter** — `test_global_search_ignores_bundle_filter` in `bookmarks/tests/test_bookmark_index_view.py`: create bookmarks that match a bundle filter and bookmarks that do not, set up a bundle selecting only the former, GET `?bundle=<id>&global_search=1`, assert ALL user bookmarks are in the visible list (not filtered to bundle).

3. **Tag cloud reflects global scope when global search active** — `test_global_search_tag_cloud_shows_all_tags` in `bookmarks/tests/test_bookmark_index_view.py`: create bookmarks with tags outside the bundle scope, GET `?bundle=<id>&global_search=1`, assert those outside-bundle tags appear in the tag cloud.

4. **Bundle-scoped search unchanged** — existing tests `test_should_list_bookmarks_matching_bundle` and `test_should_list_tags_for_bookmarks_matching_bundle` must still pass with no modifications to the test cases.

5. **UI control shown/hidden correctly** — `test_global_search_ui_control` in `bookmarks/tests/test_bookmark_index_view.py`:
   - No bundle selected → neither "Search all bookmarks" nor "Back to" link present in response HTML.
   - Bundle selected, no `global_search` → "Search all bookmarks" link present; "Back to" link absent.
   - Bundle selected, `global_search=1` → "Search all bookmarks" link absent; "Back to [bundle name]" link present.

6. **`global_search` preserved across search form submission** — `test_global_search_preserved_in_search_form` in `bookmarks/tests/test_bookmark_index_view.py`: GET `?bundle=<id>&global_search=1`, assert the rendered HTML contains `<input type="hidden" name="global_search" value="1">` inside the search form.

7. **`bundle_search_url` removes `global_search`** — verify (via the view test or templatetag unit test) that the "Back to [bundle name]" link href does not contain `global_search`, does contain `bundle=<id>`, and does contain any active `q` param.

8. **Validation gate passes** — `make lint && make test` passes on the branch.
