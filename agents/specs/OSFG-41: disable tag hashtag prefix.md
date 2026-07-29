*Spec: Option to disable the Hashtag Prefix # in front of tags*

== PRODUCT ==
*Summary:* The `#` prefix before tag names is hardcoded in HTML templates. This feature moves the `#` to a CSS `::before` pseudo-element and adds a `UserProfile` toggle (`display_tag_hashtag`, default on) that lets users remove the visual hashtag prefix entirely.

*Key design choices:*
1. **CSS `::before` not HTML**: The `#` is moved from three template locations to CSS `::before` pseudo-elements so it can be suppressed purely via CSS without template logic in tag-rendering loops.
2. **Body-level suppression class**: When `display_tag_hashtag=False`, a `hide-tag-hashtag` class is added to `<body>` in `layout.html` (where `request.user_profile` is already available via middleware). A single suppression rule in each CSS file then suppresses the `::before` everywhere, covering both the bookmark list and the details modal without duplicating template conditionals.
3. **Field name `display_tag_hashtag` (BooleanField, default=True)**: Consistent with the existing `display_url`, `display_view_bookmark_action` naming pattern in `UserProfile`.

*Behavior* (numbered, testable invariants from the user's/consumer's view):
1. **Default on** — by default, `display_tag_hashtag` is `True`; the `#` prefix is shown before every tag in the bookmark list and details modal, identical to current behavior.
2. **Toggle off** — when a user sets `display_tag_hashtag=False` in Settings → General and saves, all tag links on every page immediately render without the `#` prefix.
3. **Settings page** — the new toggle appears as a checkbox labelled "Show tag hash (#) prefix" in the General settings section, alongside existing display options (e.g. "Show bookmark URL").
4. **Custom CSS override** — a user with `display_tag_hashtag=True` can still override the prefix via Custom CSS targeting `.tags a::before` (no regression to existing custom-CSS capability).
5. **Shared/public pages** — the guest profile defaults to `display_tag_hashtag=True`; public shared bookmark pages are unaffected.
6. **Tag cloud** — the tag cloud (`tag_cloud.html`) does not render `#` before tags and is unchanged by this feature.

== TECH ==
*Context:* The `#` is currently hardcoded in three template locations:
- `bookmarks/templates/bookmarks/bookmark_list.html:44 @ 30510d3` — `#{{ tag.name }}` in the inline description tags span
- `bookmarks/templates/bookmarks/bookmark_list.html:54 @ 30510d3` — `#{{ tag.name }}` in the separate tags div
- `bookmarks/templates/bookmarks/details/form.html:99 @ 30510d3` — `#{{ tag.name }}` in the details modal tags section

Relevant CSS:
- `bookmarks/styles/bookmark-page.css (264-272) @ 30510d3` — `.bookmark-list li .tags a` sets color and spacing; no `::before` rule exists
- `bookmarks/styles/bookmark-details.css (81-83) @ 30510d3` — `.bookmark-details .tags a` sets color; no `::before` rule exists

`UserProfile` at `bookmarks/models.py (346-460) @ 30510d3` already has many `display_*` and `enable_*` BooleanFields (`display_url`, `display_view_bookmark_action`, etc.).

`UserProfileForm` at `bookmarks/forms.py (306-368) @ 30510d3` is a `ModelForm` with the fields/widgets dicts; adding a new field follows the established pattern.

`bookmarks/templates/shared/layout.html @ 30510d3` has a bare `<body>` tag; `request.user_profile` is available there via `LinkdingMiddleware` (set for all users, authenticated or guest).

*Design alternatives:*
- **`BookmarkListContext` flag** — pass `display_tag_hashtag` through `BookmarkListContext` and render `{% if ... %}#{% endif %}` in each tag loop. Rejected: requires changes to `contexts.py`, the context object, and two template loops; also doesn't cover the details modal without a third change point. The CSS body-class approach is simpler.
- **Direct template check with `request.user_profile`** — use `{% if request.user_profile.display_tag_hashtag %}#{% endif %}` in each loop. Simpler than the context path but produces inline template logic in three places; foregoes the CSS `::before` decoupling.
- **Selected: CSS `::before` + body class** — removes all `#` from HTML, adds pure-CSS rendering, and uses a single body class for suppression. Minimal template change (one attribute on `<body>`), no view logic, and is consistent with how other display settings are applied.

*Proposed changes:*

1. **`bookmarks/models.py`** — Add after the existing `display_remove_bookmark_action` field (line 445):
   ```python
   display_tag_hashtag = models.BooleanField(default=True, null=False)
   ```

2. **Migration** — New file `bookmarks/migrations/0040_userprofile_display_tag_hashtag.py` (or next sequential number) created via `python manage.py makemigrations`.

3. **`bookmarks/forms.py`** — Add `"display_tag_hashtag"` to `UserProfileForm.Meta.fields` and `"display_tag_hashtag": FormCheckbox` to `widgets`.

4. **`bookmarks/templates/bookmarks/bookmark_list.html`** — Remove `#` from lines 44 and 54: `#{{ tag.name }}` → `{{ tag.name }}`.

5. **`bookmarks/templates/bookmarks/details/form.html`** — Remove `#` from line 99: `#{{ tag.name }}` → `{{ tag.name }}`.

6. **`bookmarks/styles/bookmark-page.css`** — Inside the `.bookmark-list li .tags` block (line 264), add:
   ```css
   & a::before {
     content: "#";
   }
   ```
   Below the block (or in a global scope within the file), add the suppression rule:
   ```css
   .hide-tag-hashtag .bookmark-list .tags a::before {
     content: none;
   }
   ```

7. **`bookmarks/styles/bookmark-details.css`** — Inside `.bookmark-details .tags a` (line 81), add the `::before` rule, and add suppression:
   ```css
   & .tags a::before {
     content: "#";
   }
   .hide-tag-hashtag .bookmark-details .tags a::before {
     content: none;
   }
   ```

8. **`bookmarks/templates/shared/layout.html`** — Update the `<body>` opening tag:
   ```html
   <body{% if request.user.is_authenticated and not request.user_profile.display_tag_hashtag %} class="hide-tag-hashtag"{% endif %}>
   ```

9. **`bookmarks/templates/settings/general.html`** — Add a new `<div class="form-group">` block after the `display_url` group (line 56), following the exact pattern of the surrounding fields:
   ```html
   <div class="form-group">
     {% formfield form.display_tag_hashtag label="Show tag hash (#) prefix" has_help=True %}
     {% formhelp form.display_tag_hashtag %}
       When enabled, displays a hash (#) character before each tag. Disable to show tags without the prefix.
     {% endformhelp %}
   </div>
   ```

*Open questions resolved:*
- **Where to place the CSS class**: body-level (chosen, see Design alternatives above). No per-container approach is needed.
- **CSS `none` vs. empty string for suppression**: `content: none` is the correct CSS value to remove a pseudo-element's content entirely; `content: ""` would leave a zero-width element.
- **Should the guest profile suppress `#`?**: No — `display_tag_hashtag` defaults to `True`, so public/shared pages are unaffected without any action.
- **Tag cloud**: Does not use `#` or the `.tags` CSS class in the same way; no change needed.
- **`null=False` on the new field**: Consistent with all other BooleanFields on `UserProfile`; migration safe because `default=True` fills existing rows.

*Validation & verification criteria* (must ALL pass before merge):

1. **Tag HTML has no literal `#`** — In the rendered HTML of any bookmark list page, no tag link element contains a literal `#` character before the tag name. Checked by: `test_display_tag_hashtag_default` — assert response HTML does not contain `>#tagname<` pattern for a known tag.

2. **CSS `::before` renders `#` by default** — A new regression test `test_display_tag_hashtag_default` in `bookmarks/tests/test_bookmarks_list_template.py`: create a bookmark with a tag, render the list template with the default profile (`display_tag_hashtag=True`), confirm the rendered HTML does not contain a literal `#` in the tag anchor text (the `#` now comes from CSS, not HTML), and confirm no `hide-tag-hashtag` class appears on `<body>`.

3. **Toggle off suppresses `::before` via body class** — `test_display_tag_hashtag_disabled` in the same file: render with `display_tag_hashtag=False`, confirm `<body class="hide-tag-hashtag">` is present in the layout response. (CSS rendering itself is not testable in Python; the class presence is the contract.)

4. **Details modal also controlled** — `test_display_tag_hashtag_details_modal` in `bookmarks/tests/test_bookmark_details_modal.py` (or add to the existing suite): render details for a bookmark with tags and assert no literal `#` in tag anchor text, and that `hide-tag-hashtag` body class appears when `display_tag_hashtag=False`.

5. **`UserProfile.display_tag_hashtag` defaults to `True`** — `test_user_profile_display_tag_hashtag_default` in `bookmarks/tests/test_user_profile.py` (or add inline): create a user profile and assert `profile.display_tag_hashtag == True`.

6. **Settings form saves the toggle** — Integration test (or extend existing settings view test in `bookmarks/tests/test_settings_view.py`): POST to the settings update URL with `display_tag_hashtag=False`, reload profile from DB, assert `display_tag_hashtag == False`. POST again with `display_tag_hashtag=True`, assert it reverts.

7. **No collateral damage — existing display settings unaffected** — All currently passing tests for `display_url`, `enable_favicons`, tag display, and shared bookmarks continue to pass after the change.

8. **Validation gate passes** — `make lint && make test` exits 0 with no failures.

9. **Visual proof via computer use** — Start the app (`make init && uv run manage.py runserver 8000`), log in, screenshot the bookmark list showing tags with `#` prefix (default on). Toggle off in Settings → General → "Show tag hash (#) prefix", save, screenshot the bookmark list again confirming tags now appear without `#`. Attach both screenshots as proof.
