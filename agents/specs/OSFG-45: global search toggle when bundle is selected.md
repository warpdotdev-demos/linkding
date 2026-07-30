*Spec: Global search toggle when a bundle is selected (OSFG-45)*

== PRODUCT ==

*Summary:* When a bundle is selected as the active view, the search bar currently scopes results to bookmarks matching the bundle's filters. Many users set a bundle (e.g. "favorites") as their homepage and find it tedious to navigate away just to search across all bookmarks. This feature adds a "Search all bookmarks" toggle link that lets users search globally without leaving the bundle view.

*Key design choices:*
1. The toggle is a plain HTML link (no JavaScript) placed below the search bar in `search.html`, visible only when a bundle is selected — so it is always reachable, including on mobile where the side panel is hidden.
2. The `bundle` param is kept in the URL even when global search is active, so the selected bundle stays highlighted in the side panel and users retain context for where they came from.
3. `global_search` is stored as a string (`""` = off / `"1"` = on) consistent with existing string-based filter constants in `BookmarkSearch`.

*Behavior* (numbered, testable invariants from the user's view):

1. When no bundle is selected, the search bar behaves exactly as today — no toggle link appears, and no behavioral change.
2. When a bundle is selected (the `bundle` query param is set), a "Search all bookmarks" link appears below the search bar.
3. Clicking "Search all bookmarks" adds `global_search=1` to the URL (preserving `bundle=<id>` and any current search query `q=...`). The result set shows all the user's bookmarks (not scoped to the bundle) that match the query.
4. While `global_search=1` is active and a bundle is selected, the toggle link changes to "Search in bundle" (or equivalent), allowing the user to return to bundle-scoped results.
5. While `global_search=1` is active, the selected bundle remains highlighted in the side panel — the `bundle` param is still in the URL.
6. When the user types a new query and submits the search form while `global_search=1` is active, `global_search=1` is preserved in the resulting URL (it is a hidden field in the search form, preserved by the POST→redirect flow in `search_action`).
7. Clicking a different bundle in the side panel (which sets a new `bundle=<id>` with no `global_search`) reverts to bundle-scoped results for the new bundle. Clicking the same bundle link in the side panel also clears `global_search`.
8. The toggle link does not carry a `page` query param, so switching between global and bundle-scoped views resets to page 1.
9. The feature works on both the active (index) view and the archived view.
10. The tag cloud reflects the global-search scope when `global_search=1` — it shows tags from all matching bookmarks, not only bundle members, because `query_bookmark_tags` uses the same `_base_bookmarks_query`.
11. When `global_search=1` and no search query is active (`q=""`), all of the user's bookmarks are returned (the bundle filter is the only thing being bypassed; other standard filters — unread, shared, sort — still apply).

== TECH ==

*Context:*

- `BookmarkSearch` — `bookmarks/models.py:224-343 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`: A plain Python class (not a Django model) that holds all active search parameters. `params` is the canonical list of URL params; `defaults` maps each to its default value. `is_modified(param)` returns `True` when the value differs from the default. `query_params` returns only modified params (used to build redirect URLs). `from_request` factory reads `params` from a `QueryDict` and handles the `bundle` param specially (resolves to a `BookmarkBundle` model instance). Non-standard params (e.g. a new bool field) need explicit handling in `__init__` and in the `from_request` loop if they need type coercion.

- `_base_bookmarks_query` — `bookmarks/queries.py:227-305 @ fdd4234`: Applies all search filters. Line 269-270 applies `_filter_bundle(query_set, search.bundle)` when `search.bundle` is set. `_filter_bundle` applies the bundle's search terms, any/all/excluded tag filters, and unread/shared state filters. Skipping this call when `global_search=True` is the entire backend change.

- `BookmarkSearchForm` — `bookmarks/forms.py:248-303 @ fdd4234`: Declares an explicit form field per param. In `__init__`, iterates over `search.params` to set initial values and mark non-editable modified params as `HiddenInput`. The `{% for hidden_field in search_form.hidden_fields %}{{ hidden_field }}{% endfor %}` in `search.html` renders these as hidden `<input>` tags, preserving state across form submissions. Adding a new `global_search = forms.CharField(required=False)` field will slot in automatically.

- `bookmark_search` inclusion tag — `bookmarks/templatetags/bookmarks.py:9-28 @ fdd4234`: Builds the template context for `search.html`. Returns `search`, `search_form`, `preferences_form`, `request`, `app_version`, and `mode`. This is the right place to compute and inject the toggle URLs.

- `search.html` — `bookmarks/templates/bookmarks/search.html @ fdd4234`: Renders the search input (via `<ld-search-autocomplete>`), a search preferences dropdown, and hidden fields. The toggle link block should be added after the `</div>` closing the `.search-container`, inside the overall container, conditionally on `search.bundle`.

- `bundle_section.html` — `bookmarks/templates/bookmarks/bundle_section.html @ fdd4234`: Renders the list of bundles in the side panel; `selected` class is added when `bundle.id == bundles.selected_bundle.id`. No changes needed here — the bundle stays highlighted because `bundle` remains in the URL.

*Design alternatives:*

- **Toggle placement — side panel (`bundle_section.html`) vs. search bar area (`search.html`)**:
  The side panel uses the `hide-md` CSS class, making it hidden on mobile viewports. Placing the toggle only there would make it inaccessible to mobile users. Placing it below the search bar in `search.html` ensures it is always visible, consistent with the proximity principle (the user is about to type a search query). Chosen: `search.html`.

- **URL param representation — boolean `True/False` vs. string `"1"/""`**:
  A Python boolean in `query_params` serializes as the string `"True"` via `urlencode`, requiring special round-trip handling in `from_request`. Using a string `"1"` (on) / `""` (off, the default) is consistent with how `shared` and `unread` already use string constants, requires no special serialization, and the existing `if value:` guard in `from_request` handles presence/absence correctly. Chosen: string `"1"` / default `""`.

- **Remove `bundle` from URL when global search is activated (clean URL) vs. keep it**:
  Removing the bundle param produces a cleaner URL but loses the visual "you are in the favorites bundle" context and makes it impossible to toggle back to bundle-scoped search without re-selecting the bundle. Keeping both params (chosen) preserves context and makes the toggle reversible.

- **Toggle implementation — `<a>` link vs. checkbox/form button**:
  A form checkbox or `<button type="submit">` toggle requires either JavaScript for dynamic URL rewriting or a server round-trip with a POST→redirect. A plain `<a>` link (chosen) requires no JS, is bookmarkable, and is consistent with how bundle navigation links work in the side panel.

*Proposed changes:*

1. `bookmarks/models.py` — `BookmarkSearch`:
   - Add `"global_search"` to the `params` list.
   - Add `"global_search": ""` to the `defaults` dict.
   - Add `global_search: str = None` parameter to `__init__`.
   - Assign `self.global_search = global_search or self.defaults["global_search"]`.

2. `bookmarks/queries.py` — `_base_bookmarks_query`:
   - Change the bundle filter block at line 269 from:
     ```python
     if search.bundle:
         query_set = _filter_bundle(query_set, search.bundle)
     ```
     to:
     ```python
     if search.bundle and not search.global_search:
         query_set = _filter_bundle(query_set, search.bundle)
     ```

3. `bookmarks/forms.py` — `BookmarkSearchForm`:
   - Add `global_search = forms.CharField(required=False)` field declaration.

4. `bookmarks/templatetags/bookmarks.py` — `bookmark_search` tag:
   - Compute `global_search_on_url` and `global_search_off_url` from `request.GET`:
     - `global_search_on_url`: copy GET params, set `global_search=1`, remove `page`.
     - `global_search_off_url`: copy GET params, remove `global_search` and `page`.
   - Add both to the returned context dict.

5. `bookmarks/templates/bookmarks/search.html`:
   - Add a conditional block after the `.search-container` div, rendered only when `search.bundle` is set:
     - If `search.global_search` is truthy: show "Search in bundle" link pointing to `global_search_off_url`.
     - Otherwise: show "Search all bookmarks" link pointing to `global_search_on_url`.

*Open questions resolved:*

- **Toggle placement** — `search.html` (always visible, including mobile). Bundle section unchanged.
- **Bundle param removed on toggle?** — No. `bundle` stays in the URL so the selected bundle remains highlighted and the toggle is reversible.
- **Pagination on toggle** — Toggle link strips `page` param; results start at page 1 when scope changes.
- **Tag cloud scope** — Follows global search automatically because `query_bookmark_tags` calls `_base_bookmarks_query` with the same `search` object.
- **Form submission preserves global_search?** — Yes. The new `global_search` form field becomes a hidden field when modified, included in POST data, and preserved by `search_action`'s redirect.
- **Global search when no bundle?** — `global_search=1` with no bundle has no visible toggle and no behavioral effect (the bundle filter was never applied). The param is technically silently accepted but produces results identical to the default.
- **Shared view** — No specific support needed. The shared view does not show bundles and does not call `_filter_bundle`, so the change is inert there.

*Validation & verification criteria* (must ALL pass before merge):

1. **Regression test — query layer (new):** In `bookmarks/tests/test_queries.py`, add `test_query_bookmarks_global_search_bypasses_bundle_filter`: create a bundle with a tag filter (e.g. `any_tags="bundleTag"`); create one bookmark matching the bundle and one that doesn't; with `BookmarkSearch(q="", bundle=<bundle>, global_search="1")`, call `queries.query_bookmarks` and assert both bookmarks are returned; with `global_search=""`, assert only the bundle-matching bookmark is returned. Command: `uv run pytest bookmarks/tests/test_queries.py::QueriesBasicTestCase -n auto`. Verifies behavior invariants #3, #10.

2. **Regression test — archived view (new):** In `bookmarks/tests/test_queries.py`, add `test_query_archived_bookmarks_global_search_bypasses_bundle_filter`: same logic for `queries.query_archived_bookmarks`. Command: same. Verifies behavior invariant #9.

3. **Unit test — model parsing (new):** In `bookmarks/tests/test_bookmark_search_model.py`, add `test_from_request_global_search`: with `QueryDict("global_search=1")`, assert `search.global_search == "1"`; with `QueryDict("")`, assert `search.global_search == ""`; verify `query_params` includes `{"global_search": "1"}` for the first case and excludes `global_search` for the second. Command: `uv run pytest bookmarks/tests/test_bookmark_search_model.py -n auto`. Verifies invariant #3 at the model layer and correct URL serialization.

4. **Unit test — form hidden field (new):** In `bookmarks/tests/test_bookmark_search_form.py`, add `test_global_search_hidden_field`: with `BookmarkSearch(global_search="1")`, create a `BookmarkSearchForm`, assert `"global_search"` is in `form.hidden_fields()`. Command: `uv run pytest bookmarks/tests/test_bookmark_search_form.py -n auto`. Verifies behavior invariant #6 (form preserves state).

5. **No regression — no-bundle case:** `BookmarkSearch().query_params` must not include `global_search`; `BookmarkSearch(q="foo").query_params` must not include `global_search`. Covered by test #3 above plus full suite gate.

6. **No regression — existing bundle tests pass:** All `test_query_bookmarks_with_bundle_*` tests in `bookmarks/tests/test_queries.py` must still pass (they use `global_search=""` by default). Covered by validation gate.

7. **Validation gate:** `make lint && make test` passes with no errors. This runs `ruff check` and the full pytest suite. Command: `make lint && make test` from repo root.

8. **UI verification (computer use):** Start the dev server (`make serve-bg`), log in, create a bundle with a tag filter, navigate to `/?bundle=<id>`, confirm "Search all bookmarks" link is visible below the search bar; click it, confirm URL contains `global_search=1` and `bundle=<id>`, results include bookmarks outside the bundle; confirm "Search in bundle" link is now visible; click it, confirm `global_search` is removed from URL and results are scoped back to the bundle. Captures screenshot proof as required by `factory-verification` for user-facing changes.

Co-Authored-By: Oz <oz-agent@warp.dev>
