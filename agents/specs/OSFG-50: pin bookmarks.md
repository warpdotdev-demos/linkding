# Spec: Pin bookmarks

## PRODUCT
**Summary:** Let users mark a bookmark as pinned while creating or editing it. Pinned bookmarks are visibly distinguished in bookmark lists and always appear before unpinned bookmarks without changing the user-selected secondary sort.

**Key design choices:** Add a persisted `Bookmark.pinned` boolean that defaults to `False`; expose it through the existing bookmark form; render a compact pin icon beside the title; and prepend `-pinned` to the existing query ordering. This follows the current unread/shared field, form, list-context, icon, and query structure while avoiding new filters, preferences, or bulk actions.

**Behavior:**
1. A new bookmark can be saved pinned or unpinned; omitting the checkbox saves it unpinned by default.
2. An existing bookmark’s pinned state is shown in its edit form and can be changed by saving the form.
3. A pinned bookmark displays a recognisable pin icon in each rendered bookmark list. Unpinned bookmarks do not render that icon.
4. For active, archived, and shared bookmark lists, pinned results sort before unpinned results. Within each group, the existing selected sort (added ascending/descending or title ascending/descending) remains intact.
5. Existing unread, shared, archived, ownership, search, pagination, and sort behavior remains unchanged other than the pinned-first grouping.

## TECH
**Context:** At commit `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`, `Bookmark` owns the analogous boolean fields at `bookmarks/models.py:53-70`. `BookmarkForm` explicitly declares and whitelists unread/shared fields and initializes them for new records at `bookmarks/forms.py:31-85`; both create and edit views save this form at `bookmarks/views/bookmarks.py:229-257`. The shared form template renders unread and conditional sharing controls at `bookmarks/templates/bookmarks/form.html:57-77`. List presentation is assembled by `BookmarkItem` in `bookmarks/views/contexts.py:130-194` and rendered by `bookmarks/templates/bookmarks/bookmark_list.html:11-142`; reusable unread/shared SVG symbols are in `bookmarks/static/icons.svg:71-91`. All active, archived, and shared list queries flow through `_base_bookmarks_query` in `bookmarks/queries.py:223-299`, where the current selected ordering is applied.

**Design alternatives:**
- **Persist `pinned` on `Bookmark` (selected):** a single `BooleanField(default=False)` plus Django migration is simple, queryable, and follows unread/shared. It makes pin state durable and lets the database order it before pagination.
- **Store pinned IDs in user preferences or a separate relation:** rejected because pins belong to the bookmark record in the requester’s stated model-field pattern, complicate ownership/shared behavior, and require joins or JSON mutation.
- **Reorder the paginated page in `BookmarkListContext`:** rejected because pinned records on later database pages would not rise above unpinned records on earlier pages; ordering must occur in the query before pagination.
- **Add a pin filter, user default, bulk action, details-modal state action, API/export/import changes, or a text label instead of an icon:** rejected as unrequested scope. The feature is limited to create/edit persistence, existing list presentation, and list ordering. A compact SVG pin symbol is idiomatic with unread/shared list affordances and is clearer than a textual status.

**Proposed changes:**
1. Add `pinned = models.BooleanField(default=False)` to `Bookmark` and create the next Django migration in `bookmarks/migrations/`; existing rows must remain unpinned.
2. Add `pinned` as an optional `FormCheckbox` field in `BookmarkForm` and its `Meta.fields`; initialize it as `False` on new bookmarks. Existing instances supply their persisted value through the normal `ModelForm` binding. Place the form control alongside the unread/shared state controls, with concise “Pin” labeling/help consistent with the form.
3. Add a `pin` SVG symbol to `bookmarks/static/icons.svg`; expose the bookmark’s pin state through `BookmarkItem`; render that icon next to a pinned bookmark’s title in `bookmark_list.html`, including the accessible text/title needed to identify the state. Do not display it for unpinned rows.
4. Adjust `_base_bookmarks_query` so every existing sort adds `-pinned` as its first order expression and preserves the prior sort as the tie-breaker. This must apply before `query_bookmarks`, `query_archived_bookmarks`, and `query_shared_bookmarks` add their visibility filters and before `BookmarkListContext` paginates.
5. Extend the established Django tests for new/edit form persistence, list-template icon rendering, and query ordering. Use test fixture data with pinned/unpinned records whose titles and dates make both primary grouping and secondary ordering observable.

**Open questions resolved:** “Pin/star icon” is resolved as a new SVG pin icon, consistent with the existing SVG icon system. “Pinned above unpinned” applies to every bookmark-list context because all three list types share the same base query; it does not introduce a user-selectable pin filter or pin-only list. The pin state is per bookmark, not per user preference, and defaults to unpinned.

**Risks / blast radius:** Modifying a common base query affects active, archived, and shared list pagination and all four sort modes. Query tests must assert secondary ordering inside each pin group. The new checkbox must not disturb sharing’s profile gate or existing default/prefill behavior. The icon must not interfere with title link layout or the non-pinned rendering path.

## Validation & verification criteria
1. Add a failing-then-passing regression test in `bookmarks/tests/test_bookmark_new_view.py` proving POSTing the new bookmark form with `pinned=True` persists a pinned bookmark, and omitting/setting it false persists `False`.
2. Add a failing-then-passing regression test in `bookmarks/tests/test_bookmark_edit_view.py` proving an existing bookmark can be pinned and unpinned through the edit POST; extend the edit-form rendering coverage so an already-pinned bookmark shows its checked state.
3. Add focused template/context coverage in `bookmarks/tests/test_bookmarks_list_template.py` proving a pinned bookmark renders the pin SVG marker with accessible identification and an unpinned bookmark does not render it; unread/shared action rendering remains covered and unchanged.
4. Add focused query regression coverage in `bookmarks/tests/test_queries.py` for each supported sort direction. It must prove `query_bookmarks` returns pinned records first and retains current title/date secondary ordering within the pinned and unpinned groups; include archived/shared query coverage or shared base-query coverage that proves the ordering is inherited by those lists.
5. Exercise the actual create/edit/list flow with the new code: create one unpinned and at least two pinned bookmarks, edit a bookmark to change its pin state, and confirm all saved states survive reloads. Verify active, archived, and shared list views place pinned results before unpinned results while their selected added/title ordering remains stable within each group.
6. Record computer-use visual proof against the rendered UI and attach it to both OSFG-50 and the PR. Because the requester explicitly requires video evidence, record one full-flow video showing: pinning on create, changing pin state on edit, the visible pin icon in the list, and pinned bookmarks above unpinned bookmarks. The recording must make the relevant titles/order legible.
7. Run the focused changed test modules with `uv run pytest bookmarks/tests/test_bookmark_new_view.py bookmarks/tests/test_bookmark_edit_view.py bookmarks/tests/test_bookmarks_list_template.py bookmarks/tests/test_queries.py -n auto`, then run the mandatory repository gate `make lint && make test`; both must pass before the shared PR is made ready for review.
