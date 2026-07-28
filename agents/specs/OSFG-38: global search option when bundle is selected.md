*Spec: Global search option when a bundle is selected (OSFG-38)*

== PRODUCT ==
*Summary:* When a bundle is selected, linkding currently restricts all bookmark searches to that bundle's scope. This feature adds a global search toggle so users can search across all bookmarks without leaving their bundle view — critical for users who set a bundle (e.g. "Favorites") as their homepage.

*Key design choices:* (1) **Transient URL param** `global_search=1` rather than a saved user preference — consistent with other search params and avoids persisting a mode the user must consciously exit. (2) **Toggle in the search container** (`search.html`), rendered as a link adjacent to the search input — minimal DOM footprint, no new UI components. (3) **Labels "Search all bookmarks" / "↩ [bundle name]"** communicate the current scope; the active bundle stays highlighted in the sidebar throughout.

*Behavior* (numbered, testable invariants):
1. **No bundle selected** — no global search toggle is shown; all search behavior is unchanged.
2. **Bundle selected, global search off** (default) — a "Search all bookmarks" link appears in the search area. Bookmark results and tag cloud are scoped to the bundle.
3. **User clicks "Search all bookmarks"** — URL gets `global_search=1` added (and `page` reset/stripped). Results include all matching bookmarks regardless of bundle membership. Tag cloud reflects all matching tags across all bookmarks.
4. **Bundle selected, global search on** — the toggle changes to "↩ [bundle name]" (a back-link). The active bundle remains visually highlighted in the sidebar.
5. **User clicks "↩ [bundle name]"** — `global_search` is removed from the URL. Results revert to bundle-scoped view. The `bundle` param is preserved.
6. **User types a new query while global search is active** — `global_search=1` is preserved via a hidden field in the search form; results remain global.
7. **Archived and shared bookmark pages** — no global search toggle is shown (bundle selection is not supported on those views).
8. **`global_search=1` without a bundle param in the URL** — treated as a no-op: no toggle shown, no behavioral change vs. the no-bundle case.

== TECH ==
*Context:*
- `bookmarks/queries.py:_base_bookmarks_query() @ 30510d3` — single point of bundle filtering. When `search.bundle` is set, calls `_filter_bundle(query_set, search.bundle)` at line 269–270. The same `search` object passes through `query_bookmark_tags → query_bookmarks → _base_bookmarks_query`, so bypassing the bundle guard there automatically makes the tag cloud global too.
- `bookmarks/models.py:BookmarkSearch @ 30510d3` (line 224–343) — holds all search params. `params` list (line 238–247) drives `from_request` (line 328–343), `query_params`, and `modified_params`. Params in `preferences` list (line 248) are saved as user defaults; non-preference modified params round-trip as hidden form inputs.
- `bookmarks/forms.py:BookmarkSearchForm @ 30510d3` (line 248–303) — renders non-editable modified params as `HiddenInput` widgets (line 302–303). Any new param added to `BookmarkSearch.params` with a non-default value is automatically serialised into form submissions without further template changes.
- `bookmarks/templatetags/bookmarks.py:bookmark_search() @ 30510d3` (line 12–27) — inclusion tag that populates the context for `search.html`. The computed URL helpers (`global_search_url`, `bundle_search_url`) must be added here and passed to the template.
- `bookmarks/templates/bookmarks/search.html @ 30510d3` — renders the search input and preferences dropdown. The toggle block is inserted after the hidden fields loop.

*Design alternatives:*
- **Persistence — transient URL param vs. saved user preference:** A saved preference would persist across sessions but requires a DB migration and a settings-page entry. A transient URL param is consistent with all other search params (`q`, `bundle`, `sort`, etc.), avoids unexpected sticky state, and needs no migration. **Transient URL param chosen.**
- **Toggle placement — search container vs. preferences dropdown vs. header pill:** The preferences dropdown is for sort/shared/unread settings and would bury this context-critical control. A header pill requires a new UI component. A simple link in the search container (`search.html`) is the lowest-footprint option and is immediately visible when bundle context is active. **Search container link chosen.**
- **Tag cloud scope — also global vs. remain bundle-scoped:** Keeping the tag cloud bundle-scoped while results are global would require a separate `search` object for the tag cloud, adding complexity. Since the tag cloud derives from `query_bookmark_tags → _base_bookmarks_query`, bypassing the bundle guard there naturally propagates. **Tag cloud also goes global when `global_search=1`, chosen.**
- **URL construction — template tag vs. template filter vs. inline template logic:** Computing `global_search_url` / `bundle_search_url` in the `bookmark_search` template tag keeps template logic clean and testable (the tag context dict is exercisable in unit tests). **Template tag URL computation chosen.**

*Proposed changes:*
1. **`bookmarks/models.py` — `BookmarkSearch`:** Add `"global_search"` to the `params` list; add `"global_search": ""` to `defaults` (empty string = off, `"1"` = on). Do NOT add to `preferences` — this is not a saved setting.
2. **`bookmarks/queries.py` — `_base_bookmarks_query()`:** Change the bundle filter guard from `if search.bundle:` to `if search.bundle and not search.global_search:` (one-line change at line 269).
3. **`bookmarks/forms.py` — `BookmarkSearchForm`:** Add `global_search = forms.CharField(required=False)` so it is included in `hidden_fields()` serialisation when the param is modified (preserving `global_search=1` across form submissions).
4. **`bookmarks/templatetags/bookmarks.py` — `bookmark_search()`:** Compute and inject `global_search_url` and `bundle_search_url` into the template context:
   - `global_search_url`: current query params + `global_search=1`, with `page` removed.
   - `bundle_search_url`: current query params − `global_search`, with `page` removed.
5. **`bookmarks/templates/bookmarks/search.html`:** After the `{% for hidden_field … %}` block, insert a conditional toggle block:
   - If `search.bundle` and not `search.global_search`: render `<a href="{{ global_search_url }}">Search all bookmarks</a>`
   - Elif `search.bundle` and `search.global_search`: render `<a href="{{ bundle_search_url }}">↩ {{ search.bundle.name }}</a>`
   - Otherwise: render nothing.

*Open questions resolved:*
- **Persistence?** Transient URL param — aligns with existing search params, no DB migration needed.
- **Toggle placement?** In `search.html`'s search container, as a plain link.
- **Scope labels?** "Search all bookmarks" (inactive) / "↩ [bundle name]" (active) — minimal and self-explanatory.
- **Tag cloud scope?** Also global — naturally follows the single filter bypass; no separate `search` object needed.
- **Archived/shared pages?** Toggle not shown — bundle param is not surfaced on those views.
- **`global_search=1` with no bundle?** No-op — the guard `if search.bundle and not search.global_search:` means the bundle filter was already inactive, so behaviour is unchanged.

*Validation & verification criteria* (must ALL pass before merge):
1. **No toggle without bundle** (behavior #1): `GET /?q=test` (no `bundle` param) — response HTML contains neither "Search all bookmarks" nor any "↩" back-link. Checked by: `test_global_search_ui_toggle_visibility` in `bookmarks/tests/test_bookmark_index_view.py`.
2. **Toggle appears when bundle selected** (behavior #2): `GET /?bundle=<id>` (valid bundle, no `global_search`) — response HTML contains "Search all bookmarks" link and results are bundle-scoped. Checked by: `test_global_search_ui_toggle_visibility`.
3. **Global search bypasses bundle filter** (behavior #3): `GET /?bundle=<id>&global_search=1` — bookmarks outside the bundle appear in results. Checked by: `test_global_search_ignores_bundle_filter` in `bookmarks/tests/test_bookmark_search_model.py` (new failing-then-passing test).
4. **Tag cloud also global** (behavior #3): With `global_search=1` and a bundle selected, tag cloud includes tags from bookmarks outside the bundle. Checked by: `test_global_search_tag_cloud_shows_all_tags` in `bookmarks/tests/test_bookmark_index_view.py`.
5. **Back-link label** (behavior #4): `GET /?bundle=<id>&global_search=1` where the bundle is named "Favorites" — response HTML contains "↩ Favorites". Checked by: `test_global_search_ui_toggle_visibility`.
6. **State preserved across form submit** (behavior #6): `BookmarkSearch.from_request` with `global_search=1` — `BookmarkSearchForm.hidden_fields()` contains a hidden input `name="global_search" value="1"`. Checked by: `test_global_search_preserved_in_search_form` in `bookmarks/tests/test_bookmark_search_model.py`.
7. **No-op without bundle** (behavior #8): `BookmarkSearch.from_request` with `global_search=1` and no `bundle` — `search.bundle` is `None` and the query returns all user bookmarks (identical to the baseline with no params). Checked by: `test_global_search_no_bundle_is_noop` in `bookmarks/tests/test_bookmark_search_model.py`.
8. **No regression — existing bundle-scoped behavior unchanged**: `GET /?bundle=<id>` without `global_search` — results and tag cloud are still bundle-scoped (existing behavior preserved). Confirmed by: full validation gate `make lint && make test` (all baseline tests pass).
9. **Validation gate passes**: `make lint && make test` exits 0 with 0 failures.
10. **Visual proof** (user-facing change — computer-use required): Exercise the running UI and capture screenshots confirming: (A) bundle selected → "Search all bookmarks" link visible; (B) after clicking the link → all bookmarks visible, toggle shows "↩ [bundle name]", bundle still highlighted in sidebar; (C) after clicking back-link → bundle-scoped results restored, original toggle back. Screenshots attached to the PR and task record.

Co-Authored-By: Oz <oz-agent@warp.dev>
