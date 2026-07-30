*Spec: Add option to disable the hashtag (#) prefix in front of tags (OSFG-42)*

== PRODUCT ==
*Summary:* Users can opt out of the `#` prefix shown before tag names in bookmark lists and detail views. The `#` moves from hardcoded HTML to a CSS `::before` pseudo-element so it can be suppressed both via a per-user settings toggle and via custom CSS. Default behavior (tags show `#`) is unchanged for all existing users.

*Key design choices:*
- **CSS `::before` + body-class toggle** — moving the `#` to CSS lets power users suppress it with a single custom-CSS rule (`.hide-tag-hashtag .bookmark-list .tags a::before { content: ""; }`) without touching settings. The body class is injected server-side in `layout.html`, matching the existing `display_url`/`display_removed_bookmark_action` pattern in the codebase.
- **UserProfile field (not per-tag / not global)** — the toggle is per-user (like `display_url`), not global config. This respects multi-user deployments and requires no site-admin intervention.
- **Single `agents/specs/` spec PR, reused for implementation** — this draft PR carries the spec now; implementation adds code to the same branch/PR later.

*Behavior* (numbered, testable invariants):
1. **Default on:** Fresh accounts and existing accounts render tag links with the `#` prefix — behavior is identical to pre-feature state.
2. **Toggle in settings:** A "Show tag hash (#) prefix" checkbox appears in Settings → General, after the "Show bookmark URL" row.
3. **Toggle off — bookmark list:** When the toggle is off, all tag links in the bookmark list (`bookmark_list.html`) render without the `#` prefix.
4. **Toggle off — bookmark detail modal:** When the toggle is off, tag links in the bookmark details modal (`details/form.html`) render without the `#` prefix.
5. **CSS-level override:** When the `<body>` carries the class `hide-tag-hashtag`, the `#` pseudo-element is suppressed in both views, regardless of the settings toggle. Custom CSS `{ content: ""; }` on the `::before` also works.
6. **Unauthenticated / public pages:** The body class is only injected for authenticated requests (via `{% if user.is_authenticated %}`); shared/public bookmark pages always show the `#` prefix.
7. **DB migration:** Adding `display_tag_hashtag = BooleanField(default=True, null=False)` to `UserProfile` is backward-safe; migration 0055 applies cleanly without manual data patching (existing rows default to `True`).

== TECH ==
*Context:*
The codebase at `b7f2e1e` is the baseline. Relevant files:
- `bookmarks/models.py` — `UserProfile` model. `display_url`, `tag_search`, `tag_grouping` etc. are existing per-user preference fields. Latest migration is `0054_bookmarkbundle_filter_shared_and_more.py`.
- `bookmarks/forms.py` — `UserProfileForm`: `Meta.fields` list + `Meta.widgets` dict drive which fields appear in the settings UI. `display_url` uses `FormCheckbox` widget.
- `bookmarks/templates/settings/general.html` — settings form with `{% formfield %}` / `{% formhelp %}` template tags per preference row.
- `bookmarks/templates/shared/layout.html` — `<body>` tag currently has no classes; the PR adds a conditional class via `{% if user.is_authenticated and not user_profile.display_tag_hashtag %}hide-tag-hashtag{% endif %}`. The `user_profile` variable is injected by the `UserProfileMiddleware` into the template context.
- `bookmarks/templates/bookmarks/bookmark_list.html` — lines 44, 54: `#{{ tag.name }}` → `{{ tag.name }}`.
- `bookmarks/templates/bookmarks/details/form.html` — line 99: `#{{ tag.name }}` → `{{ tag.name }}`.
- `bookmarks/styles/bookmark-page.css` — `.bookmark-list .tags a` rule at line 264; `::before` to be added there.
- `bookmarks/styles/bookmark-details.css` — `.bookmark-details .tags a` rule at line 81; `::before` to be added there.

A complete working implementation already exists on the closed PR #5 (`factory/osfg-41-disable-tag-hashtag-prefix`). The implementation agent **must** re-implement from scratch on this branch (that PR was never merged and its branch diverged from master before the #6 and #7 merges); reading PR #5's diff (`gh pr diff 5 --repo warpdotdev-demos/linkding`) as a reference is fine and encouraged.

*Design alternatives:*
- **CSS `::before` + body-class vs. template conditional** — A pure template conditional (`{% if user_profile.display_tag_hashtag %}#{% endif %}`) would work but prevents CSS-level override (requirement 5). Body-class approach chosen.
- **`UserProfile` field vs. global site setting** — A global admin setting (e.g. Django `constance` or `.env`) would affect all users. Per-user `UserProfile` field chosen to match existing settings UX and enable per-user preference.
- **Body-class injection in layout.html vs. middleware** — Layout template injection is the established pattern (`UserProfileMiddleware` already populates `user_profile` in context). No new middleware needed. Chosen.
- **New CSS file vs. additions to existing CSS files** — Keeping the rules in `bookmark-page.css` and `bookmark-details.css` (each scoped to its component) is cleaner than a new global file. Chosen.

*Open questions resolved:*
- *Which views need the `#` removed?* Bookmark list (both compact and grid rows) and details modal — confirmed from PR #5 diff (3 template locations total). Shared/public pages do not need changes.
- *Should the `#` appear in the tag filter input or tag cloud?* No — those locations do not render `#{{ tag.name }}`; no change needed there.
- *Does this affect the REST API?* No — the API serializes tag names without a `#`; no API change required.
- *Can non-admin custom CSS already suppress the `#`?* Not today (it's hardcoded HTML text). After this feature, yes — because it's a CSS pseudo-element. This satisfies requirement 2 of the original feature request.

*Proposed changes:*
1. **`bookmarks/models.py`** — add `display_tag_hashtag = models.BooleanField(default=True, null=False)` to `UserProfile` (after `display_url`).
2. **`bookmarks/migrations/0055_userprofile_display_tag_hashtag.py`** — auto-generated migration adding the field.
3. **`bookmarks/templates/bookmarks/bookmark_list.html`** — change `#{{ tag.name }}` → `{{ tag.name }}` in both tag-rendering locations (lines 44, 54 on master).
4. **`bookmarks/templates/bookmarks/details/form.html`** — change `#{{ tag.name }}` → `{{ tag.name }}` at line 99.
5. **`bookmarks/styles/bookmark-page.css`** — inside `.bookmark-list .tags a { ... }` add `&::before { content: "#"; }`. After `.bookmark-list` add `.hide-tag-hashtag .bookmark-list .tags a::before { content: ""; }`.
6. **`bookmarks/styles/bookmark-details.css`** — inside `.bookmark-details .tags a { ... }` add `&::before { content: "#"; }`. After the selector add `.hide-tag-hashtag .bookmark-details .tags a::before { content: ""; }`.
7. **`bookmarks/templates/shared/layout.html`** — extend `<body>` to `<body{% if user.is_authenticated and not user_profile.display_tag_hashtag %} class="hide-tag-hashtag"{% endif %}>`.
8. **`bookmarks/forms.py`** — add `display_tag_hashtag` to `UserProfileForm.Meta.fields` and `Meta.widgets` with `FormCheckbox`.
9. **`bookmarks/templates/settings/general.html`** — add `{% formfield form.display_tag_hashtag label="Show tag hash (#) prefix" %}` after the `display_url` row.

*Validation & verification criteria* (must ALL pass before merge):
1. **No literal `#` in rendered tag HTML (default on)** — run `uv run pytest bookmarks/tests/test_bookmarks_list_template.py -n auto -k test_display_tag_hashtag_default` (new test): assert no `>#` in tag anchor inner HTML; assert `hide-tag-hashtag` class is absent from `<body>`.
2. **`hide-tag-hashtag` class absent when toggle is on** — `uv run pytest -k test_display_tag_hashtag_no_hide_class_by_default`: render bookmark list for a user with `display_tag_hashtag=True`; assert body tag does not contain `hide-tag-hashtag`.
3. **`hide-tag-hashtag` class present when toggle is off** — `uv run pytest -k test_display_tag_hashtag_disabled`: render bookmark list for a user with `display_tag_hashtag=False`; assert body tag contains `class="hide-tag-hashtag"`.
4. **Details modal — default on** — `uv run pytest bookmarks/tests/test_bookmark_details_modal.py -k test_display_tag_hashtag_default_details_modal`: assert no literal `>#` in tag anchor HTML in details modal.
5. **Details modal — toggle off** — `uv run pytest bookmarks/tests/test_bookmark_details_modal.py -k test_display_tag_hashtag_disabled_details_modal`: render details modal with `display_tag_hashtag=False`; assert body carries `hide-tag-hashtag`.
6. **UserProfile defaults to True** — `uv run pytest bookmarks/tests/test_user_profile_model.py -k test_display_tag_hashtag_is_enabled_by_default`: create a fresh `UserProfile`; assert `display_tag_hashtag is True`.
7. **Settings form saves the field** — `uv run pytest bookmarks/tests/test_settings_general_view.py -k test_update_profile_display_tag_hashtag`: POST to general settings with `display_tag_hashtag=False`; assert the saved profile has the field set to `False`.
8. **Migration applies cleanly** — `uv run manage.py migrate --run-syncdb` exits 0 on a fresh SQLite DB; existing DB after squash also applies cleanly.
9. **Full validation gate passes** — `make lint && make test` exits 0 with all existing tests passing plus the 7 new regression tests above.
10. **Visual proof — tags with `#` prefix (default on)** — exercise the running UI via computer use: start app with `make init && uv run manage.py runserver 8000`, log in, navigate to the bookmark list; capture a screenshot showing tag links rendered with the `#` prefix. Attach screenshot to the PR.
11. **Visual proof — settings toggle** — navigate to Settings → General; capture a screenshot showing the "Show tag hash (#) prefix" checkbox present and checked (default). Attach to PR.
12. **Visual proof — tags without `#` prefix (toggle off)** — uncheck "Show tag hash (#) prefix", save, return to bookmark list; capture a screenshot showing tag links rendered **without** the `#` prefix. Attach to PR.
