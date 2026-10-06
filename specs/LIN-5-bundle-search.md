# LIN-5: Search all bookmarks from a bundle

## Summary
Keep bundle-scoped search as the default. Add a removable scope chip that lets a user search outside the bundle without leaving the search workflow. Show the resulting scope and a link back to the bundle.

- Work item: [LIN-5](https://warp-se-demo.atlassian.net/browse/LIN-5).
- Request: [Slack discussion](https://warpsedemos.slack.com/archives/C0BQM3U96R5/p1791263824142069).
- Requester: Killian Jackson, GitHub `pkillianjackson`.
- Interview decision: Killian approved options `1A, 2A, 3A, 4A` and the scope exclusions.
- Repository: `warpdotdev-demos/linkding`; base branch: `master`.
- Code references use base commit `7e5eaf656bca4e10c4a78106b0de3a410d9531fe`.
- Status: approved by Killian Jackson ([review](https://github.com/warpdotdev-demos/linkding/pull/49#pullrequestreview-5424412702)); implementation is included on this branch and PR.

## Product behavior
1. **Bundle search remains the default.**
   - Opening a saved bundle URL selects that bundle and applies all its rules.
   - Submitting a query without changing scope searches only that bundle.
   - Show `In: <bundle name> ×` inside the search control, before the text input.
   - Show the chip even when the query is empty, the bundle has no matches, or the bundle sidebar is hidden.
2. **One action broadens the current query.**
   - Activating the chip's remove button runs the current input text without the bundle filter.
   - Use the text in the input, including edits that the user has not submitted.
   - Remove all rules contributed by the bundle: its search text, tag rules, unread rule, and shared rule.
   - Preserve the user's query, independent sort/unread/shared/date filters, and current route.
   - Start on page one and close bookmark details.
   - An empty input opens the unbundled list with those independent filters.
3. **Unbundled results show their scope.**
   - Remove `bundle` from the URL. No bundle remains selected in the sidebar.
   - Show `All bookmarks` beside the search input on the active view.
   - Show `All archived bookmarks` there on the archived view.
   - Keep the existing page heading and empty-result/error presentation.
   - Show `Back to <bundle name>` next to the scope label when a valid origin bundle exists.
4. **Search scope follows navigation, not account preferences.**
   - Later queries, recent-query selections, tag links, pagination, details, and action return URLs remain unbundled.
   - Clearing and submitting the query stays unbundled. Clearing text without submitting does not change results.
   - Keep the Back link when the query is empty.
   - Back reapplies the origin bundle to the current input text and independent filters. It resets pagination and details.
   - Selecting another bundle uses its existing navigation behavior and discards the origin.
   - Opening a saved bundle URL or a new tab does not inherit scope from another tab.
   - Browser Back/Forward restores the URL's scope, query, selected sidebar entry, and search control.
5. **The sidebar provides a matching route out.**
   - Put an `All bookmarks` entry before the user's bundles, including when the user has no bundles.
   - Selecting it removes the bundle and preserves the submitted query, independent filters, and active/archived route.
   - Reset page and details. Retain the origin bundle for the Back link when leaving a bundle.
   - Mark All bookmarks as selected whenever no valid bundle filter is active.
   - Keep the existing `hide_bundles` behavior for the sidebar. The search chip and Back link remain available independently.
6. **Archived and Shared retain their boundaries.**
   - Use the same bundle exit/return behavior on Archived.
   - Active search returns only the user's non-archived bookmarks.
   - Archived search returns only the user's archived bookmarks.
   - "All" means all bundles within that view, subject to the independent filters. It does not mean both views or other users' bookmarks.
   - Do not add the new scope UI or return metadata to Shared.
7. **Bookmark autocomplete matches the result scope.**
   - In a bundle, bookmark suggestions apply the same bundle rules and independent filters as results.
   - Outside a bundle, omit the bundle filter from suggestion requests.
   - Preserve the active/archived API endpoint and existing suggestion limit of five.
   - Keep tag completion and recent query text behavior unchanged. Neither selects a bundle.
   - Do not show stale bookmark suggestions from the prior query or scope after navigation.
8. **The control is usable without the sidebar.**
   - The chip, unbundled label, and Back link remain visible at a 375-pixel viewport and with a collapsed side panel.
   - Use existing light/dark theme tokens and focus styles.
   - The remove control is a button with accessible name `Search all bookmarks`. In Archived, use `Search all archived bookmarks`.
   - The × is decorative. Provide the same text as a hover title.
   - Keyboard users can reach and activate the button and Back link. Scope changes do not trigger merely on focus.
   - Long bundle names truncate visually without hiding the remove button or input. Keep the full name available to assistive technology and in a title.

## Technical design
### Current data flow
- `bookmarks/models.py:238` lists the search parameters. `BookmarkSearch.from_request` resolves `bundle` against the requesting owner's bundles at line 329. Only sort, shared, and unread are saved preferences at line 248.
- `bookmarks/queries.py:176` applies bundle rules in `_filter_bundle`. `_base_bookmarks_query` intersects them with the independent query and filters at line 268. Absence of `search.bundle` already provides the required unbundled behavior.
- `bookmarks/forms.py:277` creates hidden inputs for modified non-editable parameters. `bookmarks/templatetags/bookmarks.py:12` builds both search forms. `bookmarks/templates/bookmarks/search.html:14` submits those fields.
- `bookmarks/views/contexts.py:35` carries GET parameters through list, tag, details, and action URLs. `BundlesContext` at line 648 determines the selected sidebar bundle separately.
- `bookmarks/views/bookmarks.py:196` reconstructs preference redirects from `BookmarkSearch.query_params`. It discards unknown navigation metadata today.
- `bookmarks/frontend/components/search-autocomplete.js:174` sends query, user, shared, and unread without a bundle. The API already resolves bundle filters in `BookmarkViewSet.get_queryset`, `bookmarks/api/routes.py:58`.

### URL and state contract
- Keep `bundle=<id>` as the only bundle filter. Do not add a global-search filtering mode.
- Add `return_bundle=<id>` as URL-only navigation metadata. It identifies the origin for the Back link, never a result filter.
- Keep `return_bundle` outside `BookmarkSearch.params`, `BookmarkSearch.preferences`, and `UserProfile`. Do not add a database migration.
- Validate the origin as a positive integer that resolves to a bundle owned by the authenticated user. Ignore empty, malformed, oversized, deleted, nonexistent, and other-owner values without an error or leaked bundle name.
- When a valid bundle is active, ignore any supplied origin. Leaving that bundle records its own ID as the new origin.
- Without a valid active bundle, retain only a valid origin. A deleted origin removes the Back link but does not change result scope.
- Build URLs from the application's reversed active/archived route. Never accept a caller-supplied destination URL.
- Use Django query encoding and template escaping. Do not interpolate bundle names into raw HTML.
- Propagate valid origin metadata through search and preferences forms, their GET/POST redirects, tag changes, page links, details open/close, edit return URLs, and bookmark actions.
- Do not send origin metadata to autocomplete or use it for tag clouds, pagination totals, bulk-select-across queries, or saved defaults.
- Generated scope-switch URLs remove `page` and `details`. Keep independent search parameters, including explicit overrides of saved preferences.
- A direct unbundled URL without an origin has no Back link. Do not infer an origin from browser storage or a session.

Example contract, with query ordering irrelevant:

- Bundle: `/bookmarks?bundle=12&q=python&unread=yes`.
- Remove chip: `/bookmarks?q=python&unread=yes&return_bundle=12`.
- Next query: `/bookmarks?q=django&unread=yes&return_bundle=12`.
- Clear query: `/bookmarks?unread=yes&return_bundle=12` (`q=` is also valid).
- Back: `/bookmarks?bundle=12&q=django&unread=yes`; remove `return_bundle`.
- Archived follows the same transitions under its existing reversed route.

### Proposed code changes
- Add `bookmarks/services/search_scope.py` for owner-validated origin lookup, origin normalization, and unbundle/return URL construction. Keep query filtering in the existing query functions.
- Expose a scope context with the resolved bundle/origin names, unbundle URL, and return URL. Reuse it in `bookmark_search` and `BundlesContext`; do not duplicate URL rules in templates.
- Normalize origin metadata in `RequestContext.query_params`. Keep the existing URL propagation for tags, pagination, details, and actions.
- In `bookmark_search`, expose the scope context and add origin hidden inputs to both rendered forms only when unbundled with a valid origin.
- In `search_action`, validate submitted origin metadata and append it to the redirect after the existing search/preference handling. Saving defaults must still store exactly sort, shared, and unread.
- Update `search.html` and `bundle_section.html` to render the controls and All bookmarks entry.
- Extend `SearchAutocomplete` with the resolved bundle and independent sort/date attributes. Send effective sort, shared, unread, modified_since, and added_since values to suggestions, including values inherited from saved preferences.
- Do not change `Api.listBookmarks` or add an API endpoint; it already encodes supplied search parameters.
- Render the chip inside the Lit search input wrapper. Supply its scope name and server-generated target URLs as attributes. Render the unbundled label and Back link with the search control.
- On chip or Back activation, update the target URL's `q` with the live input value, close suggestions, and perform a normal Turbo visit. Server-generated links use the submitted query as their fallback. Sidebar links use the submitted query, not unsent edits.
- Clear suggestions when query/scope attributes change. Discard late responses whose query/scope no longer matches the current request.
- Adjust `bookmarks/styles/bookmark-page.css` for the scope chip and wrapped scope/return row. Keep the existing preferences button and mobile filter control accessible.
- Add a short bundle-scope section to `docs/src/content/docs/search.md`. Explain scope removal, Back, clearing, independent filters, and active/archived separation.

## Decisions
- **Chip (approved 1A):** it exposes scope before submission and works with a hidden sidebar. A results-only link is cheaper but invisible until a search runs. A second submit button uses more space. A shortcut alone is difficult to discover.
- **Remove bundle and keep a return link (approved 2A):** the URL, filter, and sidebar agree. A separate filtering mode could return automatically on clearing, but it leaves a selected bundle that does not constrain results and adds another search state. Clearing deliberately stays unbundled.
- **Preserve independent filters and view (approved 3A):** only the bundle restriction changes. Resetting filters or mixing active and archived records would change the user's intent and existing endpoint semantics.
- **All bookmarks entry and scoped bookmark suggestions (approved 4A):** the sidebar explains selection, and autocomplete no longer offers out-of-scope bookmark matches. Control-only scope is cheaper but leaves that inconsistency.
- **URL-only origin (technical choice):** validated metadata survives reloads, copied URLs, and Turbo navigation without changing query semantics. Session/local-storage state would be tab-sensitive and invisible in a copied URL. Browser history alone cannot support a durable named return link.

## Assumptions
These implementation details were not separate interview questions:

- Chip removal executes the live input immediately, rather than only changing scope for the next Enter press.
- Back uses the live input. The sidebar All bookmarks link uses the submitted query.
- Clear resets only the query. Keep origin metadata until another bundle or a navigation link without that metadata is selected.
- Use `All archived bookmarks` in the search control to make the retained archive boundary explicit. The sidebar entry remains `All bookmarks`.
- Keep tag completions and recent-query history global. Only bookmark suggestions must match result membership.
- Reuse existing app styles and Turbo navigation; no new design asset is required.

## Out of scope
- A default-bundle setting. The request concerns a saved bundle URL; Save as default retains its current preference contract.
- Making global search the default, an account-wide sticky scope, or a keyboard shortcut.
- Combining active and archived results, clearing independent filters, searching other users' bookmarks, or changing Shared.
- Search parser changes, bundle editor changes, tag suggestion filtering, or scope-aware recent-query storage.
- Dependency updates, data migrations, release scripts, or unrelated UI refactoring.

## Validation criteria
The names below are required new tests, not claims that tests already exist. Tests must use fixtures with an inside-bundle match, an outside-bundle match, a nonmatch, archived matches, and another owner's match. Exercise both search engines where query filtering applies.

### Unit and integration tests
- Add `test_bundle_scope_urls` in `bookmarks/tests/test_search_scope.py`: assert unbundle/Back transitions preserve independent parameters and route, reset page/details, encode tags and special characters, and do not restore the original query.
- Add `test_return_bundle_validation` there: cover malformed/oversized/nonpositive values, deleted/nonexistent/other-owner IDs, and valid bundle precedence over conflicting origin. Assert no error, leaked name, or filtering effect.
- Add `test_return_bundle_is_navigation_only` there: assert equal result IDs, tag clouds, counts, and bulk-selection scope with and without origin metadata.
- Add `test_bundle_scope_controls` in `test_bookmark_search_tag.py`: assert both form hidden fields, resolved bundle attributes, scope labels, return link, escaping, and absence of new controls in Shared.
- Add `test_bundle_global_search_navigation` to both `test_bookmark_index_view.py` and `test_bookmark_archived_view.py`: assert bundle defaults, unbundled matches, query changes, empty query, tag changes, pagination, details, and edit/action return URLs preserve the intended scope and origin.
- Add `test_scope_preferences_preserve_origin_only_in_url` to both view suites: Apply and Save preserve a valid origin in the redirect; saved preferences contain only sort/shared/unread; explicit off overrides remain effective.
- Add `test_all_bookmarks_bundle_entry` to both view suites: assert first position, selected state, route/filter preservation, no-bundle behavior, and other-owner exclusion. Update existing sidebar helpers to account for the new entry.
- Add `test_autocomplete_scope_filter_contract` in `test_bookmarks_api.py`: active and archived suggestion requests respect bundle/filter membership, owner boundaries, explicit preferences, and the five-result limit.
- Run `uv run pytest bookmarks/tests/test_search_scope.py bookmarks/tests/test_bookmark_search_tag.py bookmarks/tests/test_bookmark_search_form.py bookmarks/tests/test_bookmark_search_model.py bookmarks/tests/test_bookmark_index_view.py bookmarks/tests/test_bookmark_archived_view.py bookmarks/tests/test_bookmark_shared_view.py bookmarks/tests/test_bookmarks_api.py bookmarks/tests/test_queries.py bookmarks/tests/test_pagination_tag.py bookmarks/tests/test_bookmark_details_modal.py bookmarks/tests/test_bookmark_action_view.py -q`.

### Browser behavior and visual proof
- Add `bookmarks/tests_e2e/e2e_test_bundle_search_scope.py`, using `LinkdingE2ETestCase` in `bookmarks/tests_e2e/helpers.py:14`.
- `test_chip_uses_unsent_query_and_back_keeps_current_query`: enter text without submitting, remove scope, change the query, return to the bundle, and verify visible records and URL at every transition.
- `test_scope_survives_clear_navigation_and_history`: clear/submit, paginate, add/remove a tag, open/close details, apply preferences, then use browser Back/Forward. Verify scope labels, origin, and selection.
- `test_autocomplete_follows_scope`: inspect active/archived requests and suggestion membership before/after scope changes; inherited filters, late responses, and Turbo-cached visits must not expose stale out-of-scope matches.
- `test_scope_control_without_sidebar`: verify keyboard activation, a 375-pixel viewport, hide_bundles, collapsed side panel, long names, and light/dark themes. Input, ×, preferences, Filters, and Back must not overlap or disappear.
- Build successfully with `npm run build` before running manual UI verification. Run `make e2e` for the browser suite; its harness manages its own server.
- Require computer-use video evidence on the implementation PR. Record bundle search, chip removal with unsent text, an outside-bundle result, a later query, clearing, Back, and the matching archive flow. Include a mobile/hidden-sidebar segment and keyboard activation. Show the changing URL, scope label, result titles, and sidebar selection where visible.
- The spec-only PR needs no UI recording. Do not treat current UI footage as proof of the unimplemented feature.

### Completion gates
- Implementation passes the scoped tests above, `make lint`, `make test`, `npm run build`, and `make e2e`.
- Run `npx prettier bookmarks/frontend/components/search-autocomplete.js bookmarks/styles/bookmark-page.css --check` and `uv run djlint bookmarks/templates/bookmarks/search.html bookmarks/templates/bookmarks/bundle_section.html --check`.
- The documentation names the exact clear/Back/filter semantics specified here.
- Keep the specification on the implementation branch. Obtain requester approval of this document before implementation starts.
