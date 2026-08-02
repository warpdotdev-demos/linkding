# OSFG-58: Add an unread indicator chip

*Proposed change: Replace the subtle italic-only unread cue with an explicit `Unread` chip beside each unread bookmark title.*

## Summary

Unread bookmarks are currently identifiable only by italic title text. Add a compact, textual `Unread` chip to the existing bookmark-list title row while preserving the current unread data model, actions, favicon placement, title truncation, shared lists, and preview rendering. This is a template-and-CSS change only.

The design is grounded in `master` commit `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`.

## Key design choices

1. Use the visible text `Unread`, not a dot or icon, so the state is explicit and does not rely on color or prior icon knowledge.
2. Render the chip as a non-interactive sibling immediately after the unchanged title link. The title link shrinks and ellipsizes; the chip remains fully visible.
3. Use a dedicated, bookmark-scoped class with existing linkding theme tokens rather than the generic `.badge` overlay component.
4. Remove the italic unread title treatment. The chip becomes the sole title-row state cue, while the existing `Unread` action remains the mark-as-read control.
5. Render the chip wherever the shared list-item template receives `bookmark_item.unread`, including shared and preview lists. Existing ownership and preview rules continue to control actions independently.

## Product behavior

1. An unread bookmark displays one compact `Unread` chip adjacent to its title.
2. A read bookmark displays no unread chip and uses normal title typography.
3. The chip is informational, not a control. Clicking it does not gain an independent action or enlarge the bookmark link's accessible name/click target.
4. For an owned unread bookmark, the existing `Unread` action still opens the `Mark as read?` confirmation. Confirming re-renders the row without the chip or action and leaves the title in normal typography.
5. An unread shared bookmark still displays the chip even when the viewer cannot mark it as read. This is not new data exposure: the shared row already exposes unread state through its `unread` class and italic styling.
6. An unread preview bookmark displays the chip while preview-specific rules continue to hide bulk selection and actions.
7. The chip remains legible in light and dark themes and fully visible beside short, long, and truncated titles at desktop and narrow/mobile widths.

## Technical approach

### Current context

- `bookmarks/templates/bookmarks/bookmark_list.html:12-32 @ fdd4234` renders the shared list-item title structure. `bookmark_item.unread` is already available directly in this template.
- `bookmarks/views/contexts.py:126-195 @ fdd4234` exposes `BookmarkItem.unread`, builds the existing `unread` CSS class, and independently gates `show_mark_as_read` by ownership. No context, view, model, serializer, API, or migration change is needed.
- `bookmarks/styles/bookmark-page.css:178-244 @ fdd4234` positions the favicon absolutely, pads the immediately adjacent title link, applies single-line ellipsis, and contains the italic-only unread rule.
- `bookmarks/frontend/components/bookmark-page.js:19-41 @ fdd4234` expects `.title > a` and measures its first title `<span>` for truncation tooltips.
- `bookmarks/templates/bundles/preview.html:1-9 @ fdd4234` uses the same bookmark-list template with `is_preview=True`.

### Proposed changes

1. In `bookmarks/templates/bookmarks/bookmark_list.html`, leave the existing title anchor and its title `<span>` unchanged. Immediately after the anchor and still inside `.title`, conditionally render a semantic text element such as `<span class="unread-indicator">Unread</span>` when `bookmark_item.unread` is true.
2. In `bookmarks/styles/bookmark-page.css`, make the title row a flex container for unread rows, aligned vertically with `gap: var(--unit-2)`.
3. Allow the title anchor to shrink without overflowing by using `flex: 0 1 auto`, `min-width: 0`, and `width: auto` while retaining its current single-line `overflow: hidden` and `text-overflow: ellipsis` behavior. Keep the favicon before and directly adjacent to the anchor so `.title img + a { padding-left: 22px; }` still applies.
4. Make `.unread-indicator` non-shrinking and single-line. Match the existing badge visual language with `background: var(--primary-color)`, `color: var(--contrast-text-color)`, `font-size: var(--font-size-sm)`, compact `var(--unit-1)`/`var(--unit-2)` spacing, and `var(--border-radius-lg)`. Set `font-style: normal`.
5. Remove the existing `&.unread .title a { font-style: italic; }` rule.
6. Do not add JavaScript or branch on ownership, list type, or `is_preview`; the existing unread boolean and shared template provide the intended behavior on every list surface.

## Design alternatives

### Text chip versus dot, icon, or row tint

- **Selected: textual `Unread` chip.** It is self-explanatory, communicates without color, and is distinct from the existing action.
- **Rejected: dot, icon, or row tint.** These use less width but are ambiguous, color-dependent, or easily confused with the existing unread action icon.

### Dedicated inline class versus existing `.badge`

- **Selected: dedicated `.unread-indicator` using existing tokens.** It keeps the styling local to bookmark rows while reusing linkding's color, type, spacing, and radius system.
- **Rejected: generic `.badge` from `bookmarks/styles/theme/badges.css`.** That component creates translated `::after` overlay content and is designed for buttons, avatars, and tabs. Reusing it inline would risk clipping, overlap, and link decoration.

### Sibling after the title link versus inside the link

- **Selected: sibling immediately after `.title > a`.** The chip stays informational, preserves the link's accessible name and existing tooltip contract, and can remain visible while the anchor truncates.
- **Rejected: inside the anchor.** This would make `Unread` part of the link's accessible name and click target, inherit link hover/underline behavior, and complicate the existing first-span tooltip measurement.

### Replace versus retain italics

- **Selected: remove italics.** The explicit text-and-shape cue is clearer, avoids redundant visual noise, improves long-title readability, and keeps typography stable when the state changes.
- **Rejected: retain italics alongside the chip.** It adds a redundant cue without improving accessibility once the textual chip exists.

## Open questions resolved

- **Badge text or dot?** Use the text `Unread`.
- **Which style to reuse?** Reuse the generic badge palette and existing theme tokens, but not the overlay-oriented `.badge` class.
- **Where does the chip go?** Immediately after the unchanged title anchor as a flex sibling; never between the favicon and anchor.
- **How does truncation behave?** Only the title anchor shrinks and ellipsizes; the chip is non-shrinking.
- **Does italic styling stay?** No; remove it.
- **Do shared and preview lists show the chip?** Yes whenever their bookmark item is unread; existing action visibility remains unchanged.
- **How are themes handled?** Use `--primary-color` and `--contrast-text-color`, which are already overridden by the dark theme and provide small-text contrast in both themes.
- **Are data or API changes needed?** No. The scope is template, CSS, and focused template tests only.

## Affected files

- `bookmarks/templates/bookmarks/bookmark_list.html`
- `bookmarks/styles/bookmark-page.css`
- `bookmarks/tests/test_bookmarks_list_template.py`

No other production file should change.

## Risks and mitigations

- Incorrect flex sizing could hide the chip, disable ellipsis, or overflow beside preview images. Keep `min-width: 0` on the content and anchor, make only the anchor shrink, and verify desktop plus narrow layouts.
- Inserting the chip between the favicon and anchor would break the existing adjacent-sibling padding and cause overlap. Preserve the current favicon-anchor adjacency.
- Restructuring the anchor or its first title `<span>` could break truncation tooltips. Leave both unchanged and verify hover/focus on a truncated title.
- A stale Turbo update could leave the chip after mark-as-read. Exercise the existing confirmation flow end to end and verify the same row re-renders.
- Shared and preview lists could accidentally expose actions. Keep the chip conditional independent of action rendering and cover both surfaces in template tests.
- A generic class could collide with other badge components. Scope the new class to the bookmark title row.

## Validation and verification criteria

All criteria must pass before merge.

1. Add focused failing-then-passing coverage in `bookmarks/tests/test_bookmarks_list_template.py` proving an unread bookmark renders exactly one `.unread-indicator` whose normalized text is `Unread`, while a read bookmark renders none.
2. In the same file, prove an unread non-owned shared bookmark renders the indicator while its mark-as-read action remains absent.
3. In the same file, prove an unread `is_preview=True` item renders the indicator while its bulk checkbox and actions remain absent; a read preview item renders no indicator.
4. Keep the existing unread and action tests green, including `test_should_reflect_unread_state_as_css_class`, `test_should_reflect_both_unread_and_shared_state_as_css_class`, `test_show_mark_as_read_when_unread`, `test_hide_mark_as_read_when_read`, and `test_hide_mark_as_read_for_non_owned_bookmarks`.
5. Keep `bookmarks/tests/test_bookmark_action_view.py::BookmarkActionViewTestCase::test_mark_as_read` green to prove the existing state mutation remains unchanged.
6. Run the focused suite successfully: `uv run pytest bookmarks/tests/test_bookmarks_list_template.py -n auto`.
7. Run `make format`, confirm formatting changes are limited to the intended template/CSS/test files, and run `npm run build` successfully so the light and dark theme bundles compile.
8. Run the unconditional repository validation gate successfully from the repo root: `make lint && make test`.
9. Apart from this committed spec artifact, confirm the implementation diff contains only the template, CSS, and focused test changes listed above. There must be no model, migration, API, serializer, view, context, or JavaScript changes.
10. Verify the rendered chip uses readable text and has at least 4.5:1 text/background contrast in both light and dark themes.
11. At desktop and approximately 375 px width, verify with favicons both enabled and disabled and with a deliberately long title that:
    - the favicon does not overlap the title;
    - the title remains one line and ellipsizes;
    - the `Unread` chip stays fully visible;
    - an enabled preview image does not force horizontal overflow; and
    - hovering or focusing a truncated title still exposes the existing full-title tooltip.
12. Verify bulk-edit mode keeps its checkbox positioned and interactive without shifting or overlapping the title or chip.
13. Verify shared and bundle-preview pages render the chip for unread items and omit it for read items, while non-owner mutation controls and preview controls remain absent.
14. Capture **video evidence; screenshots alone are insufficient**. The recording must show:
    - a mixed read/unread list in light theme with the chip present only on unread rows;
    - the equivalent state in dark theme;
    - a narrow viewport with a favicon, long ellipsized title, and fully visible chip;
    - unread rendering on the shared and bundle-preview surfaces; and
    - the complete owned-bookmark flow: select the existing `Unread` action, see `Mark as read?`, confirm, and observe the same row re-render with the chip absent, action absent, and normal title typography.
15. Attach the final video to both OSFG-58 and the implementation PR body. The change is not verified and must not be accepted without this recording.
