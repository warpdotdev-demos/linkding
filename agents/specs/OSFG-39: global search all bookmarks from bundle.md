*Spec: Global search across all bookmarks when a bundle is selected (OSFG-39)*

---

## PRODUCT

*Summary:* When a bundle is active, users have no way to search across all bookmarks — every search is scoped to the bundle. This spec adds a "Search all bookmarks" link near the search bar that, when clicked, bypasses the bundle's filter criteria so the user's text query (`q`) runs against all bookmarks. The bundle context stays visible in the URL and sidebar at all times, and a "Back to «bundle name»" link lets the user return to bundle-scoped search. This is a purely user-facing feature that touches the query layer, the search model, the form, a template tag, and one template.

*Key design choices:*
1. **Affordance is a link, not a toggle or checkbox.** A plain `<a>` requires no JS, keeps the DOM minimal, and is consistent with linkding's link-first UI conventions (bundle links in the sidebar, tag links in the tag cloud).
2. **`global_search=1` is a URL param.** The state is reflected in the URL so result pages can be bookmarked and shared, and so the param carries naturally through form submissions as a hidden field — no cookie, no session, no extra round-trip.
3. **The `bundle` param is kept in the URL when global search is active.** This allows "Back to bundle" to be a simple URL manipulation (drop `global_search`), preserves the visual context in the sidebar selection highlight, and avoids requiring the user to re-select the bundle.

*Behavior* (numbered, testable invariants from the user's view):
1. When a bundle is selected (`bundle=<id>` in URL) and `global_search` is absent or falsy, a search returns only bookmarks matching the bundle's filter criteria (tags, search terms, unread/shared filters). This is unchanged behavior.
2. When a bundle is selected **and** `global_search=1` is in the URL, a search returns all bookmarks matching the user's text query (`q`) regardless of the bundle's filter criteria.
3. When a bundle is selected and global search is **not** active, a "Search all bookmarks" link appears near the search bar.
4. When a bundle is selected and global search **is** active, a "Back to «bundle name»" link appears near the search bar (the bundle name makes the current context visible — behavior invariant #5).
5. The current bundle's name/entry remains highlighted in the sidebar when global search is active (`bundle=<id>` is still in the URL).
6. Typing a new query and submitting the search form while global search is active keeps global search active (`global_search=1` is a hidden field in the search form).
7. When no bundle is selected, the "Search all bookmarks" link is absent.
8. Clicking a bundle link in the sidebar (of the form `?bundle=<id>`) drops `global_search` and returns to bundle-scoped search, because sidebar links are plain `?bundle=<id>` URLs.

---

## TECH

*Context:* How the area works today (commit `30510d3463237f0653ea8c1cdbd889c070062566`):

- **`BookmarkSearch`** (`bookmarks/models.py:224` @ `30510d3`): a plain Python dataclass (not a Django model) holding all search parameters. `params = ["q", "user", "bundle", "sort", "shared", "unread", "modified_since", "added_since"]`. The `bundle` field holds a `BookmarkBundle` ORM instance or `None`. `from_request()` parses every param from the request's `QueryDict`; `bundle` gets a special lookup (`BookmarkBundle.objects.filter(owner=..., pk=value).first()`); all other params are stored as raw strings.
- **`_base_bookmarks_query()`** (`bookmarks/queries.py:227` @ `30510d3`): the single function that assembles the filtered queryset. At line 268–270 it calls `_filter_bundle(query_set, search.bundle)` when `search.bundle` is set. There is no bypass.
- **`BookmarkSearchForm`** (`bookmarks/forms.py:248` @ `30510d3`): a Django `Form` (not `ModelForm`) whose `__init__` iterates `search.params` to set `initial` values and — when a param is modified and not in `editable_fields` — switches its widget to `HiddenInput`. The hidden fields are then emitted in templates via `{% for hidden_field in search_form.hidden_fields %}`.
- **`bookmark_search` template tag** (`bookmarks/templatetags/bookmarks.py:9` @ `30510d3`): an `@inclusion_tag` that renders `bookmarks/search.html`, returning a context dict that includes the `search` object and two `BookmarkSearchForm` instances.
- **`search.html`** (`bookmarks/templates/bookmarks/search.html` @ `30510d3`): renders the `<form id="search">` with the autocomplete input and hidden fields. All hidden-field values live in `{% for hidden_field in search_form.hidden_fields %}`.
- **`bundle_section.html`** (`bookmarks/templates/bookmarks/bundle_section.html` @ `30510d3`): bundle links are `<a href="?bundle={{ bundle.id }}">` — a single-param URL that drops every other query param including `global_search` on click. This naturally satisfies behavior invariant #8 with no code change.

*Design alternatives:*
- **Toggle (checkbox/switch) vs. plain link** — A toggle requires maintaining checked state, either via JS or by re-rendering the form on change (a full round-trip). A link is zero-JS, zero-form-state, and consistent with the rest of linkding's link-driven navigation. *Selected: plain link.*
- **Keep `bundle` param in global-search URL vs. drop it** — Keeping it: "Back to bundle" is a one-param-drop URL change; the sidebar selection highlight works automatically; the bundle name is available for display. Dropping it: simpler URL, but requires a re-selection step. *Selected: keep `bundle=<id>` in URL.*
- **Render link in `search.html` vs. in a new partial template** — `search.html` already receives the `search` object and will receive the two new URL context vars. A new partial would add a file for minimal gain. *Selected: extend `search.html`.*
- **Compute global-search and bundle-search URLs in the template tag vs. inline template arithmetic** — Django templates cannot easily mutate query-string dicts; the template tag already has `context["request"]` and is the right place to build these URLs. *Selected: compute in template tag.*

*Proposed changes:*

**1. `bookmarks/models.py` — `BookmarkSearch`**
- Append `"global_search"` to `params` (after `"bundle"`).
- Add `"global_search": None` to `defaults`.
- Add `global_search=None` to `__init__()` signature; assign `self.global_search = global_search or self.defaults["global_search"]`.
- `from_request()` requires no change: the existing loop already handles the new param — when `global_search=1` is in the `QueryDict`, `value = "1"` (truthy), so `initial_values["global_search"] = "1"`. No special-case branch is needed.

**2. `bookmarks/queries.py` — `_base_bookmarks_query()`**
- Change the filter-bundle conditional at line 268 from:
  ```python
  if search.bundle:
      query_set = _filter_bundle(query_set, search.bundle)
  ```
  to:
  ```python
  if search.bundle and not search.global_search:
      query_set = _filter_bundle(query_set, search.bundle)
  ```
  One line changed. No other query logic touched.

**3. `bookmarks/forms.py` — `BookmarkSearchForm`**
- Add `global_search = forms.CharField(required=False)` as a class-level form field. The existing `__init__` loop sets its `initial` from `search.global_search` and switches it to `HiddenInput` when modified, so it propagates through form submissions automatically.

**4. `bookmarks/templatetags/bookmarks.py` — `bookmark_search` tag**
- In the `bookmark_search` function, compute two URLs from `context["request"].GET`:
  - `global_search_url`: copy of current GET params with `global_search` set to `"1"` and `page` removed.
  - `bundle_search_url`: copy of current GET params with `global_search` removed and `page` removed.
- Add both to the returned context dict.

**5. `bookmarks/templates/bookmarks/search.html`**
- After the `</form>` tag (inside the `<div class="search-container">`), add a conditional block using the new context vars:
  ```html
  {% if search.bundle and not search.global_search %}
    <a href="{{ global_search_url }}" class="search-global-toggle">Search all bookmarks</a>
  {% elif search.bundle and search.global_search %}
    <a href="{{ bundle_search_url }}" class="search-global-toggle">Back to "{{ search.bundle.name }}"</a>
  {% endif %}
  ```
  The class `search-global-toggle` uses existing link styling (no new CSS required for functionality; further polish is left to the implementor's discretion).

*Open questions resolved:*
- "Exact affordance (toggle vs. link)" → **Link.** No JS overhead; consistent with linkding's link-first navigation.
- "Label text" → **"Search all bookmarks"** forward; **"Back to «bundle name»"** reverse. The bundle name doubles as the context indicator (behavior invariant #5).
- "Whether bundle breadcrumb context persists" → **Yes.** `bundle=<id>` stays in the URL; the sidebar highlights the selected bundle; the bundle name appears in the "Back to" link.
- "Whether pressing Enter while in global-search mode stays global" → **Yes.** `global_search` is carried as a hidden field in the search form (behavior invariant #6).
- "Switching to a different bundle resets global search" → **Yes, automatically.** Bundle sidebar links are `?bundle=<id>` only; clicking one drops `global_search` (behavior invariant #8, no code change required).

---

*Validation & verification criteria* (must ALL pass before merge):

1. **Bundle-scoped search unchanged (no regression)** — With a bundle selected and no `global_search`, results are limited to bookmarks matching the bundle's filter. Verified by: existing tests `test_query_bookmarks_with_bundle_search_terms`, `test_query_bookmarks_with_bundle_any_tags`, etc. still pass. Run: `uv run pytest bookmarks/tests/test_queries.py -n auto`

2. **Global search bypasses bundle filter** — New test `test_query_bookmarks_global_search_bypasses_bundle` in `bookmarks/tests/test_queries.py`:
   - Create a bundle filtering for search term `"bundle_only_term"`.
   - Create bookmark A matching the bundle filter; create bookmark B not matching it.
   - `BookmarkSearch(bundle=bundle, global_search="1")` → query returns both A and B.
   - `BookmarkSearch(bundle=bundle)` (no `global_search`) → query returns only A.
   - Run: `uv run pytest bookmarks/tests/test_queries.py::QueriesBasicTestCase::test_query_bookmarks_global_search_bypasses_bundle -n auto`

3. **`global_search` param is parsed from request** — New tests in `bookmarks/tests/test_bookmark_search_model.py`:
   - `BookmarkSearch.from_request()` with `global_search=1` in the `QueryDict` → `search.global_search == "1"`.
   - `BookmarkSearch.from_request()` without `global_search` → `search.global_search` is the default (None or "").
   - Run: `uv run pytest bookmarks/tests/test_bookmark_search_model.py -n auto`

4. **"Search all bookmarks" link rendered when bundle active, absent otherwise** — New tests in `bookmarks/tests/test_bookmark_index_view.py`:
   - `GET /?bundle=<id>` → response contains `"Search all bookmarks"`.
   - `GET /` (no bundle) → response does NOT contain `"Search all bookmarks"`.
   - Run: `uv run pytest bookmarks/tests/test_bookmark_index_view.py -k "global_search" -n auto`

5. **"Back to «bundle name»" link rendered when global search active** — New test in `bookmarks/tests/test_bookmark_index_view.py`:
   - `GET /?bundle=<id>&global_search=1` → response contains the bundle name (in the "Back to" link).
   - Run: `uv run pytest bookmarks/tests/test_bookmark_index_view.py -k "global_search" -n auto`

6. **Hidden field carries `global_search` through form submission** — New test in `bookmarks/tests/test_bookmark_index_view.py` (or `test_bookmark_search_model.py`):
   - `GET /?bundle=<id>&global_search=1` → rendered HTML contains `<input type="hidden" name="global_search" value="1">` inside the search form.
   - Run: `uv run pytest bookmarks/tests/test_bookmark_index_view.py -k "global_search" -n auto`

7. **Validation gate passes** — `make lint && make test` exits 0. Run: `make lint && make test`.

8. **Visual proof (user-facing change)** — Exercise the running UI with the computer-use tool:
   - Navigate to the bookmarks index with a bundle selected; confirm "Search all bookmarks" appears near the search bar.
   - Click "Search all bookmarks"; confirm results include bookmarks outside the bundle; confirm "Back to «bundle name»" appears.
   - Type a new query and submit; confirm global search remains active (link still shows "Back to").
   - Click the "Back to" link; confirm global search is deactivated and the bundle filter is reapplied.
   - Screenshot attached to PR and Jira ticket.

---

*Co-Authored-By: Oz <oz-agent@warp.dev>*
