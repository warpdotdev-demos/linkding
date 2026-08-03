# Spec: Duplicate bookmark detection and merge

Task: [OSFG-72](https://warp-se-demo.atlassian.net/browse/OSFG-72)  
Estimate: XL (8)  
Target: `warpdotdev-demos/linkding` at base commit `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`  
Investigation: [Oz run](https://oz.warp.dev/runs/019fc8ec-493d-7d6e-b2b9-6994d1160c37)

## Product

### Summary

Linkding must identify bookmark rows owned by the same user that refer to the same URL after known marketing/click-tracking parameters are removed. It must prevent ordinary new save/import/API operations from creating another row when such a bookmark already exists, without changing the URL that the user entered or sees. A new Duplicates page must let the owner review and merge two or more existing copies, either one group at a time or several groups in one confirmed batch, while preserving the information and assets defined below.

The requester approved a conservative URL-only identity rule. Title/content similarity, cross-user matching, unattended merging, undo, and new public merge/detection APIs are not part of v1.

### Key design choices

1. Store a separate, indexed, non-unique duplicate-match key on each bookmark. Keep `url` and `url_normalized` semantics unchanged; existing duplicate rows must be allowed to share the new key.
2. Use an owner-only, server-rendered review/preview/confirm flow. Detection always considers the owner's whole library, while filters only narrow which groups are shown.
3. Put all reconciliation in one service and one database transaction per submitted single or bulk operation. Re-fetch and validate every selected row at confirmation time; never trust hidden form state as the merge authority.
4. Keep the chosen primary bookmark's URL. Union or reconcile every other field by the deterministic rules below, reparent every `BookmarkAsset`, and defer destructive preview-file cleanup until the database transaction commits.

### Behavior

1. **Duplicate identity is conservative and URL-only.**
   - Start from the same scheme/host/path/port/auth/query-order/fragment normalization used by `normalize_url()`.
   - Remove query parameters case-insensitively when their name starts with `utm_` or exactly matches one of: `fbclid`, `gclid`, `dclid`, `gbraid`, `wbraid`, `msclkid`, `mc_cid`, `mc_eid`, `_hsenc`, `_hsmi`.
   - Preserve every other query parameter, including repeated values and blank values. Preserve fragments and the existing scheme/host/path normalization behavior.
   - Do not compare titles, descriptions, notes, page content, redirects, or response bodies.

2. **Stored and displayed URLs do not change.** The duplicate key is derived state. Saving a tracking-bearing URL must not strip or rewrite `Bookmark.url`, and `url_normalized` retains its current behavior.

3. **Ordinary saves stop recurrence without replacing existing metadata.** If an owner already has a row with the derived duplicate key before a form, REST API, SingleFile, or Netscape import save is processed, that path reuses the deterministic existing row instead of inserting another one. The deterministic row is the earliest `date_added`, breaking ties by the lowest bookmark ID. Treat that row as primary and reconcile the transient/imported copy with the same no-loss rules used by an explicit merge: tags union; distinct notes append with the incoming URL separator; unread/shared use OR; archived uses AND when the incoming path supplies that state; existing non-empty title/description win and otherwise accept incoming non-empty values; earliest supplied `date_added` wins; `date_modified` becomes the save time. Keep the existing stored URL.

4. **Concurrent-create scope is explicit.** The new key is intentionally not unique because pre-existing duplicates must coexist until the user resolves them. v1 does not add a separate identity registry solely to serialize simultaneous first saves for the same never-before-seen key. A rare race between truly concurrent first saves may still create a reviewable group; normal saves that begin after a matching row exists must reuse it.

5. **Detection is owner-scoped and library-wide.** The Duplicates page lists every non-empty duplicate-key group with at least two rows for the authenticated owner, including active and archived copies. It never reads or merges another user's bookmarks, even if the URLs match.

6. **Filters do not redefine a group.** The page reuses existing `BookmarkSearch` query/search, tag/bundle, unread, shared, and date filters, plus an all/active/archived state filter. A group is shown when at least one member matches the current filters, but every member of that group is displayed and available for review. Filtering cannot silently hide a source from the merge preview.

7. **The page has deterministic states.**
   - Empty library/no matches: explain that no likely duplicates were found.
   - Results: show group count, copy count, each copy's title, full URL, active/archived, unread/shared, dates, tags, whether notes exist, and available asset counts.
   - Invalid or stale confirmation: merge nothing, show an actionable error, and return the user to refreshed group data.

8. **Single-group merge supports two or more selected copies.** A user can select a subset of at least two rows from one duplicate group, choose exactly one selected row as primary, and open a preview. All group members are selected initially. The default primary is earliest `date_added`, then lowest ID, but the user can change it.

9. **The preview is authoritative and explicit.** Before confirmation, show the chosen primary URL and the exact resulting title, description, note text/provenance, tag set, unread/shared/archived states, dates, scalar asset choices, and historical asset count. Also list the source rows that will be deleted and state that v1 has no undo.

10. **Bulk merge operates on groups, not arbitrary bookmark selections.** The user selects two or more displayed duplicate groups, opens one preview, and confirms one batch. Each group defaults to earliest `date_added`, then lowest ID, with an optional primary override in the preview. The preview shows every group and survivor. There is no unattended or one-click “merge all.”

11. **A bulk confirmation is all-or-nothing.** If any submitted group is stale, crosses owners, contains fewer than two selected rows, includes a primary outside its selection, or no longer shares one duplicate key, no group in the request is merged.

12. **Tags are never lost.** The primary receives the union of all tags on the selected rows. Existing primary/tag relationships are retained; duplicate relationships are not created.

13. **Notes are never lost.**
   - Keep the primary's non-empty notes first and byte-for-byte unchanged.
   - Visit selected source rows in ascending `date_added`, then ID order.
   - Append each non-empty note whose complete text is not already present as an exact note value.
   - Use this deterministic separator before each appended source note: `\n\n---\nMerged from <source URL>\n\n`.
   - Identical complete notes appear once; differing notes are never overwritten or collapsed.

14. **Boolean state protects the most conservative user intent.**
   - `unread` is logical OR: if any selected copy is unread, the result is unread.
   - `shared` is logical OR: if any selected copy is shared, the result remains shared.
   - `is_archived` is logical AND: the result is archived only when every selected copy is archived, so one active copy keeps the result active.

15. **Text and dates are deterministic.**
   - Keep the primary `title` and `description` when non-empty.
   - If either primary field is empty, use the non-empty value from the selected row with the latest `date_modified`, breaking ties by lowest ID.
   - Set `date_added` to the earliest selected value.
   - Set `date_accessed` to the latest non-null selected value, or null when all are null.
   - Set `date_modified` to the merge timestamp.
   - Keep the primary URL; recompute its normalized URL and duplicate key through normal model behavior.

16. **All historical bookmark assets survive.**
   - Reassign every selected source `BookmarkAsset` row, including snapshot and upload types and every status, to the primary before deleting source bookmarks.
   - `latest_snapshot` becomes the newest reassigned or existing asset whose type is `snapshot`, status is `complete`, and file is non-empty, ordered by `date_created` descending then ID descending. If none exists, it is null.
   - No `BookmarkAsset` row or backing asset file is deleted merely because its bookmark was merged.

17. **Scalar assets follow primary-first fallback rules.**
   - Keep the primary's non-empty `web_archive_snapshot_url`, `favicon_file`, and `preview_image_file`.
   - For an empty primary field, inspect sources by `date_modified` descending then ID ascending and choose the first non-empty candidate.
   - For `preview_image_file`, a candidate is valid only when its backing file exists; otherwise continue searching and leave the result empty if none is valid.
   - For `favicon_file`, a non-empty value is sufficient because favicons are shared cache files and the loader can refresh them.
   - For `web_archive_snapshot_url`, a non-empty value is sufficient; merge does not make a network request to validate a remote archive.

18. **Preview files are cleaned without violating transaction safety.** A preview file retained by the primary must not be deleted by a source bookmark's `post_delete` signal. Clear source preview fields before row deletion, collect only unretained filenames, and delete them with `transaction.on_commit` after confirming no remaining bookmark references the filename. A database rollback must leave both rows and files untouched.

19. **Confirmation deletes only selected source rows.** Unselected members of the duplicate group remain. After a successful merge, refresh detection; a group disappears only when fewer than two rows with that key remain.

20. **Authorization and request safety match existing write operations.** All views require login and CSRF-protected POST for mutation. Every submitted bookmark is reloaded with `owner=request.user`; inaccessible IDs return the same not-found behavior as existing bookmark writes and never reveal another user's data. GET requests never mutate.

21. **The UI is reachable and usable on desktop and mobile.** Add Duplicates to both navigation variants. Group selection, primary selection, preview, confirmation, validation errors, and focus behavior use labeled native controls and the repository's existing Turbo/modal/confirm patterns.

22. **Out of scope for v1:** fuzzy title/content matching, redirect/content inspection, stripping generic parameters such as `ref` or `source`, cross-user groups, scheduled/background scanning or merging, undo/tombstones/merge audit history, a new public REST API/CLI for detection or merge, and retained access to every superseded scalar favicon/preview/archive value.

## Technical

### Current context

All references below are pinned to `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`.

- `bookmarks/models.py` (53-156): `Bookmark` stores the URL, normalized URL, text/state/date fields, owner, tags, scalar asset fields, and `latest_snapshot`; `save()` derives `url_normalized`; `query_existing()` performs owner-scoped application-level matching. The same file's delete signals remove preview and asset files immediately.
- `bookmarks/utils.py` (170-213): `normalize_url()` lowercases scheme/host, removes trailing path slashes, sorts query parameters, and preserves fragments, but does not remove tracking parameters.
- `bookmarks/services/bookmarks.py` (12-72): all web-form and REST creates call `create_bookmark()`, which updates the first `query_existing()` result or saves a new row and schedules metadata/assets. `update_bookmark()` refreshes dates and asset tasks.
- `bookmarks/forms.py` (18-113) and `bookmarks/api/serializers.py` (63-159): both create paths already delegate to the bookmark service. Edit validation must use the new duplicate identity rather than raw/existing URL equality.
- `bookmarks/services/importer.py` (133-225): Netscape import performs batched matching and `bulk_create`/`bulk_update`; because bulk operations bypass `Bookmark.save()`, the importer must explicitly derive and persist the new key.
- `bookmarks/views/bookmarks.py` (228-426), `bookmarks/templates/bookmarks/bulk_edit_bar.html` (1-44), and `bookmarks/frontend/components/bookmark-page.js` (1-153): current owner-only actions and bulk selection use server POSTs, selected IDs, and Turbo refreshes.
- `bookmarks/forms.py` (161-219), `bookmarks/views/tags.py` (112-168), and `bookmarks/templates/tags/merge.html` (1-56): tag merge provides the form-validation, modal, `transaction.atomic()`, relationship reassignment, and deletion precedent.
- `bookmarks/views/access.py` (6-32): `bookmark_write()` scopes writes to the current owner and returns not found otherwise.
- `bookmarks/urls.py` (22-48) and `bookmarks/templates/shared/nav_menu.html` (4-101): bookmark routes and both desktop/mobile navigation variants have no duplicate-management entry.
- `bookmarks/services/assets.py` (20-238): snapshot/upload assets are durable `BookmarkAsset` rows; completed snapshots update `latest_snapshot`, and asset removal selects the newest completed snapshot.
- `bookmarks/services/preview_image_loader.py` (13-89) and `bookmarks/services/favicon_loader.py` (15-83): previews are URL-hashed per-bookmark files, while favicons are domain-based shared cache files.
- `bookmarks/tests_e2e/helpers.py` (13-150) and `bookmarks/tests_e2e/e2e_test_bookmark_page_bulk_edit.py` (1-350): Playwright helpers and bulk-edit tests establish the UI-test pattern.

### Design alternatives

#### Duplicate identity storage

- **Chosen: indexed `Bookmark.url_duplicate_key`, non-unique.** It makes whole-library grouping and ordinary matching queryable, supports a deterministic data migration, and allows the very duplicates the feature must reconcile.
- **Rejected: change `url_normalized`.** This would silently change an established field's semantics, couple display/save deduplication to tracking policy, and make rollback or future policy changes harder.
- **Rejected: compute keys only while loading the page.** This avoids a migration but requires scanning and parsing every URL in Python for each request, cannot use a database index, and leaves create/import paths inconsistent.
- **Rejected for v1: a separate unique identity/registry table.** It could serialize simultaneous first creates, but adds lifecycle and retry behavior for create, edit, delete, import, and merge solely for a rare race. The indexed field plus explicit review solves the reported problem with materially less schema complexity.

#### Candidate matching

- **Chosen: exact equality after a fixed tracking denylist.** This is explainable and low-risk.
- **Rejected: title/content similarity or generic parameter stripping.** Both increase recall but can group distinct resources and were explicitly excluded by the requester.

#### Merge UX

- **Chosen: dedicated Duplicates page with preview and explicit confirmation.** Group-level selection can enforce that every merge is semantically valid.
- **Rejected: add Merge to the ordinary bookmark bulk-action dropdown.** Arbitrary filtered bookmark selections need not share a key, and the existing bar has no group/survivor preview.
- **Rejected: unattended auto-merge-all.** A matching-policy error would amplify irreversible data loss.

#### Undo and asset retention

- **Chosen: no undo; use an exact preview, an atomic database transaction, and preserve all `BookmarkAsset` rows.**
- **Rejected: tombstones/audit-based undo or a multi-value scalar-asset redesign.** Both require new persistence and UI well beyond the approved v1 boundary.

### Proposed changes

#### 1. Duplicate-key model and normalization

Add `url_duplicate_key = models.CharField(max_length=2048, blank=True, db_index=True)` to `Bookmark`.

Add a dedicated utility such as `normalize_url_for_duplicate_detection(url)` that shares the parsing/reconstruction behavior of `normalize_url()` and filters only the approved case-insensitive query names. Keep `normalize_url()` behavior unchanged.

Update `Bookmark.save()` to derive both normalized fields. Update `Bookmark.query_existing()` to query the new key owner-scoped and return `order_by("date_added", "id")`; retain only a safe fallback for rows with an unexpectedly blank key.

Use two migrations, following the existing `0046`/`0047` normalized-URL pattern:

1. Add the blank indexed field.
2. Backfill every bookmark's duplicate key deterministically, then make runtime code responsible for all future values.

Do not add a uniqueness constraint.

#### 2. Save, edit, and import paths

`create_bookmark()` continues to own form and REST create deduplication and now benefits from the duplicate key. Replace its current overwrite-style `_merge_bookmark_data()` behavior with the no-loss transient-copy reconciliation defined in Behavior 3; tag updates on a create collision must union rather than replace the existing set. SingleFile's existing `query_existing()` call follows the same rule.

Change form and serializer edit validation to reject another owner-owned row with the proposed duplicate key, excluding the edited row.

Extend Netscape parsing/import to carry the duplicate key. Query and match by that key, deduplicate repeated imported entries by that key, set it before `bulk_create`, and include it in `bulk_update`. When a match exists, preserve and reconcile existing notes/tags/state by Behavior 3 instead of overwriting them.

No new public REST endpoint is added. Existing REST create/check behavior reflects the new key because it already calls the shared model/service paths.

#### 3. Detection and merge service

Add `bookmarks/services/duplicates.py` as the sole owner of:

- Owner-scoped duplicate-group queries using `values("url_duplicate_key").annotate(Count("id")).filter(count__gt=1)`.
- Group hydration/prefetch for tags and assets, deterministic member ordering, filtering, and group pagination.
- Pure preview calculation that returns the exact survivor fields and asset summary without mutation.
- Single and bulk merge execution.

For each submitted operation:

1. Enter `transaction.atomic()`; one bulk request uses one outer transaction.
2. Sanitize IDs, re-fetch all rows owner-scoped, apply `select_for_update()` where supported, and verify the submitted grouping/primary invariants against freshly derived keys.
3. Calculate all resulting values once using the Behavior rules.
4. Union tag through-table relationships with `bulk_create(..., ignore_conflicts=True)`.
5. Reassign every source `BookmarkAsset.bookmark_id` to the primary.
6. Select `latest_snapshot` from completed non-empty snapshot assets.
7. Save primary scalar/text/state/date fields.
8. Null source `latest_snapshot` references and clear source preview fields so source deletion cannot remove retained files.
9. Delete selected source rows.
10. Register unretained preview cleanup with `transaction.on_commit`; before deleting each file, confirm no `Bookmark.preview_image_file` still references it.

Any validation or persistence failure rolls back the complete request. File cleanup must not run on rollback.

#### 4. Forms, views, routes, and templates

Add owner-aware forms that validate selected group keys, bookmark IDs, primary IDs, and bulk group payloads without treating posted values as trusted model instances.

Add login-required server-rendered routes:

- `GET /bookmarks/duplicates` — results, filters, pagination, empty state.
- `POST /bookmarks/duplicates/preview` — single or bulk authoritative preview.
- `POST /bookmarks/duplicates/merge` — final confirmed mutation.

Add `bookmarks/views/duplicates.py` and templates under `bookmarks/templates/bookmarks/duplicates/` for the index, group card, preview, and error states. Use Turbo where it reduces full-page reloads, but keep the flow functional as ordinary HTML forms without JavaScript.

Add Duplicates links to desktop and mobile navigation. Add a focused `ld-duplicate-page` component and import it from `bookmarks/frontend/index.js` only for selection/primary/preview affordances; validation and merge rules remain server-side.

#### 5. Expected files

- `bookmarks/models.py`
- `bookmarks/utils.py`
- two new `bookmarks/migrations/` files
- `bookmarks/services/bookmarks.py`
- `bookmarks/services/importer.py`
- new `bookmarks/services/duplicates.py`
- `bookmarks/forms.py`
- `bookmarks/api/serializers.py`
- new `bookmarks/views/duplicates.py`
- `bookmarks/urls.py`
- `bookmarks/templates/shared/nav_menu.html`
- new `bookmarks/templates/bookmarks/duplicates/*.html`
- `bookmarks/frontend/index.js`
- new `bookmarks/frontend/components/duplicate-page.js`
- focused unit/view/service/import/API tests under `bookmarks/tests/`
- new `bookmarks/tests_e2e/e2e_test_duplicate_bookmarks.py`

### Open questions resolved

1. **Which tracking parameters and whether to fuzzy-match:** fixed denylist plus case-insensitive `utm_*`; no fuzzy matching or generic `ref`/`source` stripping.
2. **Stored URL versus match-only canonicalization:** separate persisted key; stored URL and existing normalized URL remain unchanged.
3. **Primary and every field precedence rule:** approved exactly as documented in Behavior 12-17.
4. **What “newest” means for scalar assets:** source bookmark `date_modified` descending, then ID; snapshots use asset `date_created` descending, then ID.
5. **What makes an asset valid:** completed, non-empty snapshot record; existing backing file for preview; non-empty favicon/archive scalar.
6. **How note provenance is represented:** deterministic separator labeled with the source URL; exact duplicate complete notes appear once.
7. **How file deletion remains rollback-safe:** suppress source preview deletion and perform unretained cleanup only with `transaction.on_commit`.
8. **Bulk scope and confirmation:** whole-owner-library detection, display-only filters, selected-group preview, one atomic confirmation, no auto-merge-all.
9. **Undo:** excluded from v1.
10. **Create concurrency:** no unique registry in v1; normal pre-existing matches are reused and rare simultaneous-first-save duplicates remain detectable.
11. **Public API:** no new detection/merge API; existing create/check paths inherit the key.

### Risks and blast radius

- **Normalization drift:** duplicate-key generation must be shared by model, query, edit validation, migration, and bulk importer. Golden URL cases prevent divergent copies.
- **Create/update compatibility:** existing same-URL create behavior overwrites some metadata and replaces tags. The intentional no-loss union/append semantics must be covered for form, REST, SingleFile, and import clients.
- **False positives:** stripping any functional parameter would enable destructive merges. The fixed denylist, preview, and server-side revalidation mitigate this.
- **Large libraries:** grouping must execute in SQL using the indexed key, prefetch group details without N+1 queries, and paginate groups.
- **Data migration time:** backfill touches every bookmark. Keep schema and data migrations separate and document expected deployment behavior.
- **File/database transaction mismatch:** current delete signals remove files immediately. The merge path must clear source preview fields and use on-commit cleanup so rollback cannot lose files.
- **Stale UI/concurrent edits:** preview data can age before confirmation. Re-fetch, lock where supported, recompute keys, and reject the entire stale request.
- **Background asset tasks:** a queued task may target a deleted source bookmark; existing task handlers already tolerate missing bookmarks. Reassigned assets must remain attached to the primary.
- **Non-unique key:** simultaneous first creates can still race. This is an accepted v1 limitation, and resulting rows are immediately discoverable.
- **Irreversibility:** no undo means preview content and all-or-nothing execution are merge blockers, not optional polish.

## Validation and verification criteria

Every criterion must pass before merge.

1. **Duplicate-key URL contract** — verifies Behavior 1-2. Add `bookmarks/tests/test_duplicate_detection.py::test_duplicate_key_ignores_only_approved_tracking_parameters` and parameterize every approved exact key, mixed-case `utm_*`, repeated/blank values, query ordering, trailing slashes, ports/auth, fragments, invalid/empty input, and functional `ref`, `source`, and arbitrary query parameters. The test must show matching keys only where specified and unchanged stored/normalized URLs.

2. **Migration/backfill** — verifies Behavior 1, 5. Add a migration test that creates pre-migration rows, migrates forward, and proves same-owner tracking variants share a populated key while functional-query variants and different users remain distinct. Confirm the field is indexed and non-unique.

3. **New-save recurrence prevention and no-loss reconciliation** — verifies Behavior 3-4. Extend `bookmarks/tests/test_bookmarks_service.py`, `test_bookmarks_api.py`, and `test_importer.py` with tracking-variant cases that fail before the change and pass after it. Form/service create, REST create/check, SingleFile lookup, and Netscape import must reuse the earliest existing row; a functional-query difference must still create a row. Include three or more variants and an existing archived row. Give the existing and incoming copies unique tags and notes plus conflicting unread/shared/archive/title/description/date values; assert the existing URL remains, tags and notes are preserved, and every field follows Behavior 3.

4. **Edit collision validation** — verifies Behavior 1-3, 20. Add form and API tests showing an edit to another owned duplicate key is rejected, a functional-query edit is allowed, and another user's matching key is neither rejected nor exposed.

5. **Owner-scoped group detection** — verifies Behavior 5-7. Add service tests for active plus archived rows, groups of two and four, different owners, non-duplicates, blank keys, deterministic member/group ordering, empty state, and SQL-backed pagination.

6. **Filter semantics** — verifies Behavior 6. Add view/service tests for search text/tag/bundle, unread, shared, date, and all/active/archived filters. A group must appear when one member matches, and its rendered/previewed group must still contain every member.

7. **Single merge field reconciliation** — verifies Behavior 8-15, 19. Add `bookmarks/tests/test_duplicate_merge_service.py` cases for two and four selected rows, user-selected non-default primary, unselected group member retention, tag union, exact-note deduplication and URL separators, unread OR, shared OR, archived AND, primary/fallback title and description, earliest added, latest accessed including all-null, merge-time modified, and primary URL retention.

8. **Hard no-loss assertion** — verifies the requester's explicit requirement and Behavior 12-14. In one regression test, give every source a unique tag and unique note and conflicting unread/shared states; after merge, assert every tag and every unique note string is present and `unread`/`shared` are true when any source was true.

9. **Asset reconciliation** — verifies Behavior 16-18. Add tests with completed, pending, failed, snapshot, and upload assets across all selected rows. Assert every asset row is reparented, no backing asset file is deleted, the newest valid completed snapshot is selected, primary scalar values win, blank primary scalars use the approved fallback ordering, and a missing preview file is skipped.

10. **Preview-file transaction safety** — verifies Behavior 18. Use temporary preview storage to prove a retained source preview survives, an unretained/unreferenced preview is deleted only after commit, a filename still referenced by another bookmark survives, and an injected exception rolls back rows/assets while deleting no file.

11. **Authorization and stale input** — verifies Behavior 11, 20. Add view/service tests for anonymous access, CSRF, another user's IDs, a primary outside selection, fewer than two rows, mixed keys, already-deleted sources, a key changed after preview, GET mutation attempts, and repeated confirmation. Each invalid request must merge nothing and must not disclose inaccessible rows.

12. **Bulk all-or-nothing behavior** — verifies Behavior 10-11. Add `bookmarks/tests/test_duplicate_bulk_merge.py` for at least three groups, deterministic default primaries, per-group override, preview output, and successful one-request merging. Inject one stale/invalid group and assert every otherwise-valid group remains unchanged.

13. **UI rendering and accessibility** — verifies Behavior 7-10, 21. Add view/template tests for desktop/mobile navigation, empty and result states, complete group information, labeled checkboxes/radios, one selected primary, no-submit states, preview warnings, validation errors, and successful result messages.

14. **Browser regression flow** — verifies Behavior 5-11, 19-21. Add `bookmarks/tests_e2e/e2e_test_duplicate_bookmarks.py` that navigates through Duplicates, filters a group without hiding its members, previews and confirms a single merge with a changed primary, then selects and confirms multiple groups in bulk. Assert the source rows disappear, survivors display merged states/tags/notes, and resolved groups leave the page.

15. **Targeted deterministic tests pass.** Run the focused tests with `uv run pytest bookmarks/tests/<affected test file>.py -n auto`, including the new detection, service, bulk, view, API, import, and migration coverage. Run the focused browser file after `make prepare-e2e`.

16. **Full UI suite passes.** Run `make e2e` and resolve any duplicate-page, navigation, Turbo, or bulk-selection regression.

17. **Repository validation gate passes unconditionally.** Run exactly `make lint && make test` from the repository root with no failures.

18. **Required video proof is attached to both records.** Per `factory-ui-verification`, start the real app using the configured app start command, seed at least three safe-match groups containing tracking variants and conflicting tags/notes/unread/shared/archived states, and use computer use to capture a video recording that visibly demonstrates:
    - navigation to automatic whole-library duplicate detection;
    - review, primary change, preview, confirmation, and result of one single-group merge;
    - selection, preview, one confirmation, and results for multiple groups in a bulk merge;
    - retained merged tags/notes and unread/shared state on survivors.

    Attach the reported video recording to OSFG-72 and embed/link it in the PR description. Screenshots alone, a Playwright trace alone, or a video that omits either the single or bulk flow does not satisfy this criterion.
