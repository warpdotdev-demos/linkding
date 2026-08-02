*Spec: Fix parenthesized tag search*

Ticket: [OSFG-60](https://warp-se-demo.atlassian.net/browse/OSFG-60)

== PRODUCT ==

*Summary:* In the boolean-search mode, a tag query such as `#hello(world)` is split into the tag `hello` and a grouped term `world`, so a bookmark tagged `hello(world)` is not returned. Tag tokens must support balanced parentheses without weakening parentheses as boolean grouping delimiters, and quoted tag literals must provide an unambiguous escape hatch for delimiter-bearing tag names.

*Key design choices:*
- Accept balanced parenthesized segments inside an unquoted tag after the tag token has begun, so the exact reported query `#hello(world)` works without changing existing tag links, autocomplete insertion, REST clients, or legacy-search behavior.
- Add quoted tag literals (`#"..."` and `#'...'`) as the unambiguous form for tag names that cannot be represented safely by the unquoted rule; use the same escaping rules already used for quoted search terms.
- Preserve parentheses at tag-token depth zero as boolean grouping delimiters, so queries such as `(#python OR #js) AND #tag` keep their existing AST, precedence, and results.

*Behavior*:
1. A bookmark tagged `hello(world)` is returned when a non-legacy user searches for `#hello(world)`, clicks that tag, or selects that tag from search autocomplete.
2. An unquoted tag may contain one or more balanced parenthesized segments after at least one ordinary tag character: `#hello(world)`, `#a(b)(c)`, and `#a(b(c))` each produce one `TagExpression` containing the full tag name.
3. Parentheses outside a tag or encountered at tag-token depth zero remain boolean grouping tokens. `(#python OR #js) AND #tag`, `(#hello(world) OR #other)`, and nested boolean groups retain the current precedence and result semantics.
4. An unquoted opening parenthesis is absorbed into a tag only when it occurs after at least one tag character and has a matching close before the next whitespace or quote boundary. An unmatched opening parenthesis keeps the current malformed-query behavior rather than silently becoming part of a tag. A closing parenthesis with no tag-local opening parenthesis ends the tag and remains available to close a boolean group.
5. A quoted tag literal starts when `#` is immediately followed by either quote character. `#"hello(world)"` and `#'hello(world)'` both produce `TagExpression("hello(world)")`; parentheses, whitespace, boolean words, and the other quote character inside the literal are tag data. Backslash escaping follows `read_quoted_string`: escaped matching quotes and backslashes round-trip, and an unclosed quote is handled with the parser's existing lenient end-of-input behavior.
6. `expression_to_string` emits simple tags in the existing `#name` form and emits a double-quoted tag literal when the tag contains whitespace, parentheses, a quote, or a backslash. The serializer escapes backslashes and double quotes so parse → serialize → parse preserves the same AST.
7. `strip_tag_from_query` removes a matching parenthesized or quoted tag without damaging adjacent boolean expressions, and `extract_tag_names_from_query` returns the complete normalized tag name (for example, `hello(world)`, not `hello`).
8. Normal tag searches, implicit and explicit `AND`, `OR`, `NOT`, special keywords, ordinary quoted terms, legacy search, archived/shared bookmark searches, and the REST API `q` parameter retain their existing behavior.
9. Invalid/ambiguous boundary forms remain deterministic: `#(name)` keeps the existing empty-tag-plus-group interpretation, and `#name)` treats the depth-zero `)` as a grouping delimiter. A caller that needs either parenthesis as literal boundary data uses the quoted form (`#"(name)"` or `#"name)"`).

== TECH ==

*Context:* The defect was reproduced before this spec: on current boolean search, `#hello(world)` tokenizes to `TAG(hello) LPAREN TERM(world) RPAREN`, parses as `TagExpression("hello") AND TermExpression("world")`, and returns no bookmark; the same bookmark is returned in legacy mode. The spec is grounded at `fdd4234bb40108b6c87f9ed8fecb332c3f754a2a`:
- `bookmarks/services/search_query_parser.py:26-145 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` owns tokenization; `read_tag` currently stops at every `(`, `)`, or quote.
- `bookmarks/services/search_query_parser.py:353-419 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` serializes AST nodes; tags are currently always emitted as raw `#<name>`.
- `bookmarks/services/search_query_parser.py:488-573 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` implements tag stripping and extraction on the parser AST.
- `bookmarks/queries.py:33-138 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` converts `TagExpression` values to Django filters and is shared by active, archived, shared, and REST API list paths.
- `bookmarks/views/contexts.py:291-370 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` appends raw tag names to tag-chip links and removes selected tags through `strip_tag_from_query`.
- `bookmarks/frontend/components/search-autocomplete.js:134-163,220-239 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` suggests tags and inserts raw `#<tag>` text.
- `bookmarks/api/routes.py:58-72 @ fdd4234bb40108b6c87f9ed8fecb332c3f754a2a` builds `BookmarkSearch` from the REST request, so API `q` values use the same parser and query path.

*Design alternatives*:
- **Treat all parentheses as ordinary unquoted tag characters:** smallest tokenizer change, but it consumes the `)` that closes `(#python OR #js)` and breaks the established boolean grammar. Rejected because boolean grouping is a hard compatibility requirement.
- **Quoted tag literals only:** gives a simple, unambiguous grammar and supports all tag names, but leaves the exact reported `#hello(world)` query broken and requires every producer/client to adopt quoting before the customer-visible flow works. Rejected as the sole fix; retained as the explicit escape hatch.
- **Balanced unquoted parenthesized segments only:** fixes the exact report and requires no producer changes, but tag names with a leading, trailing, unbalanced, quoted, or whitespace delimiter still have no representation in boolean search. Rejected as incomplete on its own.
- **Selected — balanced unquoted segments plus quoted tag literals:** preserves the exact existing UI/API spelling, keeps depth-zero parentheses for grouping, and adds a total, unambiguous representation for boundary cases. The cost is a modest increase in tokenizer/serializer tests and two accepted spellings for balanced names; the serializer provides one canonical quoted spelling when it rebuilds an unsafe tag.

*Proposed changes:*
1. In `SearchQueryTokenizer`, extend `read_tag` with bounded balanced-parenthesis scanning. Consume a `(` into the tag only after ordinary tag content exists and only when a matching `)` occurs before whitespace, a quote, or end-of-input; include nested and consecutive balanced segments. While consuming such a segment, include every nested parenthesis in the tag value. Leave a depth-zero `)` unconsumed for the main tokenizer to emit as `RPAREN`.
2. When `#` is followed immediately by `'` or `"`, have `read_tag` call the existing quoted-string reader and emit the result as one `TAG` token instead of dropping the empty tag and emitting a `TERM`.
3. Add one parser-owned tag formatting helper and use it from `_expression_to_string(TagExpression)`. Return raw `#name` only when round-tripping is unambiguous; otherwise return a double-quoted tag literal with backslash and double-quote escaping.
4. Keep `bookmarks/queries.py`, `AddTagItem`, search autocomplete, and API route behavior structurally unchanged: their existing raw `#hello(world)` output/input becomes valid through the shared tokenizer. Exercise each call site in tests or required UI/API verification to guard the blast radius.
5. Add focused parser/helper coverage in `bookmarks/tests/test_search_query_parser.py`, query integration coverage in `bookmarks/tests/test_queries.py`, tag-link/removal coverage beside the existing context/template tests, and REST `q` coverage in `bookmarks/tests/test_bookmarks_api.py`.
6. Do not change the database schema, stored tag names, legacy parser, search precedence, or public API shape.

*Open questions resolved:*
- **Should parentheses be tag data or grouping syntax?** They are tag data only inside a provably balanced segment of an already-started tag; at tag depth zero they remain grouping syntax.
- **How are otherwise ambiguous tag names represented?** With `#"<tag name>"` or `#'<tag name>'`; the AST serializer uses the double-quoted form canonically for unsafe names.
- **Must every tag-producing call site start quoting?** No. Existing raw producers remain compatible for balanced internal parentheses, which also avoids changing legacy-search autocomplete behavior. Parser/serializer tests and end-to-end evidence still cover those call sites.
- **Does this change legacy search?** No. Legacy search already treats `#hello(world)` as one whitespace-delimited tag, and its parsing/URLs remain unchanged.
- **Are migrations or documentation required?** No schema or configuration changes are introduced. The query syntax is established by tests; user-facing documentation is optional unless the implementation exposes quoted tag syntax in help text.

*Risks / blast radius:*
- Token-boundary changes are on the central search hot path. A swallowed depth-zero `)` would alter boolean precedence; explicit AST and result-set regressions mitigate this.
- Parser-generated strings feed selected-tag highlighting/removal. Round-trip, extraction, and removal tests must cover both raw balanced and quoted forms.
- Active, archived, shared, autocomplete, tag-chip, and REST searches share the same parser indirectly. Integration/API tests plus one continuous UI video must prove these surfaces agree.
- Lenient quoted-string behavior already exists. Reusing it avoids a second escape grammar, but tests must pin escaped quotes/backslashes and unclosed quoted tags.
- The balanced lookahead must be linear and bounded to the current token; avoid repeated suffix scans that make tokenization quadratic for long queries.

*Validation & verification criteria* (must ALL pass before merge):
1. Re-run the confirmed reproduction before and after the implementation with a bookmark tagged `hello(world)`: `query_bookmarks(..., BookmarkSearch(q="#hello(world)"))` returns no bookmark before the change and exactly the tagged bookmark after it. Add a failing-then-passing regression named for parenthesized tag search in `bookmarks/tests/test_queries.py`, and run `uv run pytest bookmarks/tests/test_queries.py -n auto`.
2. Add tokenizer/parser table tests in `bookmarks/tests/test_search_query_parser.py` proving that `#hello(world)`, `#a(b)(c)`, and `#a(b(c))` each produce one full `TagExpression`; `#"hello(world)"`, `#'hello(world)'`, quoted boundary parentheses, spaces, escaped quotes, and escaped backslashes also produce the exact tag value. Run `uv run pytest bookmarks/tests/test_search_query_parser.py -n auto`.
3. In the same parser suite, prove boolean grouping is unchanged by asserting the exact ASTs for `(#python OR #js) AND #tag`, `(#hello(world) OR #other) AND NOT #excluded`, and nested boolean groups. Also pin unmatched/ambiguous cases from Behavior #4 and #9 to their specified parse result or `SearchQueryParseError`.
4. Add serializer round-trip tests proving `parse_search_query(expression_to_string(ast)) == ast` for simple, balanced-parenthesis, leading/trailing-parenthesis, whitespace, quote, and backslash tag values. Prove simple tags still serialize as `#python` and unsafe tags serialize as escaped double-quoted tag literals.
5. Add `strip_tag_from_query` and `extract_tag_names_from_query` tests for raw and quoted `hello(world)`: extraction returns `["hello(world)"]`; removing it from standalone, `AND`, `OR`, and `NOT` expressions removes only that tag and preserves a parseable, equivalent remainder.
6. Add tag-link/context coverage proving clicking the `hello(world)` chip produces a `q` value that the boolean parser reads as the complete tag, and removing the selected chip removes the complete tag without leaving `world` or unmatched grouping tokens.
7. Add REST integration coverage in `bookmarks/tests/test_bookmarks_api.py`: authenticated `GET /api/bookmarks/?q=%23hello%28world%29` returns the tagged bookmark, while a normal tag query and a grouped boolean tag query return their expected result sets.
8. Prove no collateral damage in query integration tests: ordinary `#python`, implicit/explicit `AND`, `OR`, `NOT`, `!unread`/`!untagged`, quoted terms, strict/lax tag modes, legacy search, and active/archived/shared query paths retain their expected results.
9. Run the repository validation gate from the repo root with `make lint && make test`; both commands must pass.
10. Produce one continuous computer-use video after building static assets (`npm run build` or `make frontend-bg` before `make serve-bg`, otherwise `/static/bundle.js` is missing). The video must visibly show: creating or opening a bookmark tagged `hello(world)`; finding it by typing `#hello(world)`; finding it by clicking the tag and by selecting its autocomplete suggestion; a normal tag search still returning the correct bookmark(s); and `(#python OR #js) AND #tag` returning the correct boolean subset. Attach the video evidence to OSFG-60 and the implementation PR; screenshots alone do not satisfy the request.
