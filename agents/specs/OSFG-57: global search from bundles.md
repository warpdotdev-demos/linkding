*Spec: Global search from a selected bundle (OSFG-57)*

== PRODUCT ==

*Summary:* Users commonly keep a small “favorites” bundle open as their homepage. Today, any search performed while that bundle is selected is constrained by the bundle, so finding an item elsewhere requires leaving the bundle. Add a visible, reversible search-scope control that temporarily searches beyond the selected bundle without losing the bundle, query, or other search context.

*Key design choices:*
- **Use a transient URL override.** The canonical state is `global_search=1`; it is not a saved user preference. Bundle scope remains the default every time a bundle is selected.
- **Keep the bundle selected.** Global mode bypasses only the bundle’s saved filters. The URL retains `bundle=<id>` so the UI can show the bundle context and switch back without reconstructing it.
- **Put the control in the visible search control group.** On active and archived bookmark pages, show an anchor-style two-state action immediately after the search field and before the search-preferences button. Visible copy is **“All bookmarks”** in bundle-scoped mode and **“This bundle”** in global mode; accessible labels are **“Search all bookmarks”** and **“Search only this bundle”**.
- **Bypass the bundle centrally.** All bookmark-list and tag-cloud query paths that use `BookmarkSearch` receive the same scope decision, while owner, view, sharing, archive, query, and explicit search-preference filters remain enforced.

*Behavior* (numbered, testable invariants):

1. With no valid bundle selected, search behaves exactly as it does on `master`: no scope control is rendered, `global_search` is false, and text, tag, special-keyword, sort, shared, unread, user, and date filters keep their current behavior.
2. With a valid bundle selected and no global override, the bookmark list and tag cloud remain constrained by the bundle’s saved search, any/all/excluded tags, unread filter, and shared filter.
3. On the active and archived bookmark pages, a selected bundle renders a keyboard-focusable anchor action in the search control group, immediately after the search field and before the search-preferences button. Its scoped-mode copy is “All bookmarks” with accessible label “Search all bookmarks.”
4. Activating “All bookmarks” navigates on the current view route and adds `global_search=1`. It retains the valid `bundle`, `q`, `sort`, `shared`, `unread`, `modified_since`, and `added_since` state, but resets transient `page` and `details` state so the new result set starts on page 1 without an unrelated details modal.
5. In global mode, only the selected bundle’s filters are skipped. The active/archived/shared view boundary, bookmark owner or public-sharing constraints, text and `#tag` expressions, advanced Boolean expressions, `!untagged`, `!unread`, explicit `shared=yes|no`, explicit `unread=yes|no`, sort, user, and date filters continue to apply.
6. The tag cloud is derived from the same globally scoped bookmark queryset. In global mode it includes tags from all results allowed by invariant 5, including out-of-bundle results; it never includes tags excluded by the current view or visibility boundary.
7. Global mode changes the visible action copy to “This bundle,” with accessible label “Search only this bundle” and a visually distinct active state. Activating it removes `global_search` while preserving the bundle, query, and other search parameters listed in invariant 4.
8. The search form and search-preferences form preserve `bundle` and an active `global_search=1` as hidden request state. Applying preferences keeps global mode for the current request. “Save as default” persists only the existing `BookmarkSearch.preferences` (`sort`, `shared`, `unread`), never `global_search` or `bundle`.
9. The URL is the source of truth: refresh and browser back/forward reproduce the displayed scope. `BookmarkSearch.query_params` serializes active global mode only as `"1"` and omits the default false state.
10. Only the exact query value `global_search=1` enables the override. Missing, empty, `0`, `true`, malformed, or repeated values that do not resolve to the final exact value `"1"` are false. If `bundle` is missing, invalid, or belongs to another user, global mode is normalized to false and is not preserved by generated URLs or forms.
11. Selecting another bundle uses the existing bare `?bundle=<id>` bundle link and therefore resets global mode (and the other prior search parameters that bundle navigation already resets). Clearing the bundle also removes global mode.
12. Archived bookmarks support the same control and semantics as active bookmarks, but “All bookmarks” means all *archived* bookmarks allowed by the remaining filters; global mode must never mix active and archived results.
13. Shared bookmarks have no bundle selector and do not expose the scope control in normal navigation. The shared query’s existing owner/public-sharing constraints remain mandatory. If an authenticated user manually supplies a valid owned `bundle` and `global_search=1`, the central query semantics may bypass that bundle, but they must not bypass sharing, selected-user, or public-only constraints.
14. “Untagged” is an active-bookmarks query (`q=!untagged`), not a separate view. In global mode it finds untagged bookmarks outside the bundle while retaining the active/archived boundary. `!shared` is not a supported search keyword on current `master`; shared-state regression coverage uses the existing `shared=yes|no` preference instead.
15. Search autocomplete, tag autocomplete, feeds, and the REST API retain their current contracts. `ld-search-autocomplete` currently calls the API without bundle state, so this change must not add `global_search` to its request or alter suggestion semantics; the control and list/tag-cloud behavior remain server-rendered web-UI concerns.
16. The control remains readable and operable at desktop and mobile widths without collapsing the search input, covering the preferences button, or creating horizontal overflow. Its visible label change and active styling must not be the sole accessibility signal; each state has the accessible label defined above.

== TECH ==

*Context researched:* `warpdotdev-demos/linkding` `origin/master` at `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` (2026-07-30 UTC).

- `bookmarks/models.py:224 @ fdd4234` — `BookmarkSearch` owns the request parameters, defaults, saved-preference subset, model-aware `query_params` serialization, and `from_request` parsing. `bundle` is resolved only from bundles owned by `request.user`.
- `bookmarks/forms.py:248 @ fdd4234` — `BookmarkSearchForm` mirrors every `BookmarkSearch.params` entry and turns modified non-editable parameters into hidden fields, which is how bundle and other state survive GET/POST search forms.
- `bookmarks/views/bookmarks.py:43 @ fdd4234` — active, archived, and shared views each parse one `BookmarkSearch`, then pass it to their bookmark-list and tag-cloud contexts. `search_action` rebuilds the redirect from `search.query_params`.
- `bookmarks/views/contexts.py:32 @ fdd4234` — `RequestContext` owns current-route URL generation and strips `details`; `BookmarkListContext` at line 197 builds the list, action/return URLs, pagination, and search state. Active, archived, and shared subclasses select their query path. Tag-cloud contexts reuse the same search.
- `bookmarks/queries.py:176 @ fdd4234` — `_filter_bundle` applies the bundle’s saved term/tag/unread/shared constraints. `_base_bookmarks_query` at line 227 applies owner, date, query, explicit unread/shared, bundle, and sort filters in sequence. `query_bookmarks`, `query_archived_bookmarks`, and `query_shared_bookmarks` add their view/visibility boundaries around that base. Tag queries at line 308 derive tags from the corresponding bookmark query.
- `bookmarks/templatetags/bookmarks.py:9 @ fdd4234` and `bookmarks/templates/bookmarks/search.html:1 @ fdd4234` — the inclusion tag creates the search and preferences forms; the template renders the search field, hidden state, and preferences dropdown.
- `bookmarks/templates/bookmarks/bundle_section.html:27 @ fdd4234` — bundle links are deliberately bare `?bundle=<id>` URLs, so selecting a bundle resets transient search state.
- `bookmarks/styles/bookmark-page.css:45 @ fdd4234` — `.search-container` is a flex control group with a 300px desktop maximum. Adding visible scope copy requires explicit responsive sizing so the search input remains usable.
- `bookmarks/frontend/components/search-autocomplete.js:137 @ fdd4234` — autocomplete requests carry mode, user, shared, unread, and query, but not bundle. This confirms autocomplete is a regression-smoke surface, not part of the new scope contract.

*Prior art:* Unmerged PR #14 (`factory/global-search-bundle-override`, OSFG-47) added a boolean `global_search`, bypassed `_filter_bundle`, generated two context URLs, and rendered “Search everywhere” / “Bundle scope.” It proved the central-query approach but is not shipped. It covered only active-page view assertions, did not cover archived/shared/untagged/filter regressions, did not normalize a global flag without a valid bundle, and inserted long copy into the existing fixed-width search group without a responsive style contract. This spec keeps the useful URL/query approach while closing those gaps; implementation must start from this OSFG-57 branch and current `master`, not merge or reuse PR #14.

*Design alternatives:*

- **Transient URL parameter (chosen) vs. saved preference.**
  - URL state is bookmarkable, works with refresh/back, and cannot make a favorites homepage unexpectedly open globally later.
  - A saved preference would require adding scope to `UserProfile.search_preferences` and could silently defeat the purpose of a bundle homepage. It is rejected.
- **Preserve `bundle` and bypass it (chosen) vs. remove `bundle` from the link.**
  - Preserving it retains selected-bundle context and provides a one-click return.
  - Removing it is simpler but is equivalent to navigating home, loses the context the requester wants to keep, and cannot render a reliable return action. It is rejected.
- **Same-route flag (chosen) vs. a separate global-search route.**
  - The same route reuses current active/archived/shared security and view boundaries and keeps generated links small.
  - A separate route duplicates view, context, action, and tag-cloud wiring and risks inconsistent filters. It is rejected.
- **Central `_base_bookmarks_query` condition (chosen) vs. per-view branching.**
  - The central condition keeps bookmark lists, tag clouds, actions, and all view types consistent and bypasses exactly `_filter_bundle`.
  - Per-view branching duplicates logic and can let a tag cloud disagree with its list. It is rejected.
- **Visible anchor action in the search group (chosen) vs. checkbox, sidebar action, or preferences-dropdown option.**
  - An anchor changes shareable GET state without JavaScript, is discoverable where the user searches, and supports browser navigation.
  - A checkbox needs submission/JavaScript, the sidebar separates scope from search intent, and the preferences dropdown hides a transient action among persistent settings. They are rejected.

*Proposed changes:*

1. In `bookmarks/models.py`, add non-preference boolean `global_search` to `BookmarkSearch.params`, defaults, constructor, parsing, and serialization. Parse only exact `"1"`, serialize true as `"1"`, omit false, and normalize false unless `bundle` resolved to an owned `BookmarkBundle`.
2. In `bookmarks/forms.py`, add a non-required `global_search` field so the existing hidden-field mechanism preserves active global mode. Do not add it to `BookmarkSearch.preferences`.
3. In `bookmarks/queries.py`, change only the bundle step of `_base_bookmarks_query`: call `_filter_bundle` when `search.bundle` exists and `not search.global_search`. Do not move or weaken owner, archive, sharing, query, explicit filter, or sort clauses.
4. In `bookmarks/views/contexts.py`, derive enable/disable URLs from the current view’s `RequestContext`, `search.query_params`, and `RequestContext.get_url` semantics. Preserve the parameters in invariant 4, add/remove only `global_search`, and remove `page`/`details`.
5. In `bookmarks/templatetags/bookmarks.py`, pass the list context’s scope URLs/state into the inclusion template without duplicating URL construction in the template.
6. In `bookmarks/templates/bookmarks/search.html`, render the two-state anchor only for a valid bundle in active/archived mode. Use the exact visible and accessible copy from invariant 3/7 and expose a stable selector such as `.global-search-toggle` for tests and computer-use verification.
7. In `bookmarks/styles/bookmark-page.css`, fit the new fixed-width scope action into the grouped search controls at desktop and mobile widths. The search input remains flexible, the action/preferences controls remain non-overlapping, and focus/active styles use existing theme tokens.
8. Add focused regression coverage in the existing model, form, query, active-view, archived-view, and shared-view test modules. No model migration, API/serializer, feed, JavaScript autocomplete, profile-setting, or documentation change is required.

*Open questions resolved:*

- **Flag name and accepted value:** `global_search=1`; only exact `"1"` enables it.
- **Persistence:** request/URL only; never saved in profile preferences.
- **Return behavior:** retain the valid bundle and all durable search/filter state; remove only `global_search` when returning to the bundle.
- **Pagination/details:** reset when scope changes because the result set changes.
- **Active vs. archived:** both are first-class supported bundle views; archived global mode remains archived.
- **Shared:** no first-class control because shared navigation has no bundle selector; generic query semantics must still preserve all sharing security boundaries.
- **Untagged/shared special syntax:** cover supported `!untagged` and `!unread`; use `shared=yes|no` because `!shared` is unsupported on current master.
- **Tag cloud:** changes with the list because it is derived from the same bookmark query.
- **Autocomplete/API/feed:** unchanged; no new public API parameter.
- **Invalid/foreign bundle:** the bundle remains unresolved and the global flag is normalized away.

*Risks / blast radius:*

- `_base_bookmarks_query` is shared by active, archived, shared, tag-cloud, and action paths. A misplaced condition could bypass owner/visibility/view filters; keep the change immediately around `_filter_bundle` and cover every boundary.
- Search state crosses GET search, POST preference, pagination, tag links, details links, and bulk-action URLs. Missing form/URL serialization could silently drop global mode or the bundle; test generated URLs and hidden fields.
- Global mode intentionally broadens the displayed/bulk-selectable result set. Bulk actions must operate on the same globally scoped query the user sees, never on the old bundle-only query.
- The existing 300px search control is layout-sensitive. Long labels can crowd the input; responsive computer-use proof is mandatory.
- Malformed or foreign bundle IDs must not activate or preserve global mode, both for intuitive URLs and ownership isolation.

*Validation & verification criteria* (must ALL pass before merge):

1. **Failing-before/passing-after model regression:** add `test_global_search_from_request_requires_valid_owned_bundle` and `test_global_search_query_params_round_trip` in `bookmarks/tests/test_bookmark_search_model.py`. They prove exact `"1"` parsing, false values, invalid/foreign/no bundle normalization, true serialization as `"1"`, and omission when false. These tests must fail on `origin/master` and pass after implementation.
2. **Failing-before/passing-after form regression:** extend `bookmarks/tests/test_bookmark_search_form.py` with `test_global_search_is_preserved_as_hidden_request_state`. It proves active `bundle` and `global_search=1` are hidden in both search/preference forms while `preferences_dict` still contains only sort/shared/unread. It must fail before and pass after.
3. **Failing-before/passing-after query matrix:** add tests in `bookmarks/tests/test_queries.py` covering:
   - `test_query_bookmarks_global_search_bypasses_only_bundle`;
   - `test_query_bookmark_tags_global_search_matches_global_results`;
   - `test_global_search_preserves_term_tag_and_boolean_queries`;
   - `test_global_search_preserves_untagged_unread_and_shared_filters`;
   - `test_query_archived_bookmarks_global_search_stays_archived`;
   - `test_query_shared_bookmarks_global_search_preserves_visibility`.
   The fixtures must include in-bundle and out-of-bundle matches plus records excluded by owner, archive, sharing, query, tag, unread, and shared boundaries. Each new global-mode assertion must fail before the change and pass after; existing bundle-scoped assertions must continue passing.
4. **Failing-before/passing-after active-view regression:** add tests in `bookmarks/tests/test_bookmark_index_view.py` proving the control is absent without a valid bundle, scoped mode renders “All bookmarks,” global mode renders “This bundle,” each URL preserves the required parameters and resets page/details, search/preference submissions preserve active mode, the result list/tag cloud broaden correctly, and switching bundles drops global mode.
5. **Failing-before/passing-after archived-view regression:** add equivalent focused coverage in `bookmarks/tests/test_bookmark_archived_view.py` proving the control works with an archived bundle, broadens only archived results/tags, and never includes active records.
6. **Shared/non-bundle regression proof:** run the existing shared visibility, selected-user, public-only, term-search, tag-cloud, and bundle tests in `bookmarks/tests/test_bookmark_shared_view.py`, plus a focused assertion that normal shared/no-bundle pages render no scope control. Existing active no-bundle, `#tag`, advanced expression, `!untagged`, `!unread`, sort, shared/unread preference, and autocomplete-related tests must remain green.
7. **Scoped deterministic command:** from the repo root, run:
   `uv run pytest bookmarks/tests/test_bookmark_search_model.py bookmarks/tests/test_bookmark_search_form.py bookmarks/tests/test_queries.py bookmarks/tests/test_bookmark_index_view.py bookmarks/tests/test_bookmark_archived_view.py bookmarks/tests/test_bookmark_shared_view.py -n auto`
   Record the passing summary on the PR and OSFG-57.
8. **Full repository validation gate:** from the repo root, `make lint && make test` exits 0. This is mandatory even if the scoped suite passes.
9. **Running-UI setup:** run `make init` once if needed, build current frontend assets with `npm run build`, start the app with `make serve-bg`, and verify `http://127.0.0.1:8000` is reachable before invoking computer use. Always stop it afterward with `make serve-stop`.
10. **Mandatory computer-use VIDEO — new behavior:** capture a replayable recording against the running UI using deterministic bookmarks inside and outside a “Favorites” bundle. The recording must show: bundle-scoped text search excludes the out-of-bundle match; activating “All bookmarks” reveals it; the URL visibly retains `bundle` and `q` and adds `global_search=1`; the tag cloud broadens; activating “This bundle” restores scoped results without losing the query; changing bundles removes global mode; refresh and browser back restore the correct states.
11. **Mandatory computer-use VIDEO — search regression proof:** in the same recording or an additional recording, show no-bundle text search, `#tag`, `!untagged`, `!unread`, shared/unread preference controls, search autocomplete opening without errors, archived bundle scoped/global behavior, and a normal shared-view term search. Show that active global mode never includes archived records and archived global mode never includes active records.
12. **Responsive/accessibility visual proof:** the video must include desktop and mobile/narrow viewport states showing the scope action, usable search input, preferences button, visible keyboard focus, correct accessible label/state, and no overlap or horizontal overflow.
13. **Evidence attachment:** attach the actual replayable video evidence to both OSFG-57 and the final PR body (screenshots may supplement but do not replace video). Validate the captured states against criteria 10–12. Never commit video or screenshots to the branch.

Co-Authored-By: Oz <oz-agent@warp.dev>
