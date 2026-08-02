*Spec: Add a clear unread bookmark chip*

== PRODUCT ==

*Summary:* Bookmark rows currently communicate unread state only by italicizing the title, which is easy to miss while scanning. Add a compact, visible `Unread` text chip beside unread bookmark titles while preserving the existing unread data, actions, and partial-update behavior.

*Key design choices:* Render a real text `<span>` from the existing `bookmark_item.unread` value; keep italics as a secondary cue; use an unread-only flex layout in which the title can shrink and ellipsize while the chip cannot shrink; render the chip in every active, archived, shared/anonymous, and preview use of the common bookmark-list template.

*Behavior*:
1. Every rendered bookmark with `unread = true` shows exactly one text chip labelled `Unread` immediately beside its title.
2. A bookmark with `unread = false` shows no unread chip.
3. The chip is a stronger primary state cue than the existing italics: it has a solid theme-primary background, contrasting text, compact spacing, and the existing border radius, and remains legible in both light and dark themes.
4. Long titles remain on one line and ellipsize before the chip. The chip remains visible, does not shrink or wrap, and does not disturb favicon or bulk-edit-checkbox alignment.
5. The row layout remains intact with preview images enabled or disabled, inline or separate descriptions, favicons enabled or disabled, bulk-edit mode active, and viewport widths at or below 600 px.
6. The common title treatment applies to active, archived, shared/anonymous, and preview list variants whenever their `BookmarkItem.unread` value is true. Shared, anonymous, and preview variants show the state chip even when edit actions are unavailable.
7. Confirming the existing row action labelled `Unread` marks that bookmark read, updates the row in place without a full navigation, and removes both the chip and the mark-as-read action from that row only. Marking the bookmark unread again causes the chip to render again.
8. Existing confirmation text, action visibility rules, Turbo partial-update behavior, title links, favicons, descriptions, previews, and all other bookmark-row content remain unchanged.
9. `Unread` is rendered as visible DOM text, not generated content or a decorative pseudo-element, so assistive technologies can announce the state without a redundant ARIA label.
10. Product-code changes remain limited to the common bookmark-list template and its stylesheet. Tests may change only where needed to cover rendering and disambiguate existing E2E locators; there are no model, context, migration, serializer, API, JavaScript, or dependency changes.

== TECH ==

*Context:*
- `bookmarks/views/contexts.py:150 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` already assigns `BookmarkItem.unread`, and `bookmarks/views/contexts.py:156-164 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` derives the row's `unread` CSS class. No data, context, or API change is needed.
- `bookmarks/templates/bookmarks/bookmark_list.html:16-31 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` is the shared title block. It renders the optional bulk-edit checkbox, optional absolutely positioned favicon, and full-width title anchor, but no explicit unread-state element.
- `bookmarks/templates/bookmarks/bookmark_list.html:117-129 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` separately renders the existing editable-row action also labelled `Unread`. That button means “mark as read” and remains unchanged.
- `bookmarks/styles/bookmark-page.css:185-213 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` positions the favicon and gives the title anchor `display: block`, `width: 100%`, and nowrap/overflow/ellipsis behavior. `bookmarks/styles/bookmark-page.css:242-244 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` adds italics as the only current unread treatment.
- `bookmarks/styles/theme/variables.css:14-40,76-104 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` and `bookmarks/styles/theme-dark.css:16-53 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` define the existing primary, contrast-text, spacing, font-size, and radius tokens for both themes. `var(--primary-color)` with `var(--contrast-text-color)` is selected because the configured light and dark token pairs both provide readable contrast without introducing a new theme token.
- `bookmarks/tests/test_bookmarks_list_template.py:15-329,607-640,824-842,1018-1151 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` provides BeautifulSoup/`assertInHTML` helpers and existing coverage for unread row classes, mark-as-read action visibility, anonymous shared rendering, and preview rendering.
- `bookmarks/tests_e2e/e2e_test_bookmark_page_partial_updates.py:124-136 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` and `bookmarks/tests_e2e/e2e_test_bookmark_details_modal.py:61-78 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` currently locate `Unread` by text. Once both a chip and an action carry that text, those broad locators are ambiguous under Playwright strict mode.
- Triage reproduced the baseline in the running app: unread rows have italic titles but no chip; the mark-as-read confirmation updates only the selected row in place and removes its unread styling/action.

*Design alternatives:*
- **State markup:** A real `<span>` is selected over a CSS pseudo-element, icon, or dot. The selected markup satisfies the requested text label and accessibility requirement directly. Generated content is less reliable for assistive technology, while an icon or dot would be less explicit and would require an additional accessible name.
- **Title/chip layout:** An unread-only flex row is selected over dropping an inline sibling into the current block layout, making every title row flex, or absolutely positioning the chip. Flex allows the title anchor to shrink and ellipsize while the chip stays visible. Limiting flex to unread rows minimizes layout change for read rows. A plain inline sibling can wrap or be pushed away by the current full-width anchor; absolute positioning requires fragile reserved offsets; changing every row expands the regression surface unnecessarily.
- **Flex sizing:** The title anchor uses `flex: 0 1 auto`, `width: auto`, and `min-width: 0`, while the chip uses `flex: 0 0 auto`. Giving the anchor `flex-grow: 1` would pin the chip to the far edge instead of keeping it visually adjacent to the title; omitting `min-width: 0` can prevent ellipsis; allowing the chip to shrink can clip its label.
- **Favicon and checkbox positioning:** Keep the existing absolute-position rules and the `img + a` padding selector unchanged. The absolutely positioned favicon and bulk-edit control remain outside flex sizing, while the title anchor continues to reserve favicon space. Rebuilding them as flex children would be broader and risks alignment changes in read rows.
- **Existing italics:** Keep the italic rule as secondary reinforcement. Removing it would be an unrelated visual-language change; retaining it provides redundant state communication while the chip becomes the clear primary cue.
- **Variant coverage:** Render in all uses of `bookmark_list.html` rather than gating on `is_preview`, editability, archive state, sharing, or preview-image settings. Unread is bookmark state already present on the view model in every variant; the chip displays state, unlike the separately gated mark-as-read action.
- **Visual treatment:** Use `var(--primary-color)` with `var(--contrast-text-color)` rather than inventing chip-specific tokens, reusing the existing `.badge` rules, or using a faint shade. The existing `.badge` is generated dot/count content rather than a reusable text chip. A solid primary fill is more noticeable than the shade treatment and uses theme-aware tokens already configured for readable contrast in both themes.

*Proposed changes:*
1. In `bookmarks/templates/bookmarks/bookmark_list.html`, immediately after the title anchor and still inside `.title`, conditionally render `<span class="unread-chip">Unread</span>` when `bookmark_item.unread` is true. Do not gate it on `bookmark_list.is_preview`, ownership, sharing, archive state, action visibility, or preview-image settings.
2. In `bookmarks/styles/bookmark-page.css`, make `.title` a flex container only for unread rows, preserving `position: relative`, and add centered alignment plus `var(--unit-2)` gap. Override the unread title anchor with `flex: 0 1 auto`, `width: auto`, and `min-width: 0`, while retaining its existing nowrap/overflow/ellipsis behavior and italic rule. Leave favicon and bulk-edit positioning selectors unchanged.
3. Style `.unread-chip` with `flex: 0 0 auto`, `white-space: nowrap`, `padding: 0 var(--unit-1)`, `border-radius: var(--border-radius)`, `background: var(--primary-color)`, `color: var(--contrast-text-color)`, `font-size: var(--font-size-sm)`, `font-style: normal`, `font-weight: 500`, and `line-height: var(--line-height)`.
4. In `bookmarks/tests/test_bookmarks_list_template.py`, add an `assertUnreadChip` helper that selects `.title > .unread-chip`, checks its exact count, and checks visible text when present. Add focused tests named `test_should_render_unread_chip_for_unread_bookmarks` and `test_should_not_render_unread_chip_for_read_bookmarks`. Extend or add focused archived, shared/anonymous, and `is_preview=True` cases so they prove that an unread chip is present even when the mark-as-read action is unavailable.
5. In `bookmarks/tests_e2e/e2e_test_bookmark_page_partial_updates.py`, update the existing mark-as-read flow to locate the action as a button by role/name rather than by broad text. In `bookmarks/tests_e2e/e2e_test_bookmark_details_modal.py`, locate/assert the state chip by `.unread-chip` while leaving the details-modal toggle scoped to the modal. These test-only changes prevent the strict-mode collision already encountered by the similar closed PR #20; do not change product behavior or add unrelated E2E coverage.

*Affected files:*
- `bookmarks/templates/bookmarks/bookmark_list.html`
- `bookmarks/styles/bookmark-page.css`
- `bookmarks/tests/test_bookmarks_list_template.py`
- `bookmarks/tests_e2e/e2e_test_bookmark_page_partial_updates.py`
- `bookmarks/tests_e2e/e2e_test_bookmark_details_modal.py`
- `agents/specs/OSFG-59: add unread bookmark chip.md`

*Open questions resolved:*
- **How should flex/truncation work?** Use unread-only flex, a shrinkable title anchor with `min-width: 0`, and a non-shrinking chip; preserve the current absolute favicon and checkbox rules.
- **What visual treatment works in both themes?** Use the existing solid primary background and contrast-text tokens with compact existing spacing/radius tokens; do not add theme variables.
- **Keep or remove italics?** Keep them as a secondary cue; the chip is the new primary indicator.
- **Which variants receive the chip?** Every variant rendered through the common template, including active, archived, shared/anonymous, preview, with or without preview images, because the chip communicates state rather than editability.
- **Does the chip need extra ARIA?** No. Its visible DOM text is the accessible label; a pseudo-element is explicitly excluded.
- **Should the state transition animate?** No. Preserve the current immediate Turbo row replacement; animation would add behavior and scope.

*Risks / blast radius:*
- The flex override can break truncation if `min-width: 0`, `width: auto`, or the chip's non-shrinking behavior is omitted. Implementation and visual proof must exercise a deliberately long title at desktop and narrow widths.
- The absolute favicon and bulk-edit checkbox depend on existing positioning. The selected approach leaves those rules unchanged, but visual verification must cover favicons on/off and bulk-edit mode.
- The mark-as-read button and state chip share the word `Unread`. Closed PR #20 required Playwright locator fixes after this caused strict-mode collisions. All E2E and computer-use interactions must identify the chip by `.unread-chip` and the action by button role/name, never an unscoped text locator.
- Theme, responsive, and truncation regressions are visual and are not fully expressible in Django template tests. The required running-UI video is acceptance evidence, not optional supporting material.
- The common template has a broad surface. Focused variant tests and video must confirm that displaying state is independent of action availability and does not expose controls on shared/anonymous or preview rows.

*Validation & verification criteria* (must ALL pass before merge):
1. Re-run the confirmed baseline with at least one unread and one read bookmark. Before the product change, `BookmarkListTemplateTest.test_should_render_unread_chip_for_unread_bookmarks` fails because no `.unread-chip` exists; after the change, each unread row contains exactly one `.title > .unread-chip` whose visible text is exactly `Unread`, and `test_should_not_render_unread_chip_for_read_bookmarks` confirms read rows contain none. This verifies behavior #1, #2, and #9.
2. Focused template tests prove active, archived, shared/anonymous, and `is_preview=True` rendering includes the unread chip while existing ownership/preview rules still hide the mark-as-read action where appropriate. Run `uv run pytest bookmarks/tests/test_bookmarks_list_template.py -n auto`. This verifies behavior #6, #8, and #10.
3. The two existing unread E2E paths use unambiguous locators: `.unread-chip` for state and a role-scoped `Unread` button for the action. Run the affected E2E tests through `make e2e` or the repository's supported focused E2E invocation and confirm no Playwright strict-mode locator error. This verifies behavior #7 and mitigates the PR #20 regression.
4. Inspection of the final diff shows product-code changes only in `bookmarks/templates/bookmarks/bookmark_list.html` and `bookmarks/styles/bookmark-page.css`, plus the focused test files and this spec. There are no model, context, migration, serializer, API, JavaScript, dependency, or generated-media changes. This verifies behavior #10.
5. In the running app, unread and read rows are visibly distinguishable in both light and dark themes. The chip uses the selected existing CSS custom properties, remains readable, and its text is present in the rendered DOM/accessibility tree. This verifies behavior #1-#3 and #9.
6. In the running app, a deliberately long unread title ellipsizes on one line while its chip remains visible and unwrapped. Exercise desktop and a viewport at or below 600 px, favicons on and off, bulk-edit mode, preview images on and off, and inline and separate description modes; no title, chip, favicon, checkbox, description, or preview image overlaps, clips, or shifts out of its row. This verifies behavior #4 and #5.
7. Active, archived, shared/anonymous, and preview list rendering shows the chip when the rendered bookmark is unread and omits it when read. Action availability remains determined only by the existing ownership/preview rules. Confirm deterministically with the focused template tests and exercise representative rendered variants in the running UI. This verifies behavior #1, #2, #6, and #8.
8. The existing mark-as-read flow remains unchanged in the running UI: select the row's `Unread` button by role/name, observe the `Mark as read?` confirmation, confirm, and verify the row updates without full navigation, the chip and action disappear only from that row, and surrounding rows remain unchanged. Use the existing details flow to mark the same bookmark unread again and verify the chip returns without a full reload. This verifies behavior #7 and #8.
9. Capture and attach **computer-use video evidence** to both OSFG-59 and the final PR body. Screenshots alone do not satisfy this criterion. The recording or set of recordings must visibly demonstrate: an unread row with the chip beside its title; a read row without a chip; both light and dark themes; the long-title layout at desktop and at or below 600 px; the representative layout combinations from criterion #6; the mark-as-read button and `Mark as read?` confirmation; the in-place update removing the chip; and the mark-unread flow restoring it. The video must be checked against criteria #5-#8 before attachment.
10. The repository validation gate passes from the repository root: `make lint && make test`.
