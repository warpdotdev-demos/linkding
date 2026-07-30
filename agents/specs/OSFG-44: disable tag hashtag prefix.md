*Spec: Add option to disable the hashtag (#) prefix in front of tags (OSFG-44)*

== PRODUCT ==

*Summary:* Add a per-user setting that controls whether the `#` hashtag character is shown before tag names in the bookmark list and bookmark details modal. When the setting is off the `#` is hidden; when it is on (the default) behaviour is identical to today. The `#` is moved from hardcoded HTML to a CSS `::before` rule so it can also be suppressed via the user's Custom CSS field independently of the toggle.

*Key design choices:*
- **Body-class toggle** — a `hide-tag-hashtag` CSS class is added to `<body>` when the setting is off; CSS `::before { content: "#"; }` rules on the affected tag links render the character by default. One body-class switch covers all surfaces without per-template branching, and it preserves the ability to override via Custom CSS.
- **Field name `display_tag_hashtag`** — consistent with the existing `display_url`, `display_view_bookmark_action`, etc. naming pattern; `BooleanField(default=True)` preserves backward compatibility.
- **Scope: bookmark list + details modal only** — tag cloud links already have no `#` prefix; RSS/Atom feeds are machine-readable and out of scope.

*Behavior* (numbered, testable invariants from the user's view):
1. By default (new and existing users), every tag in the bookmark list and bookmark details modal is displayed with a `#` prefix exactly as today — `#tagname`.
2. When the user turns the setting off in Settings → General, the `#` character disappears from all tag links in the bookmark list (inline description and separate description modes) and in the bookmark details modal. The tag name text remains unchanged.
3. When the setting is back on, the `#` reappears. Toggling is immediately effective on the next page load.
4. Tags in the tag cloud (side panel) are unaffected by the setting — they never displayed `#` and continue not to.
5. Authenticated users' tag display on their own bookmark pages and on pages they view (including shared bookmark pages) reflects their own profile setting.
6. For unauthenticated visitors (public shared pages, no guest profile configured), the standard profile is used (`UserProfile()` in `middlewares.py:13`), which defaults `display_tag_hashtag=True` — they always see `#`.
7. A user with the setting off can independently hide `#` on additional surfaces not covered by the toggle by adding a Custom CSS rule such as `.tags a::before { content: ""; }` — the CSS pseudo-element mechanism makes this possible without further code changes.

== TECH ==

*Context:* The codebase at commit `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`.
- Hardcoded `#` appears in **three locations** in the current master:
  - `bookmarks/templates/bookmarks/bookmark_list.html:44 @ fdd4234` — inline description mode tag link: `#{{ tag.name }}`
  - `bookmarks/templates/bookmarks/bookmark_list.html:54 @ fdd4234` — separate description mode tag link: `#{{ tag.name }}`
  - `bookmarks/templates/bookmarks/details/form.html:99 @ fdd4234` — details modal tag link: `#{{ tag.name }}`
- The tag cloud (`bookmarks/templates/bookmarks/tag_cloud.html`) renders just `{{ tag.name }}` — already no `#`.
- `UserProfile` (`bookmarks/models.py:346 @ fdd4234`) holds all per-user display preferences; new boolean fields are added here and wired into the settings form and template.
- `bookmarks/forms.py:306` — `UserProfileForm` lists the `fields` and `widgets` dicts; new fields are added to both.
- `bookmarks/templates/settings/general.html` — settings form template; new checkbox inserted in the "Profile" section, following the same `formfield`/`formhelp` pattern used by `display_url` and others.
- `bookmarks/styles/bookmark-page.css:264 @ fdd4234` — the `.tags { & a { ... } }` block inside `ul.bookmark-list` is where the CSS `::before` rule goes.
- `bookmarks/styles/bookmark-details.css` — has the `.bookmark-details .tags a` selector where the `::before` rule for the details modal goes.
- `bookmarks/templates/shared/layout.html:8 @ fdd4234` — `<body>` tag has no dynamic classes today; we add `{% if not request.user_profile.display_tag_hashtag %}class="hide-tag-hashtag"{% endif %}` here (or an equivalent multi-class pattern when there are other body classes in future).
- Two prior attempts (PR #5 / OSFG-41, PR #8 / OSFG-42) implemented this identically — both used `display_tag_hashtag`, the same CSS class, and the body-class mechanism. PR #5 passed review (0 issues) but was closed by the human without merging. This spec adopts the same proven approach.

*Design alternatives:*
- **Template conditional (per-template `{% if %}`)** — simpler to understand but requires branching in each of the three template locations independently; also makes Custom CSS suppression impossible since no CSS `::before` rule is emitted. Rejected: inferior to the body-class approach for extensibility.
- **CSS custom property (e.g. `--tag-prefix: "#"`)** — theoretically elegant, but CSS custom properties in `content` are not widely supported across older browsers. Rejected: unnecessary complexity and browser compat risk.
- **`tag_prefix_char` string field** — allows an arbitrary prefix character, not just `#`. Over-engineered for a boolean toggle request. Rejected: YAGNI.
- **Body-class toggle (selected)** — a single CSS class on `<body>` controls all tag prefix rendering in one place, is overridable via Custom CSS, and follows the pattern already used by other body-level conditional styles in the codebase.

*Proposed changes:*
1. **`bookmarks/models.py`** — add `display_tag_hashtag = models.BooleanField(default=True, null=False)` to `UserProfile`.
2. **Migration** — new auto-generated migration `bookmarks/migrations/0055_userprofile_display_tag_hashtag.py` (or next available number). `default=True` means existing rows get `True` with no data loss.
3. **`bookmarks/templates/bookmarks/bookmark_list.html`** — change both `#{{ tag.name }}` occurrences (lines 44 and 54) to `{{ tag.name }}`.
4. **`bookmarks/templates/bookmarks/details/form.html`** — change `#{{ tag.name }}` (line 99) to `{{ tag.name }}`.
5. **`bookmarks/styles/bookmark-page.css`** — inside the `.tags { & a { ... } }` block within `ul.bookmark-list`, add:
   ```css
   &::before {
     content: "#";
   }
   ```
   And at the top level (or in a dedicated suppression block):
   ```css
   .hide-tag-hashtag ul.bookmark-list .tags a::before {
     content: "";
   }
   ```
6. **`bookmarks/styles/bookmark-details.css`** — add equivalent `::before` and suppression rules for `.bookmark-details .tags a`.
7. **`bookmarks/templates/shared/layout.html`** — change `<body>` to:
   ```html
   <body{% if not request.user_profile.display_tag_hashtag %} class="hide-tag-hashtag"{% endif %}>
   ```
8. **`bookmarks/forms.py`** — add `"display_tag_hashtag"` to `UserProfileForm.Meta.fields` list and `"display_tag_hashtag": FormCheckbox` to `widgets`.
9. **`bookmarks/templates/settings/general.html`** — add a new `<div class="form-group">` block with the `display_tag_hashtag` checkbox after the `display_url` block (around line 56), following the existing `formfield`/`formhelp` template-tag pattern.

*Open questions resolved:*
- **Shared/public pages affected?** — The guest profile (`standard_profile` in `middlewares.py`) is a non-DB `UserProfile()` instance whose `display_tag_hashtag` field defaults to `True`, so unauthenticated visitors always see `#`. Authenticated users viewing shared bookmark pages of other users do so through their own session profile, so their own setting applies. This is consistent with how `bookmark_link_target` and other profile settings work.
- **Tag cloud scope?** — Out of scope. The tag cloud has never shown `#`. Including it would be a separate behavior change.
- **RSS feeds scope?** — Out of scope. Tag names in RSS item `<category>` elements are machine-readable metadata strings; adding/removing `#` there would be a semantic change not requested.
- **Field name** — `display_tag_hashtag` (matches `display_url`, `display_view_bookmark_action` naming in `UserProfile`).
- **CSS class name** — `hide-tag-hashtag` (clear, distinct from existing classes).
- **Migration number** — use the next available: check `bookmarks/migrations/` and add `0055_...` (or the correct next number); Django auto-generates this correctly.

*Validation & verification criteria* (must ALL pass before merge):
1. **Default on (regression test) — `test_bookmark_list_tag_prefix_default`** — Create a user with the default profile (`display_tag_hashtag=True`), load the bookmark list, verify that tag anchor text includes no literal `#` in the HTML (the character is now CSS-generated) AND that no `hide-tag-hashtag` class is present on `<body>`. Written in `bookmarks/tests/test_bookmarks_list_template.py`. Verifies behavior invariant #1.
2. **Setting off shows no # (regression test) — `test_bookmark_list_tag_prefix_hidden`** — Set `user_profile.display_tag_hashtag=False`, load the bookmark list, verify `<body class="hide-tag-hashtag">` is present in the rendered HTML. Written in `bookmarks/tests/test_bookmarks_list_template.py`. Verifies invariant #2.
3. **Details modal default (regression test) — `test_bookmark_details_tag_prefix_default`** — Load the bookmark details modal for a user with default profile, verify tag anchor text has no literal `#` and no `hide-tag-hashtag` on body. Written in `bookmarks/tests/test_bookmark_details_modal.py`. Verifies invariant #1 for the details surface.
4. **Details modal off (regression test) — `test_bookmark_details_tag_prefix_hidden`** — Set `display_tag_hashtag=False`, load the details modal, verify `hide-tag-hashtag` class on body. Written in `bookmarks/tests/test_bookmark_details_modal.py`. Verifies invariant #2 for the details surface.
5. **Settings form saves toggle (regression test) — `test_update_profile_display_tag_hashtag`** — POST to the settings update view with `display_tag_hashtag=False`, assert `UserProfile.display_tag_hashtag` is `False` after save. POST with it absent/True, assert it reverts to `True`. Written in `bookmarks/tests/test_settings_general_view.py`. Verifies invariant #3.
6. **UserProfile model default (regression test) — `test_display_tag_hashtag_defaults_true`** — Instantiate `UserProfile()`, assert `display_tag_hashtag is True`. Written in `bookmarks/tests/test_user_profile_model.py`. Verifies invariant #1 edge case (standard/default profile).
7. **Tag cloud unaffected** — Load the bookmark list with `display_tag_hashtag=False`, assert tag cloud links (`tag_cloud` section) contain no literal `#` prefix AND no `hide-tag-hashtag` class prevents any rendering (since the tag cloud never emitted `#`). This can be confirmed by the existing tag cloud tests passing unmodified. Verifies invariant #4.
8. **Validation gate** — `make lint && make test` passes with zero failures. This is the `validate_command` for `warpdotdev-demos/linkding`.
9. **Visual proof (user-facing change)** — Exercise the running UI with `computer_use` after implementation and attach screenshots showing: (a) bookmark list with `display_tag_hashtag=True` (default — `#` visible), (b) Settings page with the new checkbox, (c) bookmark list with `display_tag_hashtag=False` (`#` not visible). Attach screenshots to the PR and the Jira ticket. Verifies invariants #1, #2, #3 visually.

Co-Authored-By: Oz <oz-agent@warp.dev>
