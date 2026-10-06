# LIN-6: Search all bookmarks from within a bundle

## Summary

Keep bundle-scoped search as the default. Add an `In: <bundle> ×` chip inside the search field. Activating the chip submits the current typed query without the bundle filter. Keep the current active or archived view and independent search filters.

- Work item: [LIN-6](https://warp-se-demo.atlassian.net/browse/LIN-6).
- Requester and spec reviewer: `pkillianjackson`.
- Source: [request thread](https://warpsedemos.slack.com/archives/C0BQM3U96R5/p1791265644134139).
- Interview decision: the requester said, “Let's go with your recommendations.”
- This document specifies implementation. This spec PR does not implement the feature.
- Obtain the requester's approval of this document before implementation. Reuse this PR and branch for implementation.

## Product behavior

1. **Default scope.** A valid, user-owned `bundle=<id>` on the active or archived bookmark page applies the bundle filter. An ordinary search submission stays within that bundle. Preserve existing autocomplete selection behavior; Enter with no selected suggestion submits the scoped search.
2. **Visible control.** When that bundle is active, show `In: <bundle name> ×` inside the search field, before the text input. Show it even when `hide_bundles` or `collapse_side_panel` is enabled. Do not require the sidebar or mobile Filters drawer to be open.
3. **One-action global search.** Make the chip a native submit button. Clicking or tapping it, or activating it with Enter or Space, immediately searches outside the bundle. Use the live input value, including text typed since the last page load and completed tag tokens. Do not first navigate away and ask the user to retype or press Enter.
4. **Global results.** Remove `bundle` from the final URL. Remove the chip and clear the sidebar's selected bundle. “All bookmarks” means the signed-in user's bookmarks in the current view: active remains active; archived remains archived. Do not combine both views or include other users' bookmarks.
5. **Retained filters.** Preserve the typed `q`, including tag expressions, and the effective `sort`, `unread`, `shared`, `added_since`, `modified_since`, and `user` search parameters. Preserve saved search preference defaults. Remove all rules imposed by the bundle, including its text, tag, unread, and shared rules. Do not convert bundle rules into independent filters.
6. **Reset transient list state.** Start global results on page 1. Do not carry a `page` or `details` parameter into the final URL. Do not retain the submitted scope-action marker. Normal URL normalization may omit empty or default-valued parameters; the effective query and filters must remain the same.
7. **Empty and invalid queries.** An empty input removes the bundle and lists bookmarks in the current view under the remaining filters. If filters leave no matches, use the existing empty state. If the query is invalid, use the existing query error state. Do not silently clear filters or rewrite query expressions to produce results.
8. **Navigation after global search.** Tag addition/removal, pagination, search preferences Apply/Save, and bookmark detail/action/return links use the global URL. They must not restore the removed bundle. Existing tag clicks continue to reset pagination. Existing ordinary query and preference submissions retain their current normalization behavior.
9. **Returning to a bundle.** Existing bundle links re-enter scoped search on the current page path. Keep their current `?bundle=<id>` behavior, which resets independent query parameters. Browser Back restores the prior scoped URL and its chip. Do not add a Back-to-bundle control or restore scope through session state.
10. **Autocomplete consistency.** Bookmark suggestions respect the active bundle. After global search, bookmark suggestions omit the bundle and use the current view and existing independent suggestion filters. Keep tag-name suggestions and recent query strings unchanged. Do not change the minimum query length, result limit, selection keys, or bookmark-opening behavior.
11. **Unscoped and shared pages.** Do not show the chip when no valid owned bundle is resolved. Shared/public bookmark pages retain their current search UI and behavior. Do not add a scope control there.
12. **Accessible and responsive control.** The chip has the accessible name `Search all bookmarks, remove bundle filter: <full bundle name>`. Keep `In:`, the remove symbol, and keyboard focus visible. Allow only the displayed bundle name to truncate. Expose the full name through the accessible name and a title. Preserve an editable text input and the preferences button on desktop and mobile, in light and dark themes.

## Technical design

### Current data flow

- `bookmarks/models.py (238-343)`: `BookmarkSearch` resolves an owned bundle from the request. `query_params` serializes modified search parameters. Saved preferences contain only `sort`, `shared`, and `unread`.
- `bookmarks/forms.py (248-303)`: `BookmarkSearchForm` renders modified non-editable parameters as hidden inputs. Both the GET search form and POST preferences form preserve `bundle` today.
- `bookmarks/templatetags/bookmarks.py (12-33)` and `bookmarks/templates/bookmarks/search.html (3-15)`: the shared search partial receives `search` and `mode`. It wraps the Lit autocomplete in a GET form.
- `bookmarks/frontend/utils/element.js (58-79)`: `TurboLitElement` renders into light DOM. A native button inside the autocomplete belongs to the enclosing Django form.
- `bookmarks/frontend/components/search-autocomplete.js (14-29, 168-185, 288-313)`: the component renders the input and fetches bookmark suggestions. It currently sends `q`, `user`, `shared`, and `unread`, but not the bundle.
- `bookmarks/views/bookmarks.py (43-105, 196-212)`: active and archived pages parse GET search parameters. POST preference submissions use `search_action` and redirect to the current page path.
- `bookmarks/queries.py (176-224, 268-270)`: the bundle filter is ANDed with independent filters. Omitting the bundle already supplies the required global result semantics.
- `bookmarks/views/contexts.py (56-64, 301-394, 648-665)`: URLs propagate the current request parameters. Bundle selection follows `request.GET`. Tag changes remove page/detail state.
- `bookmarks/api/routes.py (58-71)`: active and archived bookmark listing endpoints already accept `bundle`. No endpoint or response change is required.

### Search control and submit contract

Change `bookmarks/templates/bookmarks/search.html` and `bookmarks/frontend/components/search-autocomplete.js`.

- Pass the resolved `search.bundle.id` and `search.bundle.name` as `bundle` and `bundle-name` component attributes on active/archived pages only.
- Declare string properties `bundle` and `bundleName`, with empty-string defaults. Render the chip only when `bundle` is nonempty.
- Render the chip inside `.form-autocomplete-input`, before the text input.
- Submit `name="search_scope"` and `value="all"` only when the chip is activated.
- Retain the existing hidden `bundle` input in the GET form. This preserves ordinary scoped search.
- Put the existing neutral, unnamed Search submit input **before** `<ld-search-autocomplete>` in form order. It must remain the first submit control after the Lit component renders. Otherwise, implicit Enter submission could activate the new global-search button.
- Do not add a hidden `search_scope` input. Do not add the marker to `BookmarkSearch.params` or stored preferences.
- Use native form submission. Do not read `input-value` from the server-rendered attribute, build a URL from the old page query, or intercept the chip to modify persistent state.
- Escape bundle names through Django attribute escaping and Lit text interpolation. Do not inject them with raw HTML.
- Keep autocomplete's existing key handlers. Its selected-suggestion Enter/Tab handling must not invoke the chip.

Interface shape, not a full implementation:

```html path=null start=null
<button type="submit" name="search_scope" value="all"
        aria-label="Search all bookmarks, remove bundle filter: Books">
  In: Books <span aria-hidden="true">×</span>
</button>
```

### Canonical global-search redirect

Change `index` and `archived` in `bookmarks/views/bookmarks.py`.

- After their existing POST dispatch, handle GET requests whose `search_scope` value equals `all` before constructing search/list/sidebar contexts.
- Use one shared, small redirect helper in that view module. This is request/URL handling, not new query logic.
- Copy the submitted GET parameters. Remove `bundle`, `page`, `details`, and `search_scope`.
- Parse the copy with `BookmarkSearch.from_request(request, params, request.user_profile.search_preferences)`.
- Serialize `search.query_params` with the existing `urllib.parse.urlencode` pattern. Redirect with `HttpResponseRedirect` to `request.path` plus those parameters. Use the bare path when no parameters remain.
- Do not copy unknown parameters into the canonical URL. Match the existing `search_action` normalization of known search parameters.
- The redirected request follows existing view/query/context logic. It has no bundle, so both results and sidebar selection agree.
- A repeated GET intent after the bundle is absent produces the same unscoped search URL. It never creates persistent state.
- Do not add this handler to shared views, API routes, or feeds.
- Keep `search_action`'s preference behavior unchanged. Add regression coverage that scoped preferences preserve the bundle, while preferences after global search do not restore it.

Example with default preference values: `/bookmarks?bundle=7&q=old&page=3` with live input `history #book` and chip activation finishes at `/bookmarks?q=history+%23book`. On archived pages, the final path remains `/bookmarks/archived`. Compare decoded parameters in tests; query-string ordering is not the product contract.

### Bookmark suggestions

Change `SearchAutocomplete.loadSuggestions` in `bookmarks/frontend/components/search-autocomplete.js`.

- Add the component's `bundle` value to `suggestionSearch`.
- Keep the existing view-specific API path: active or `/archived`.
- Let `Api.listBookmarks` omit an empty bundle value through its existing truthy-value filtering (`bookmarks/frontend/api.js (6-21)`).
- Do not change the API implementation, query filter functions, tag cache, or search-history format.
- Preserve scoped attributes across Turbo restoration. Follow `TurboLitElement`'s existing cache lifecycle instead of saving bundle state independently.

### Layout and documentation

- Add scoped-control styles in `bookmarks/styles/bookmark-page.css`, next to `.search-container` (`48-136`).
- Use existing theme color, spacing, control-height, border, and focus tokens. Keep the preferences control visually grouped with the search field.
- Cap the chip at 45% of the input shell width. Make the bundle-name segment shrink and ellipsize. Keep the text input flexible with `min-width: 0`. Keep the remove symbol from shrinking.
- Make the whole chip clickable, not just the symbol. Its target must measure at least 24 by 24 CSS pixels.
- At a 375px viewport, the search field, chip, editable input, preferences button, and Filters button must remain reachable without horizontal page overflow.
- Follow existing navigation focus behavior: initial load stays on body; Turbo navigation focuses main content. Do not introduce autofocus. Reference `bookmarks/tests_e2e/e2e_test_a11y_navigation_focus.py (7-64)`.
- Update `docs/src/content/docs/search.md` during implementation. Add a short Bundle scope section explaining scoped Enter, the immediate global chip action, current-view/retained-filter semantics, and returning through a bundle link.

## Decisions

- **Chip versus separate button.** A chip shows the current scope in the field and uses less header space; its remove action needs an explicit accessible name. A separate Search-all button is clearer as an action but crowds the header. A keyboard modifier is compact but undiscoverable and lacks touch access. A preferences option is discoverable only after opening a menu. Choose the chip, as accepted in the interview.
- **Immediate submission versus a pending toggle.** Immediate submission satisfies the one-action workflow and uses the live input. A pending toggle permits further editing before submission but needs a second action and temporary scope state. Choose immediate submission.
- **Canonical URL versus remembered bundle context.** Dropping `bundle` makes results, sidebar selection, copied URLs, and navigation consistent. Keeping a highlighted bundle without applying it preserves visual context but misrepresents scope. Session memory supports a custom return path but adds hidden state. Choose the canonical URL and existing return navigation.
- **Current view versus combined results.** Keeping active/archived separation preserves each page's existing query and action semantics. Combining both would find more records but changes result/action behavior and broadens this feature. Choose the current view.
- **Independent filters versus reset-all.** Retaining filters preserves the user's query intent and matches LIN-6's acceptance criteria. Reset-all may return more matches but discards deliberate constraints. Choose retained filters; remove bundle-imposed rules only.
- **Scoped versus global bookmark suggestions.** Keeping current global suggestions is the smallest code change but conflicts with the displayed bundle scope. Scoping them uses the existing API and makes suggestions agree with results. Choose scoped bookmark suggestions; retain current tag/history suggestions.
- **Native GET intent versus client-only URL rewriting.** A native submitter reads the live form value and reuses server normalization. It costs one canonical redirect and requires a neutral first submitter. Client URL rewriting avoids that redirect but duplicates form/query handling and can use stale query state. Choose native `search_scope=all` and the shared view redirect helper.
- **No preference in v1.** A persistent global-search default could remove repeat scope switching but changes the agreed scoped default and adds settings/state. Keep scope URL-driven. Re-entering a bundle starts scoped search.

## Assumptions

- **Assumption A1 — entry point:** “default view” means a saved browser URL or shortcut containing `?bundle=N`. The requester did not explicitly identify that workflow. `UserProfile` has no default-bundle setting, and `GlobalSettings.landing_page` offers Login or Shared Bookmarks, not a bundle URL (`bookmarks/models.py:459`, `536-548`). This feature works for any valid owned bundle URL and does not depend on how it was opened.

## Out of scope

- A default-bundle setting, a search-all-by-default setting, or session/local-storage scope persistence.
- A sidebar All-bookmarks entry, a Back-to-bundle control, or a new shortcut.
- Combining active and archived lists or expanding ownership/public-sharing access.
- API contracts, model/schema/migration changes, feed behavior, search expression parsing, or bundle definitions.
- Changing tag suggestion scope, recent-search storage, or existing suggestion-selection semantics.
- Broad malformed-bundle/error-handling changes, dependency updates, or unrelated frontend refactors.

## Validation criteria

The test names below are required additions unless a named test already exists. Implement the view checks in both `bookmarks/tests/test_bookmark_index_view.py` and `bookmarks/tests/test_bookmark_archived_view.py`. Each check must assert the decoded final URL and visible result set where relevant.

### Form, view, and regression checks

- `test_hidden_fields` in `bookmarks/tests/test_bookmark_search_form.py`: retain the scoped hidden bundle field and omit it for an unscoped `BookmarkSearch`.
- `test_scope_control_attributes`: assert resolved bundle ID/name attributes and the neutral submit input's position before the component. Assert no scope marker is a hidden field.
- `test_scope_control_visibility`: cover no bundle, valid bundle, nonexistent numeric bundle, and another user's bundle. Only the owned valid bundle supplies scope attributes. Include `hide_bundles=True` and `collapse_side_panel=True`.
- `test_search_all_canonical_redirect`: submit `search_scope=all`, `bundle`, and a query that matches owned bookmarks both inside and outside the bundle. Follow the redirect. Assert no bundle/action/page/detail parameters, no selected sidebar bundle, and the outside match. Exclude another owner's bookmark and the opposite archive state.
- `test_search_all_preserves_independent_filters`: exercise sort, unread, shared, date filters, user, and query tags. Include overrides of saved preferences and default values omitted from the URL. Verify the result set/order and effective filters. Assert profile preferences are unchanged.
- `test_search_all_removes_bundle_rules`: cover bundle text, any/all/excluded tags, unread, and shared rules. Verify they no longer constrain results while independent filters still apply.
- `test_search_all_empty_and_invalid_query`: cover empty input, zero matches under retained filters, and an invalid parser expression. Preserve existing states and clear only bundle/transient state. Also exercise legacy search.
- `test_search_all_navigation_stays_global`: assert tag, page, detail/action, and return links do not include the bundle or marker. Cover pagination after producing more than one page.
- `test_search_action_preserves_current_scope`: scoped Apply/Save redirects retain `bundle`; global Apply/Save redirects omit it. Neither flow stores the bundle or marker in preferences.
- `test_search_all_intent_is_idempotent`: the intent without a bundle redirects to the same canonical unscoped URL. Unknown intent values do not activate global search.
- `test_scope_control_absent_on_shared_view` in `bookmarks/tests/test_bookmark_shared_view.py`: shared/public pages do not gain chip attributes or intent handling.
- Run existing query, ownership, shared-view, and API regressions. Add `test_list_bundle_scope_matches_search` and `test_archived_bundle_scope_matches_search` in `bookmarks/tests/test_bookmarks_api.py` if equivalent list-contract coverage is absent: bundle plus `q` narrows results; omitting bundle broadens only within the endpoint's existing view/ownership boundary.

Run the targeted suite with `uv run pytest bookmarks/tests/test_bookmark_search_form.py bookmarks/tests/test_bookmark_index_view.py bookmarks/tests/test_bookmark_archived_view.py bookmarks/tests/test_bookmark_shared_view.py bookmarks/tests/test_bookmark_search_model.py bookmarks/tests/test_queries.py bookmarks/tests/test_bookmarks_api.py -q`. Run the complete suite with `make test`. Both must pass.

### Browser regression checks

Add `bookmarks/tests_e2e/e2e_test_bundle_search_scope.py` using `LinkdingE2ETestCase` from `bookmarks/tests_e2e/helpers.py`. Reuse the existing test server and fixtures.

- `test_enter_remains_bundle_scoped`: Enter without a selected suggestion retains `bundle` and excludes outside matches. This guards against making the chip the default submitter.
- `test_chip_submits_live_query_globally`: type a query different from the URL query, complete a tag token, activate the chip, and assert the live query and outside result on both active and archived pages.
- `test_scope_chip_keyboard_activation`: Tab reaches the chip; Enter and Space activate it. Verify its complete accessible name and visible focus. Verify autocomplete Escape/arrow/selected-suggestion handling stays intact.
- `test_suggestions_follow_bundle_scope`: record the bookmark suggestion request. With a bundle it contains the bundle ID and excludes an outside match. After global search it omits bundle and includes that match. Repeat for the archived endpoint.
- `test_global_navigation_and_back`: change a tag, paginate, apply preferences, open/close details, and return to a bundle. Global navigation stays unscoped; bundle-link navigation and browser Back restore URL-driven scoped rendering without stale or duplicated chips.
- `test_scope_chip_layout`: cover a 256-character bundle name with HTML-sensitive characters, 375px and desktop viewports, light/dark themes, hidden bundles, and a collapsed sidebar. Assert no horizontal overflow, a usable input/preferences/Filters control, and at least a 24px chip target.

Run `make e2e`. The suite must pass. Do not install or script a separate browser automation harness.

### Build, formatting, and visual proof

- Run `make format`, `make lint`, and `npm run build` during implementation. Inspect formatting changes and keep them limited to touched files. The build and lint must succeed.
- After a successful build, use the computer-use tool to exercise the running feature. Require **video** of a bundle URL, scoped Enter, the immediate chip action with a live query, the outside-bundle result, the bundle-free URL/unselected sidebar, and returning to the bundle. Include the archived and keyboard paths.
- Require the computer-use report to describe long-name/mobile layout and light/dark theme observations. Record those states in the video; supplementary screenshots are optional.
- Put the verification video in the implementation PR description. Do not commit captured media. Automated test output alone is not visual proof.
- The spec-only PR requires `git diff --check`, verification that only this document changed, and human approval. It does not require a frontend build, application tests, or visual proof before implementation.
