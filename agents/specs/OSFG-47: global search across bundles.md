*Spec: Global search override when a bundle is active (OSFG-47)*

== PRODUCT ==

*Summary:* When a bundle is selected, searches are currently scoped to that bundle's bookmarks — users must navigate away to search globally, losing their bundle context. This feature adds a transient "Search everywhere" toggle in the search bar area that, when active, bypasses the bundle filter and queries all bookmarks, while keeping the bundle parameter in the URL so the user can return to the bundle-scoped view.

*Key design choices:*
- **Transient URL flag, not a saved preference.** `global_search=1` lives only in the URL query string and is never stored in `UserProfile.search_preferences`. Bundle-scoped search is the natural default; global search is a deliberate, per-search override.
- **Toggle rendered in the search container, not the bundle sidebar.** The search bar area is where users express search intent. Rendering the toggle adjacent to the search input (below it, visible only when a bundle is active) keeps all search-scoping controls together. This avoids the sidebar placement, which would require extra interaction to discover.
- **Navigating to a different bundle implicitly resets global search.** The existing bundle sidebar links (`?bundle=<id>`) do not carry forward `global_search`, so switching bundles naturally returns to bundle-scoped search — no explicit clear needed.

*Behavior* (numbered, testable invariants from the user's/consumer's view):

1. **Default — bundle search is scoped.** When a bundle is active and no `global_search` flag is set, results are filtered to bookmarks matching both the bundle's criteria and the search query, as today.
2. **Toggle appears only when a bundle is active.** The "Search everywhere" toggle/link is absent when no bundle is selected (`bundle` param absent or null). It appears (below the search input) when `bundle=<id>` is present in the URL.
3. **Activating global search bypasses the bundle filter.** When the user clicks the toggle (adding `global_search=1` to the URL), subsequent results come from all bookmarks matching the query — the bundle's tag/keyword filters are ignored. The bundle parameter remains in the URL.
4. **Global search is reflected in the URL.** The URL carries both `bundle=<id>` and `global_search=1` while in global mode, making the state bookmarkable and shareable.
5. **The tag cloud updates to reflect global search scope.** When `global_search=1` is active, the tag cloud shows tags from all matching bookmarks, not just bundle-scoped ones.
6. **The toggle shows the active state.** The toggle visually differentiates its active state (global search on) from its inactive state (bundle-scoped), so the user can tell which mode is active.
7. **Deactivating returns to bundle-scoped search.** When the toggle is clicked again (removing `global_search=1` from the URL), results return to bundle-scoped.
8. **Navigating to a different bundle clears global search.** The existing bundle sidebar links use `?bundle=<id>`, which drops `global_search`. Clicking a different bundle always starts in bundle-scoped mode.
9. **No bundle selected — `global_search` is ignored.** If `global_search=1` is present in the URL but `bundle` is absent or resolves to null, `global_search` has no effect (there is no bundle to bypass).
10. **Global search has no effect on the `archived` and `shared` views.** The feature applies to the active bookmarks view (`/`) and the archived view (`/archived`); both already pass `search` through the same `_base_bookmarks_query` pathway so the fix applies uniformly, but the shared view is not in scope (it has no bundle sidebar).

== TECH ==

*Context:* (files commit-pinned to `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`)

- `bookmarks/models.py @ fdd4234` — `BookmarkSearch` (line 224): a plain Python class (not a Django model) representing the active search parameters. It holds `params`, `defaults`, `preferences`, `from_request`, and `query_params`. The `bundle` param (default `None`) holds a `BookmarkBundle` instance resolved from the URL's `bundle=<id>` value.
- `bookmarks/queries.py @ fdd4234` — `_base_bookmarks_query` (line 227): applies `_filter_bundle(query_set, search.bundle)` when `search.bundle` is truthy (line 268–270). `_filter_bundle` (line 176) applies the bundle's search terms, any/all/excluded tag filters, and unread/shared filters.
- `bookmarks/queries.py @ fdd4234` — `query_bookmark_tags` (line 308): calls `query_bookmarks`, which calls `_base_bookmarks_query`. Because tags come from the bookmark queryset, bypassing the bundle filter in `_base_bookmarks_query` automatically scopes the tag cloud to all results.
- `bookmarks/forms.py @ fdd4234` — `BookmarkSearchForm` (line 248): renders non-editable modified params as `HiddenInput` so they survive form submissions (line 302–303). This is the mechanism that keeps `bundle` in the URL when a search query is typed. The same mechanism will carry `global_search` forward.
- `bookmarks/templates/bookmarks/search.html @ fdd4234` — search container template: renders the `ld-search-autocomplete` component and a `{% for hidden_field in search_form.hidden_fields %}` block (line 14) that serializes all modified non-editable search params. The toggle belongs here, rendered conditionally on `search.bundle`.
- `bookmarks/templates/bookmarks/bundle_section.html @ fdd4234` — bundle sidebar: uses `<a href="?bundle={{ bundle.id }}">` (line 29) — bare links that drop all other params, including `global_search`. No change needed here.
- `bookmarks/views/bookmarks.py @ fdd4234` — `index` view (line 43): builds `BookmarkSearch.from_request`, constructs `BookmarkListContext` and `ActiveTagCloudContext` from the same `search` object.

*Design alternatives:*

- **Toggle placement: search bar area vs. bundle sidebar vs. search preferences dropdown.**
  - Search bar area (chosen): co-locates with the search input, visible and actionable at a glance. Consistent with how other search-scoping controls (sort, shared, unread) are nearby.
  - Bundle sidebar: requires the user to look away from the search area; the sidebar link pattern (`?bundle=<id>`) doesn't naturally support a secondary toggle without additional templating.
  - Search preferences dropdown: hidden behind a click; more appropriate for persistent preferences. Global search is transient, not a preference.

- **UI control: anchor/link vs. checkbox vs. form input.**
  - Anchor link (chosen): consistent with the existing bundle sidebar link pattern (`<a href="?bundle={{ bundle.id }}">`). No JavaScript needed. The toggle URL is built in the template using `search.query_params` with `global_search` added or removed. Active state is styled with a CSS class.
  - Checkbox: would require a form submission. Inconsistent with how bundle selection works (direct navigation).
  - Lit web component: unnecessary complexity for a one-param toggle.

- **Persistence: transient URL flag vs. saved preference.**
  - Transient URL flag (chosen): bundle scoping is the natural, expected behavior. Persisting global search would mean a user returning to their favorites homepage would unexpectedly see all bookmarks — violating the purpose of the bundle. Global search is an intentional override, not a default.
  - Saved preference: would require `global_search` in `BookmarkSearch.preferences` and `UserProfile.search_preferences`; more intrusive change with undesirable default-state implications.

- **Clearing global_search when bundle is deselected: explicit clear vs. rely on link behavior.**
  - Rely on existing link behavior (chosen): the bundle sidebar links are `?bundle=<id>` with no `global_search`, which naturally drops it. No additional logic needed.
  - Explicit clear in the view: adds complexity without benefit since the URL already handles it.

*Proposed changes:*

1. **`bookmarks/models.py`** — add `global_search` to `BookmarkSearch`:
   - Add `"global_search"` to `params` list (after `"bundle"`).
   - Add `"global_search": False` to `defaults`.
   - Add `global_search: bool = None` parameter to `__init__`; assign `self.global_search = global_search if global_search is not None else self.defaults["global_search"]`.
   - `from_request`: in the existing loop over `BookmarkSearch.params`, the `value = query_dict.get(param)` call will pick up `global_search=1` from the URL. Add a type coercion: after the loop, convert `global_search` to bool (truthy string `"1"` → `True`, absent/`"0"` → `False`). Simplest: check `initial_values.get("global_search")` and set it to `bool(int(value))` or just `value == "1"`.
   - `query_params`: the existing `query_params` property serializes modified params. For `global_search`, the value must serialize as `"1"` (truthy) or be omitted (falsy/default). Since `global_search=False` is the default, `is_modified` returns False when it's False, so it's naturally omitted. When True (`is_modified` returns True), `query_params` will include `"global_search": True`. The URL-encode of `True` is `"True"` — override serialization in `query_params` to emit `1` for bool True. OR: store as string `"1"` internally (simplest, matches the URL's `"1"`).
   - Cleanest approach: store `global_search` as `True`/`False` bool in `__init__`, and in `query_params` add a special case: `if isinstance(value, bool): query_params[param] = "1" if value else "0"` (or omit when false since default is False and `is_modified` handles it).
   - `from_request`: coerce the string `"1"` → `True` when building `initial_values`.

2. **`bookmarks/queries.py`** — bypass bundle filter when `global_search` is set:
   - In `_base_bookmarks_query`, change the bundle filter condition from:
     ```python
     if search.bundle:
         query_set = _filter_bundle(query_set, search.bundle)
     ```
     to:
     ```python
     if search.bundle and not search.global_search:
         query_set = _filter_bundle(query_set, search.bundle)
     ```
   - No other change to queries.py.

3. **`bookmarks/templates/bookmarks/search.html`** — render the "Search everywhere" toggle:
   - After the closing `</form>` tag (line 15) and before the `<ld-dropdown>` for search preferences (or inside the `search-container`), add a conditional block:
     ```html
     {% if bookmark_list.search.bundle %}
       <div class="global-search-toggle">
         {% if bookmark_list.search.global_search %}
           <a href="?{{ bookmark_list.search|query_params_without:'global_search' }}" class="btn btn-sm active">All bookmarks</a>
         {% else %}
           <a href="?{{ bookmark_list.search|query_params_with:'global_search=1' }}" class="btn btn-sm">Search everywhere</a>
         {% endif %}
       </div>
     {% endif %}
     ```
   - **Implementation note**: the template needs a way to add/remove `global_search` from `search.query_params`. The cleanest approach is to add two Django template filters to the `shared` template tag library (`bookmarks/templatetags/shared.py` or a similar tags file):
     - `query_params_without`: takes a `BookmarkSearch` and a param name, returns the URL-encoded query string with that param removed.
     - `query_params_with`: takes a `BookmarkSearch` and a `key=value` string, returns the URL-encoded query string with that param added/overridden.
   - Alternatively, build the toggle URLs in the view layer (in `BookmarkListContext`) and expose them as template context variables. This is simpler for templates. Add `global_search_on_url` and `global_search_off_url` to `BookmarkListContext` (computed from `search.query_params`).
   - **Chosen approach**: compute toggle URLs in `BookmarkListContext` (contexts.py), exposing `search_everywhere_url` (the URL that adds `global_search=1`) and `back_to_bundle_url` (the URL that removes it). The template uses these directly without custom filters. This is consistent with how `return_url` and `action_url` are already computed in the context.

4. **`bookmarks/views/contexts.py`** — add toggle URLs to `BookmarkListContext`:
   - In `BookmarkListContext.__init__`, after building `search`, compute:
     ```python
     if search.bundle:
         params_with_global = {**search.query_params, "global_search": "1"}
         params_without_global = {k: v for k, v in search.query_params.items() if k != "global_search"}
         self.search_everywhere_url = request_context.index_url + "?" + urllib.parse.urlencode(params_with_global)
         self.back_to_bundle_url = request_context.index_url + "?" + urllib.parse.urlencode(params_without_global) if params_without_global else request_context.index_url
     else:
         self.search_everywhere_url = None
         self.back_to_bundle_url = None
     ```
   - These URLs are then used in `search.html`: show the "Search everywhere" link (pointing to `search_everywhere_url`) when `not search.global_search`, or the "Back to bundle" link (pointing to `back_to_bundle_url`) when `search.global_search` is True.

5. **`bookmarks/templates/bookmarks/search.html`** — simpler version using context URLs:
   ```html
   {% if bookmark_list.search.bundle %}
     <div class="global-search-toggle">
       {% if bookmark_list.search.global_search %}
         <a href="{{ bookmark_list.back_to_bundle_url }}" class="btn btn-link btn-sm">Bundle scope</a>
       {% else %}
         <a href="{{ bookmark_list.search_everywhere_url }}" class="btn btn-link btn-sm">Search everywhere</a>
       {% endif %}
     </div>
   {% endif %}
   ```

*Open questions resolved:*

- **Should `global_search` be a preference?** No — transient URL flag only. Persisting it would break the bundle-as-homepage use case. Settled from the ticket's acceptance criteria ("reflected in the URL...bookmarkable").
- **Should navigating to a different bundle preserve `global_search`?** No — the existing bundle links use bare `?bundle=<id>` which drops it. This is the correct behavior per acceptance criteria ("Navigating to a different bundle clears the global search flag"). No code change needed.
- **Does the API need to support `global_search`?** Out of scope for this ticket. The REST API has its own search endpoint that does not use `BookmarkSearch.from_request`; the `global_search` param in `BookmarkSearch` is only wired through the web UI path.
- **What about the `archived` view?** `archived` view uses the same `_base_bookmarks_query` pathway; the change to `queries.py` applies there automatically. The template change in `search.html` uses `bookmark_list.search.bundle`, so the toggle appears on the archived view too when a bundle is active.
- **`global_search` serialization in `query_params`**: store as bool `True`/`False`; in the `query_params` property, serialize as `"1"` when True (so URL reads `global_search=1`). `from_request` coerces `"1"` → `True`. Default `False` means `is_modified()` returns `False` → not emitted in `query_params` or hidden fields unless explicitly True. This keeps the URL clean when global search is off.

*Validation & verification criteria* (must ALL pass before merge):

1. **Backend — bundle filter bypassed when `global_search=True`.** `BookmarkSearch(bundle=bundle, global_search=True)` passed to `queries.query_bookmarks()` returns all non-archived bookmarks matching the search query, not just those in the bundle. Checked by new test `test_query_bookmarks_global_search_ignores_bundle_filter` in `bookmarks/tests/test_queries.py` — must fail before the change, pass after.

2. **Backend — bundle filter still applied when `global_search=False` (regression).** `BookmarkSearch(bundle=bundle, global_search=False)` (or `global_search` absent) still scopes results to the bundle. Verified by the existing bundle query tests (lines 1293–1500 in `test_queries.py`) passing without modification.

3. **Model — `global_search` round-trips through `from_request`.** `BookmarkSearch.from_request(request, QueryDict("bundle=1&global_search=1"))` returns a `BookmarkSearch` with `global_search=True`. `BookmarkSearch.from_request(request, QueryDict("bundle=1"))` returns `global_search=False`. Checked by new test in `bookmarks/tests/test_bookmark_search_model.py`.

4. **Model — `global_search=True` appears in `query_params` as `"1"`.** `BookmarkSearch(bundle=bundle, global_search=True).query_params` includes `{"global_search": "1", "bundle": bundle.id}`. Checked by extending the `test_query_params` test in `test_bookmark_search_model.py`.

5. **Model — `global_search=False` is not emitted in `query_params`.** `BookmarkSearch(bundle=bundle, global_search=False).query_params` does NOT include `global_search`. Checked by the same test extension.

6. **Tag cloud — updates to global scope when `global_search=True`.** When `global_search=True`, `query_bookmark_tags` returns tags from all matching bookmarks, not just those in the bundle. Checked by the same test that covers criterion 1 (tags query uses the same search object).

7. **UI — toggle renders only when a bundle is active.** With a bundle selected (`?bundle=<id>&q=python`), the rendered HTML includes the "Search everywhere" link. Without a bundle (`?q=python`), it is absent. Checked by a view test in `bookmarks/tests/test_bookmarks_index_view.py` (or similar) that asserts presence/absence of the toggle element.

8. **UI — active state shown when `global_search=1`.** With `?bundle=<id>&global_search=1`, the toggle renders the "Bundle scope" (back) link, not the "Search everywhere" link. Checked by the same view test.

9. **No regression — existing search form hidden fields still carry bundle param.** When a bundle is active and the user submits a search query, `bundle=<id>` is preserved in the submitted URL. Checked by existing view tests for search with a bundle.

10. **Validation gate passes.** `make lint && make test` exits 0 on the final branch.

Co-Authored-By: Oz <oz-agent@warp.dev>
