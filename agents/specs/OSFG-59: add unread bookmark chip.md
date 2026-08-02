*Spec: Add a clear unread bookmark chip*

== PRODUCT ==

*Summary:* Bookmark rows currently communicate unread state only by italicizing the title, which is easy to miss while scanning. Add a compact, visible `Unread` text chip beside unread bookmark titles without changing unread data or actions.

*Key design choices:* Render a real text `<span>` from the existing `bookmark_item.unread` value; keep italics as a secondary cue; use an unread-only flex layout that preserves title ellipsis and reserves space for a non-shrinking chip; render the chip in every active, archived, shared, and preview use of the common list template.

*Behavior*:
1. A bookmark with `unread = true` shows one text chip labelled `Unread` immediately beside its title.
2. A bookmark with `unread = false` shows no unread chip.
3. The chip is visually distinct through a solid theme-primary background, contrasting text, compact spacing, and the existing border radius; it remains legible in light and dark themes.
4. Long titles remain on one line and ellipsize before the chip. The chip remains visible, does not shrink or wrap, and does not disturb favicon or bulk-edit-checkbox alignment.
5. The layout remains intact with preview images enabled or disabled, inline or separate descriptions, and at viewport widths of 600 px or less.
6. The common title treatment applies to active, archived, shared/anonymous, and preview list variants whenever their `BookmarkItem.unread` value is true. Shared and preview variants show the state chip even when edit actions are unavailable.
7. Confirming the existing row action labelled `Unread` marks that bookmark read, updates the row in place, and removes both the chip and the mark-as-read action. Marking the bookmark unread again causes the chip to render again.
8. Existing confirmation text, action visibility rules, Turbo partial-update behavior, and all other bookmark-row content remain unchanged.
9. `Unread` is rendered as DOM text, not generated content, so assistive technologies can announce the state without an additional ARIA label.

== TECH ==

*Context:*
- `bookmarks/views/contexts.py:150 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` already assigns `BookmarkItem.unread`, and `bookmarks/views/contexts.py:156-164 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` already derives the row's `unread` CSS class. No model, context, API, serializer, or migration change is needed.
- `bookmarks/templates/bookmarks/bookmark_list.html:16-31 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` renders the shared title block with an optional absolutely positioned favicon and a full-width title anchor, but no unread-state element.
- `bookmarks/styles/bookmark-page.css:189-213 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` positions the favicon and gives the anchor `display: block`, `width: 100%`, and nowrap/overflow/ellipsis behavior. `bookmarks/styles/bookmark-page.css:242-244 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` adds italics as the only unread treatment.
- `bookmarks/styles/theme/variables.css:14-39,90-99 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` and `bookmarks/styles/theme-dark.css:16-39 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` define the existing primary, contrasting-text, spacing, font-size, and radius tokens used by both themes.
- `bookmarks/tests/test_bookmarks_list_template.py:607-640 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` already tests unread/shared row classes; the same test class also renders shared and preview variants.
- Triage reproduced the baseline in the running app: unread rows have italic titles but no chip; the mark-as-read confirmation updates only the selected row in place and removes its existing unread styling/action.

*Design alternatives:*
- **State markup:** A real `<span>` is selected over a CSS pseudo-element or icon/dot. It satisfies the requested text label and accessibility requirement without duplicating state in ARIA. Generated content and decorative icons are less reliable for assistive technology and less explicit for users.
- **Title/chip layout:** An unread-only flex row is selected over dropping an inline sibling into the current block layout or absolutely positioning the chip. Flex allows the anchor to shrink and ellipsize while the chip remains visible; the alternatives either wrap/push the chip away or require fragile offsets.
- **Existing italics:** Keep the italic rule as secondary reinforcement. Removing it would be a separate visual-language change with no benefit to scope; the new chip becomes the primary signal.
- **Variant coverage:** Render in all uses of `bookmark_list.html` rather than gating on `is_preview`, editability, or list context. Unread is already present on the view model and row class in those variants; the chip displays state, unlike the separately gated mark-as-read action.
- **Visual treatment:** Use `var(--primary-color)` with `var(--contrast-text-color)` rather than inventing new tokens or using the existing `.badge` pattern. The current `.badge` is generated dot/count content, not a reusable text chip; the selected tokens already adapt to light and dark themes and provide the strongest scan cue.

*Proposed changes:*
1. In `bookmarks/templates/bookmarks/bookmark_list.html`, immediately after the title anchor and still inside `.title`, conditionally render `<span class="unread-chip">Unread</span>` when `bookmark_item.unread` is true. Do not gate it on `bookmark_list.is_preview`, ownership, sharing, or action visibility.
2. In `bookmarks/styles/bookmark-page.css`, make `.title` a flex container only for unread rows with centered alignment and `var(--unit-2)` gap. Override the unread title anchor to `flex: 0 1 auto`, `width: auto`, and `min-width: 0` while retaining its existing nowrap/overflow/ellipsis and italic rules. Style `.unread-chip` with `flex: 0 0 auto`, `white-space: nowrap`, `padding: 0 var(--unit-1)`, `border-radius: var(--border-radius)`, `background: var(--primary-color)`, `color: var(--contrast-text-color)`, `font-size: var(--font-size-sm)`, `font-style: normal`, `font-weight: 500`, and `line-height: var(--line-height)`.
3. In `bookmarks/tests/test_bookmarks_list_template.py`, add a focused helper/assertion for `<span class="unread-chip">Unread</span>`. Extend the existing unread-state test to require exactly one chip, add the read-state negative assertion, and add focused assertions to the existing shared/non-owned and preview rendering coverage proving the state chip remains while the mark-as-read action is hidden. Do not add model, API, JavaScript, or broad end-to-end test changes.

*Open questions resolved:*
- **Keep or remove italics?** Keep them as a secondary cue; the chip is the new primary indicator.
- **Which list variants receive the chip?** All variants rendered through the common template, including shared/anonymous and preview, because the chip communicates state rather than editability.
- **Does the chip need extra ARIA?** No. Its visible DOM text is the accessible label; a pseudo-element is explicitly excluded.
- **Should the transition animate?** No. Preserve the current immediate Turbo row replacement; animation would add behavior and scope.

*Risks / blast radius:*
- The flex override can break truncation if `min-width: 0`, `width: auto`, or the chip's non-shrinking behavior is omitted. The implementation and visual proof must exercise a deliberately long title.
- The absolute favicon and bulk-edit checkbox depend on existing positioning. The selected approach leaves those rules untouched, but visual verification must cover favicon on/off and bulk-edit alignment.
- The mark-as-read button and state chip share the word `Unread`; tests and computer-use interactions must identify the chip by `.unread-chip` and the action by its button role/name.
- Theme or responsive regressions are visual rather than fully expressible in the Django template test, so the required running-UI video is part of acceptance, not optional supporting evidence.

*Validation & verification criteria* (must ALL pass before merge):
1. Re-run the confirmed baseline with at least one unread and one read bookmark. Before the change, the focused chip assertion fails because no `.unread-chip` exists; after the change, each unread row contains exactly one `.title > .unread-chip` whose text is `Unread`, while read rows contain none. Check with the extended `BookmarkListTemplateTest.test_should_reflect_unread_state_as_css_class` plus the new read-state negative assertion.
2. The focused template coverage proves shared/non-owned and preview rendering still includes the unread chip while their existing mark-as-read-action assertions remain absent. Run `uv run pytest bookmarks/tests/test_bookmarks_list_template.py -n auto`.
3. Inspection of the final diff shows changes only to `bookmarks/templates/bookmarks/bookmark_list.html`, `bookmarks/styles/bookmark-page.css`, `bookmarks/tests/test_bookmarks_list_template.py`, and this committed spec. There are no model, context, migration, serializer, API, JavaScript, or dependency changes.
4. In the running app, unread and read rows are visibly distinguishable in both light and dark themes. The chip uses the selected existing CSS custom properties, remains readable, and is exposed as text in the accessibility tree.
5. In the running app, a long unread title ellipsizes on one line while its chip remains visible and unwrapped. Verify with favicons on and off, bulk-edit mode on, preview images on and off, inline and separate description modes, and a viewport at or below 600 px; no title, chip, favicon, checkbox, or preview image overlaps or shifts out of its row.
6. Active, archived, shared/anonymous, and preview list rendering show the chip when the rendered bookmark is unread and omit it when read. Action availability remains determined by the existing ownership/preview rules.
7. The existing mark-as-read flow remains unchanged: click the row's `Unread` button, observe the `Mark as read?` confirmation, confirm, and verify the row updates without a full navigation, the chip and action disappear only from that row, and surrounding rows remain unchanged. Mark the same bookmark unread again and verify the chip returns.
8. Capture and attach **video evidence**—screenshots alone do not satisfy this criterion—to both OSFG-59 and the PR body. The recording must show in one continuous verification flow: an unread row with the `Unread` chip beside its title; a read row without the chip; the mark-as-read button and `Mark as read?` confirmation; the in-place update removing the chip; and the mark-unread flow restoring it. The recording must also demonstrate the long-title layout at desktop and <=600 px and the chip in both light and dark themes.
9. The repository validation gate passes from the repository root: `make lint && make test`.
