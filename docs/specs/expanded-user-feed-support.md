# Expanded user feed support

## Status and references

- Status: Proposed. Implementation requires requester approval.
- Tracker: [LIN-2](https://warp-se-demo.atlassian.net/browse/LIN-2).
- Request: [Slack thread](https://warpsedemos.slack.com/archives/C0BQM3U96R5/p1787251249907169).
- Adjacent work: [warpdotdev-demos/linkding#44](https://github.com/warpdotdev-demos/linkding/pull/44).
- Upstream context:
  - [sissbruecker/linkding#1305](https://github.com/sissbruecker/linkding/issues/1305)
  - [sissbruecker/linkding#1442](https://github.com/sissbruecker/linkding/issues/1442)
  - [sissbruecker/linkding#1349](https://github.com/sissbruecker/linkding/pull/1349)
  - [sissbruecker/linkding#1449](https://github.com/sissbruecker/linkding/pull/1449)

## Summary

Linkding already provides RSS feeds for a user's own bookmarks and for shared
bookmarks. This specification compares ways to add Atom, multiple feed tokens,
cross-user feeds, and better feed filters. It recommends a phased design that
preserves all existing URLs. It does not recommend exposing an owner's complete
private bookmark library to another user.

The recommended sequence is:

1. Merge PR #44 as the public per-user feed baseline.
2. Fix token-only bundle authorization as a separate small change.
3. Add Atom on distinct routes.
4. Add named, independently revocable feed tokens.
5. Add user filtering to the authenticated shared feed.
6. Add owner-created, bundle-scoped private feed grants only if the requester
   confirms that private cross-user access is required.

This sequence delivers low-risk improvements before it adds a new privacy
surface.

## Size scale

The estimates are relative engineering sizes. They include code, migrations
when applicable, automated tests, user documentation, and review fixes.

- **Small (S):** one to two engineering days.
- **Medium (M):** three to five engineering days.
- **Large (L):** one to two engineering weeks.
- **Extra large (XL):** more than two engineering weeks or a separate product
  project.

The estimates assume that PR #44 merges before implementation starts.

## Current behavior

### Feed credentials and routes

- `FeedToken` stores a 160-bit random hexadecimal key as its primary key.
  `FeedToken.user` is a `OneToOneField`, so each user can have at most one feed
  token (`bookmarks/models.py:490-513`).
- The original migration created the same one-to-one relationship
  (`bookmarks/migrations/0015_feedtoken.py:14-30`).
- Linkding creates the token lazily when the user opens Settings >
  Integrations (`bookmarks/views/settings.py:178-187`).
- The private routes are:
  - `/feeds/<feed_key>/all`
  - `/feeds/<feed_key>/unread`
  - `/feeds/<feed_key>/shared`
- The tokenless route is `/feeds/shared`
  (`bookmarks/urls.py:101-109`).
- The Integrations page displays all four URLs. It tells users to revoke the
  single token in Django admin (`bookmarks/templates/settings/integrations.html:186-231`).
- Django's `Feed` class produces RSS 2.0 by default. Linkding does not override
  `feed_type` in `BaseBookmarksFeed` (`bookmarks/feeds.py:4,31-121`).
- The project uses Django 6.0.5 or later, which includes Django's
  `Atom1Feed` generator (`pyproject.toml:8-20`).

### Feed contents and filters

- A feed item contains the bookmark title, description, URL, added date, and
  tag names (`bookmarks/feeds.py:52-73`).
- A feed item does not render bookmark notes. However, the search engine tests
  `q` against title, description, notes, and URL
  (`bookmarks/queries.py:67-80`).
- Feed requests currently parse `q`, `unread`, `shared`, and `bundle`.
  `limit` is applied when the items are rendered
  (`bookmarks/feeds.py:32-50`).
- `q` already supports tag expressions such as `#python`. The query tests cover
  single tags, multiple tags, and mixed term and tag searches
  (`bookmarks/tests/test_queries.py:187-253`).
- A bundle can already store search text, any tags, all tags, excluded tags,
  unread state, and shared state (`bookmarks/models.py:167-211`). Bundle
  predicates are combined with the request predicates
  (`bookmarks/queries.py:168-291`).
- `BookmarkSearch` also supports `user`, sorting, and date filters, but the
  current feed parser does not pass those values
  (`bookmarks/models.py:238-330`, `bookmarks/feeds.py:39-44`).
- Feed tests cover RSS metadata, ownership, shared visibility, `q`, unread,
  shared, tags, limit, bundles, and control-character removal
  (`bookmarks/tests/test_feeds.py:20-355`).

### Sharing boundaries

- A bookmark has one `shared` flag (`bookmarks/models.py:44-61`).
- `enable_sharing` allows shared bookmarks to appear to authenticated users.
  `enable_public_sharing` allows them to appear without login
  (`bookmarks/models.py:438-439`,
  `bookmarks/templates/settings/general.html:192-207`).
- Shared bookmark queries require both `Bookmark.shared=True` and the owner's
  `enable_sharing=True`. Public queries also require
  `enable_public_sharing=True` (`bookmarks/queries.py:47-60`).
- The authenticated shared page resolves `?user=<username>` and filters by that
  owner (`bookmarks/views/contexts.py:112-128`).
- The existing token-authenticated `/feeds/<feed_key>/shared` route returns
  shared bookmarks from all sharing-enabled users. It does not filter to the
  feed token owner (`bookmarks/feeds.py:88-106`).
- The tokenless `/feeds/shared` route returns only publicly shared bookmarks
  (`bookmarks/feeds.py:109-121`).
- `bookmark_read` returns 404 when the caller is outside the owner, shared, and
  public-shared rules. The feed code does not use this object-level helper
  (`bookmarks/views/access.py:7-26`, `bookmarks/feeds.py:33-50`).

### Verified bundle authorization defect

The code recognizes `?bundle=<id>`, but it does not work for a normal external
feed reader:

1. `BaseBookmarksFeed.get_object` resolves the feed token.
2. It then calls `access.bundle_read(request, bundle_id)`
   (`bookmarks/feeds.py:33-39`).
3. `bundle_read` requires the bundle owner to equal `request.user`
   (`bookmarks/views/access.py:36-43`).
4. A feed reader presents the key in the URL. It does not have a Linkding login
   session.
5. The bundle tests force-login the feed owner before every request. They do not
   cover a token-only request (`bookmarks/tests/test_feeds.py:20-26,330-355`).

This defect must be fixed as its own **Small (S)** work item. The feed token
owner, not the session user, must authorize a bundle on a private feed.
Tokenless public feeds must reject `bundle`. Existing bundle URLs must keep
their shape.

## Assumptions

These assumptions did not receive requester confirmation before this draft:

1. **Syndication scope:** This work targets external feed readers. It does not
   add an in-Linkding following timeline.
2. **Adjacent PR:** PR #44 is the prerequisite baseline. This specification
   does not repeat its implementation.
3. **Compatibility:** Existing feed URLs must continue to return RSS and must
   not require a forced token rotation.
4. **Private access default:** An owner must explicitly create each private
   grant. No profile setting enables private access by itself.
5. **Safe source scope:** A private grant can expose one owner-controlled
   bundle. It cannot expose the owner's complete private library.

If the requester rejects assumption 1 or 2, revise this specification before
implementation. Assumptions 3 through 5 are proposed defaults in the option
comparisons below.

## Product behavior

The numbered behaviors describe the recommended design.

1. Existing RSS URLs continue to work without redirects or changed contents.
2. Every existing RSS feed has an Atom equivalent on a distinct `.atom` route.
3. Settings > Integrations lets a user create multiple feed tokens.
4. Each feed token has a required user-visible name.
5. Deleting one feed token invalidates only URLs that contain that token.
6. An upgraded user keeps the current token and URL. Linkding names that row
   `Default feed token`.
7. A user's own feeds continue to support `q`, `unread`, `shared`, `limit`, and
   an authorized `bundle`.
8. `q` remains the tag-filter interface. Linkding does not add a duplicate
   `tag` query parameter.
9. The public shared feed supports `?user=<username>` after PR #44.
10. The authenticated shared feed can also support `?user=<username>`. It still
    returns only bookmarks that the owner marked shared.
11. Linkding does not expose another user's unshared bookmarks through an
    ordinary feed token or through `?user=`.
12. If private cross-user feeds are approved, an owner creates a named grant
    for one of the owner's bundles.
13. A private grant has its own random bearer key. It does not reuse either
    user's ordinary feed token.
14. A grant URL returns only the intersection of the grant's fixed source
    bundle and mandatory privacy predicates.
15. Request query parameters cannot broaden a private grant.
16. Deleting a grant invalidates its URL immediately.
17. Deleting the source bundle invalidates its grants.
18. Unknown, revoked, and unauthorized scoped feed URLs return the same 404
    response.
19. Private grant creation warns that feed items expose URLs, titles,
    descriptions, dates, and tags to every holder of the URL.
20. Linkding does not add JSON Feed or an in-app social timeline in the first
    implementation.

## Option 1: Syndication formats

### 1A. Distinct Atom routes — recommended

Add a parallel Atom route for each RSS route:

- `/feeds/<feed_key>/all.atom`
- `/feeds/<feed_key>/unread.atom`
- `/feeds/<feed_key>/shared.atom`
- `/feeds/shared.atom`

PR #44's public user filter composes with the Atom public route:

`/feeds/shared.atom?user=<username>`

Use Django's built-in `Atom1Feed`. Share object lookup, query construction, item
fields, and privacy rules with the RSS classes. The format class is the only
intentional output difference.

An illustrative interface is:

```python
from django.utils.feedgenerator import Atom1Feed


class AtomFeedMixin:
    feed_type = Atom1Feed
```

**Changes**

- Models and migrations: none.
- Routes: add four named Atom routes in `bookmarks/urls.py`.
- Feed classes: add a small Atom mixin or format-specific subclasses in
  `bookmarks/feeds.py`. Do not duplicate query methods.
- Templates: list RSS and Atom links in
  `bookmarks/templates/settings/integrations.html`.
- Public feed discovery: add an Atom `<link>` beside the RSS discovery link.
  Preserve PR #44's `user` query string in both links. The current discovery
  link is tested in `bookmarks/tests/test_bookmark_shared_view.py:661-668`.
- Docs: add a feed guide at `docs/src/content/docs/feeds.md` and add it to the
  Guides sidebar in `docs/astro.config.mjs:18-44`.
- Tests: parameterize feed behavior across RSS and Atom. Assert
  `application/atom+xml`, Atom entry structure, metadata, item parity, escaping,
  token failures, and the PR #44 public user filter.

**Migration and compatibility**

- No data migration is required.
- Existing URLs remain RSS.
- Existing token keys work on both formats.
- No client must send a new header or query parameter.

**Security and privacy**

- Atom must call the same authorization and query code as RSS.
- Atom must not add fields that RSS omits.
- Format selection must happen before rendering, not before authorization.

**Settings surface**

- Rename the section from `RSS Feeds` to `Feeds`.
- Group links by feed scope.
- Give each row `RSS` and `Atom` links.
- Keep the credential warning visible for both formats.

**Trade-offs**

- Advantages: explicit URLs, simple caching, easy feed-reader setup, built-in
  Django support, and no ambiguity in automated tests.
- Disadvantages: twice as many routes and discovery links.

**Size:** Small (S).

### 1B. `?format=atom`

Examples:

- `/feeds/<feed_key>/all?format=atom`
- `/feeds/shared?format=atom&user=<username>`

**Changes**

- Models and migrations: none.
- Routes: unchanged.
- Feed code: select the generator from a validated `format` value.
- Templates and docs: build query strings for each format.
- Tests: cover valid, missing, repeated, and unsupported values.

**Compatibility**

- An absent `format` keeps RSS.
- Existing URLs remain valid.

**Security**

- The authorization rules remain identical.
- Cache keys must include the query string.

**Trade-offs**

- Advantages: no new route declarations.
- Disadvantages: more query-string construction, weaker content-type clarity,
  and easier accidental loss of existing filters when a UI builds the URL.

**Size:** Small (S).

### 1C. HTTP `Accept` negotiation

One URL returns RSS or Atom from the request `Accept` header.

**Changes**

- Models and migrations: none.
- Routes: unchanged.
- Feed code: parse supported media types and set `Vary: Accept`.
- Templates: show one URL instead of deterministic format URLs.
- Tests: cover exact types, wildcards, quality values, unsupported types, and
  cache headers.

**Compatibility**

- A missing or wildcard header must keep RSS.

**Security**

- Privacy rules do not change.
- Shared caches can serve the wrong representation if `Vary` handling is
  incorrect.

**Trade-offs**

- Advantages: one canonical URL.
- Disadvantages: feed readers do not consistently make format preferences
  visible, debugging is harder, and cache behavior is more complex.

**Size:** Medium (M).

### 1D. JSON Feed

JSON Feed is not part of Django's syndication generator set used by this
project. It requires a custom renderer or another dependency.

**Changes**

- Models and migrations: none.
- Routes: add `.json` feed routes or extend format selection.
- Feed code: implement and maintain a separate serializer.
- Templates and docs: advertise a third format.
- Tests: duplicate metadata, item, escaping, encoding, and privacy parity
  coverage.

**Compatibility**

- Existing RSS URLs do not change.

**Security**

- The renderer must use the same authorized queryset.
- JSON fields must not expose notes, internal IDs, archive assets, or other
  fields that RSS omits.

**Trade-offs**

- Advantages: convenient for JSON clients.
- Disadvantages: no demonstrated requester need, more maintenance, and more
  risk of output drift.

**Size:** Medium (M).

**Recommendation:** Implement 1A. Leave 1B, 1C, and 1D out.

## Option 2: Multiple feed tokens

### 2A. Named full-access tokens — recommended first step

Change `FeedToken.user` from one-to-one to many-to-one. Add a required `name`.
Keep the random `key` as the primary key.

The target model shape is:

```python
class FeedToken(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(
        User,
        related_name="feed_tokens",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=128)
    created = models.DateTimeField(auto_now_add=True)
```

Each token grants the same access that the single current token grants. The
benefit is independent revocation by device or feed reader.

**Changes**

- Models: alter `FeedToken.user`; add `name`; keep `key` and `created`
  (`bookmarks/models.py:490-513`).
- Migration:
  - Add `name` with a temporary migration default of `Default feed token`.
  - Alter `user` to `ForeignKey`.
  - Remove the migration default after existing rows are populated.
  - Preserve every existing `key`, `user`, and `created` value.
- Routes and feed classes: no URL shape change. Key lookup already identifies
  one row (`bookmarks/feeds.py:33-34`).
- Access helpers: add an owner-checked `feed_token_write` helper beside
  `api_token_write` (`bookmarks/views/access.py:69-74`).
- Views: replace lazy one-token creation with token list, create, and delete
  actions. Follow the API token CRUD pattern
  (`bookmarks/views/settings.py:172-238`).
- Templates: replace the fixed list with a table of named tokens and their feed
  URLs. Reuse the API token table interaction pattern
  (`bookmarks/templates/settings/integrations.html:106-160`).
- Admin: show name, owner, and created date. The current admin shows only key
  and user (`bookmarks/admin.py:312-340`).
- Docs: explain that every full-access token can read all of its owner's
  unarchived bookmarks through the `all` route.
- Tests:
  - migration preservation on SQLite and PostgreSQL;
  - two tokens for one user;
  - same feed results for both tokens;
  - deletion invalidates only one key;
  - cross-user deletion returns 404;
  - names are required and escaped;
  - Settings lists only the current user's tokens;
  - e2e create, copy URL, and delete flows.

**Compatibility**

- Existing rows become `Default feed token`.
- Existing RSS URLs remain byte-for-byte valid.
- Opening Integrations does not create another token when one already exists.
- A user with no token receives one default token on first visit, matching the
  current lazy behavior.
- No forced rotation occurs.

**Security and privacy**

- Every token is a bearer credential with full read access through the `all`
  route.
- A name is metadata. It does not restrict access.
- The UI must state that deleting one row is the revocation operation.
- The token key remains visible because users must copy complete feed URLs.
- Token names must not appear in feed output.

**Settings surface**

- Show token name and creation time.
- Show RSS and Atom URLs for each token.
- Add `Create feed token`.
- Add a confirmation before deletion.
- Keep public feeds outside the credential table.

**Trade-offs**

- Advantages: smallest structural change, preserves URLs, and solves
  device-specific revocation.
- Disadvantages: a token intended for one narrow subscription can be edited to
  reach `/all` and can change query parameters.

**Size:** Medium (M).

### 2B. Fixed-scope feed tokens

Store allowed route types and filters on each token. Reject every request that
tries to broaden the stored scope.

Possible fields include `feed_type`, `bundle`, `query`, `unread`, and `shared`.

**Changes**

- Models and migrations: add scope fields and validation to `FeedToken`.
- Routes: existing routes remain, but each route must validate token scope.
- Feed classes: intersect route scope, token scope, and request filters.
- Templates: add a scope builder when the token is created.
- Docs: define which fields can change after creation.
- Tests: cover every widening attempt and every scope combination.

**Compatibility**

- Migrate the existing token as unrestricted.
- Existing URLs remain valid.

**Security and privacy**

- This option gives real least privilege only when request values cannot
  override stored values.
- Mutable scope can silently broaden an existing URL. Scope should therefore be
  immutable, or a scope change must rotate the key.

**Trade-offs**

- Advantages: one credential can safely represent one purpose.
- Disadvantages: a larger schema, a combinatorial test matrix, and a more
  complex creation UI.

**Size:** Large (L).

### 2C. Full-access token plus saved URL presets

Keep option 2A and store named filter presets separately. A preset builds a
convenient URL that still contains a full-access token.

**Changes**

- Models and migrations: add a preset table. Create no rows during migration.
- Routes: either add a preset identifier or expand the preset into the current
  query parameters.
- Feed classes: resolve the preset, then use the existing unrestricted token.
- Templates: add preset create, list, copy, and delete controls.
- Docs: state that a preset is convenience, not authorization.
- Tests: preset ownership, URL generation, deletion, and proof that the
  underlying token can still reach `/all`.

**Compatibility**

- Existing tokens and URLs remain valid.

**Security**

- This is not least privilege. A URL holder can remove the preset identifier
  or change the route if the full token remains visible.

**Trade-offs**

- Advantages: convenient UI and reusable filters.
- Disadvantages: it can look scoped without being scoped.

**Size:** Medium (M).

**Recommendation:** Implement 2A. Use explicit warnings. Do not describe 2C as
a security boundary. Implement 2B only after a concrete least-privilege use
case is approved.

## Option 3: Feeds for another user's bookmarks

### Public and already-shared bookmarks

Public, shared, and private are separate capabilities.

#### 3A. Public per-user shared feeds — already in PR #44

PR #44 adds `?user=<username>` to the tokenless public shared feed. It also
adds user-qualified feed titles and preserves the selected user in feed
discovery.

This specification treats that behavior as the baseline:

- Do not create another public per-user route.
- Atom must preserve the same `user` behavior and titles.
- Multiple tokens do not affect the tokenless route.
- Private grants must not reuse the `user` parameter.

**Migration:** none.

**Security:** the query must continue to require `shared=True`,
`enable_sharing=True`, and `enable_public_sharing=True`.

**Settings:** keep one tokenless public URL and document `?user=`.

**Tests:** reuse and parameterize PR #44's user filtering, 404, title escaping,
and discovery tests.

**Size:** Already in flight.

#### 3B. Per-user authenticated shared feed — recommended

Extend `/feeds/<feed_key>/shared` with `?user=<username>`. This feed returns only
bookmarks that the target owner marked shared and only while that owner has
sharing enabled.

**Changes**

- Models and migrations: none.
- Routes: unchanged.
- Feed classes: resolve `user` for `SharedBookmarksFeed` and pass it to
  `query_shared_bookmarks`. Build on the context and title work from PR #44.
- Templates and docs: document that this parameter differs from public
  sharing. It can include a user's non-public shared bookmarks.
- Tests: target owner, unknown owner, disabled sharing, unshared bookmark,
  multiple tokens, RSS/Atom parity, and title escaping.

**Compatibility**

- No `user` value keeps the current all-users shared feed.
- Existing URLs and tokens remain valid.

**Security and privacy**

- This option does not expose unshared bookmarks.
- The target owner already opted into authenticated sharing with
  `enable_sharing`.
- Return 404 for an unknown user, matching PR #44.

**Settings surface**

- Add a short example. Do not enumerate every instance user.
- A future URL builder can accept a username.

**Trade-offs**

- Advantages: small change, aligns the shared page and feeds, and uses the
  existing sharing contract.
- Disadvantages: usernames are discoverable to authenticated feed-token
  holders, and the global shared feed remains broad.

**Size:** Small (S).

### Private and unshared bookmarks

Private access is not an extension of `?user=`. It is a new authorization
system.

#### 3C. Owner-issued bearer grant for one bundle — recommended if required

An owner creates a grant for one bundle that the owner controls. The grant has
its own 160-bit random key and URL. The bundle is the maximum content scope.

An illustrative model is:

```python
class PrivateFeedGrant(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    bundle = models.ForeignKey(BookmarkBundle, on_delete=models.CASCADE)
    intended_recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_private_feed_grants",
    )
    created = models.DateTimeField(auto_now_add=True)
```

`intended_recipient` records intent. It does not authenticate a feed reader.
The random URL remains the runtime credential.

Recommended routes:

- `/feeds/grants/<grant_key>`
- `/feeds/grants/<grant_key>.atom`

Do not use `/feeds/<owner-token>/all?user=<username>`. That shape makes the
ordinary token and an editable username control a private boundary.

**Changes**

- Models: add `PrivateFeedGrant`. Validate that the bundle owner equals the
  grant owner.
- Migration: create the new table. Create no grant rows. The feature is
  opt-in.
- Routes: add RSS and Atom grant routes.
- Queries: start from `Bookmark.objects.filter(owner=grant.owner)`, apply the
  authorized grant bundle, then apply output ordering and limit. Do not resolve
  a bundle from `request.user`.
- Feed classes: add a grant-aware context. Keep ordinary `FeedToken` and grant
  lookup separate.
- Access helpers: add owner-only create and delete checks.
- Views and templates: add `Private feed grants` to Settings > Integrations.
  Creation selects one owned bundle and optionally records an intended Linkding
  user.
- Docs: add a threat warning and exact revocation procedure.
- Tests:
  - default database has no grants;
  - owner can grant only an owned bundle;
  - bundle contents are the maximum result set;
  - unshared bookmarks in the bundle are visible through the grant;
  - bookmarks outside the bundle are never visible;
  - query parameters cannot broaden scope;
  - another user cannot create, edit, or delete the grant;
  - deletion of the grant, bundle, or owner returns 404;
  - intended-recipient deletion does not broaden access;
  - RSS and Atom output contain the same authorized items;
  - token and username enumeration return uniform 404 responses;
  - e2e creation, warning, URL copy, and revocation.

**Compatibility**

- Existing feed tokens and URLs do not change.
- No existing user receives a grant during migration.
- A grant key never becomes an ordinary feed token.

**Security and privacy**

- Every person or system that has the URL can read the grant.
- A named intended recipient cannot prevent forwarding.
- The feed exposes URL, title, description, added date, and tags.
- It does not render notes. Free `q` must be disabled because `q` currently
  searches notes and can become a keyword oracle
  (`bookmarks/queries.py:67-80`).
- Free `unread` must be disabled. It exposes the owner's reading state.
- Free `shared`, `user`, and `bundle` must be disabled. They are either
  irrelevant or can confuse the grant boundary.
- A validated `limit` can remain. It affects output size, not authorization.
- Filters must always intersect an already-authorized base queryset.
- Application logs and browser history can contain the bearer key. Code must
  not log the full request path for these routes at normal verbosity.
- Revocation is deletion of the grant. Return 404 immediately afterward.

**Settings surface**

- Put grants in a table separate from ordinary feed tokens.
- Show name, source bundle, intended recipient when present, and creation time.
- Show a warning before creation.
- Show the complete URL after creation and on the grant row because feed
  readers need it.
- Require confirmation before deletion.
- State that a recipient name does not stop URL forwarding.

**Trade-offs**

- Advantages: works in external feed readers, gives the owner a fixed maximum
  scope, and supports independent revocation.
- Disadvantages: bearer URLs can be forwarded, bundle edits change visible
  contents, and the feature adds a sensitive authorization path.

**Size:** Large (L).

#### 3D. Owner-issued grant for all private bookmarks

This option replaces the bundle in 3C with the owner's complete active bookmark
set.

**Changes**

- Models and migrations: use the grant model from 3C without a required bundle.
  Create no rows during migration.
- Routes and feed classes: use the same grant routes, but scope directly to all
  active bookmarks owned by the grant owner.
- Templates and docs: replace bundle selection with a high-severity
  complete-library warning.
- Tests: include newly created bookmarks, archived-bookmark exclusion,
  revocation, RSS/Atom parity, and every widening attempt.

**Migration and compatibility**

- The new table starts empty.
- Existing feeds do not change.

**Security and privacy**

- One leaked URL exposes the owner's complete active library.
- New bookmarks become visible automatically.
- A query string can create a note-content oracle if `q` is allowed.

**Trade-offs**

- Advantages: simple mental model and no bundle maintenance.
- Disadvantages: excessive blast radius and unsafe future-content behavior.

**Size:** Medium (M).

**Recommendation:** Do not implement.

#### 3E. Grant bookmarks already marked shared

This option creates a recipient URL but limits it to `shared=True`.

**Changes**

- Models and migrations: add an owner-issued grant row. Create no rows during
  migration.
- Routes and feed classes: add recipient-specific RSS and Atom routes that
  require the existing shared predicates.
- Templates and docs: add grant create and revoke controls and explain the
  difference from the all-users authenticated shared feed.
- Tests: shared and unshared items, `enable_sharing`, recipient-grant
  revocation, and format parity.

**Compatibility**

- Existing feeds do not change.

**Security**

- It preserves the existing bookmark-level sharing decision.
- It duplicates 3B unless recipient-specific revocation is a requirement.

**Trade-offs**

- Advantages: lower privacy risk than unshared bookmark grants.
- Disadvantages: little added value over the authenticated shared feed.

**Size:** Medium (M).

**Recommendation:** Prefer 3B.

#### 3F. Named-user subscription with an in-app timeline

Store an owner-to-subscriber relation. Require a Linkding session to view an
aggregated timeline.

**Changes**

- Models: subscription and access-control tables.
- Routes and views: authenticated timeline, management, and owner approval.
- Queries: aggregate multiple owners with per-owner revocation.
- Templates: new navigation, timeline, request, approval, and management UI.
- Feed support: external readers still require a separate bearer or OAuth-like
  credential.
- Tests: authorization, request lifecycle, revocation, aggregation, pagination,
  notifications, and e2e workflows.

**Compatibility**

- Existing feeds can remain unchanged.

**Security**

- Sessions can enforce the subscriber identity.
- External feed readers cannot use this relation without another credential
  design.

**Trade-offs**

- Advantages: strongest named-user semantics and a visible audit trail.
- Disadvantages: this is a social product feature, not a feed-format change.

**Size:** Extra large (XL).

**Recommendation:** Out of scope for this work.

#### 3G. Share the owner's ordinary feed token

This requires no implementation. It gives the recipient the owner's
`/all` credential.

**Security**

- The recipient can change the route and every free filter.
- The URL exposes all active bookmarks.
- The owner must revoke every subscription that uses the one token.

**Recommendation:** Explicitly reject and document this pattern.

### Recipient identity decision

There are two useful labels for option 3C:

- **Secret URL only:** no recipient row. This is honest about bearer semantics.
- **Named intended recipient:** records the owner's intent and improves the
  management UI. It does not enforce identity in an external feed reader.

**Proposed default:** Allow an optional intended recipient. Describe it as
metadata, not authorization. The bearer key is the authorization mechanism.

**Requester decision required:** Is bearer-URL access acceptable for private
bookmarks? If no, do not implement private external feeds. Scope a separate
authenticated or delegated-authorization project instead.

## Option 4: Feed scoping and filters

### Scope composition rule — recommended

Apply constraints in this order:

1. Resolve the credential.
2. Establish the mandatory route scope.
3. Establish the credential or grant's fixed maximum scope.
4. Authorize every referenced model object against the credential owner.
5. Apply optional request filters as intersections.
6. Apply ordering.
7. Apply a validated output limit.

No later step can widen an earlier step.

### Filter matrix

| Filter | Own `all` / `unread` feed | Authenticated shared feed | Public shared feed | Private bundle grant |
| --- | --- | --- | --- | --- |
| `q` | Keep | Keep, but harden notes behavior | Keep, but harden notes behavior | Reject |
| `user` | Reject | Add after PR #44 | PR #44 baseline | Reject |
| `bundle` | Keep after auth fix | Reject | Reject | Fixed by grant; reject override |
| `unread` | Keep | Leave out of new examples | Leave out of new examples | Reject |
| `shared` | Keep | Redundant; reject on new scoped URLs | Redundant; reject on new scoped URLs | Reject |
| `limit` | Keep and validate | Keep and validate | Keep and validate | Keep and validate |
| explicit tag parameter | Do not add | Do not add | Do not add | Do not add |

The recommendation keeps old own-feed behavior for compatibility. New scoped
routes can reject incompatible parameters with 400. Unknown credentials and
unauthorized objects still return 404.

### 4A. Keep free query parameters

This is the current model for a user's own token. It is appropriate when the
token is already full access.

**Changes**

- Models and migrations: none.
- Routes: unchanged.
- Feed code: centralize parsing and validation.
- Templates and docs: document the real supported set.
- Tests: composition, duplicates, invalid values, and route restrictions.

**Security**

- Free filters do not provide least privilege.
- Search on shared or cross-user data can reveal whether private note keywords
  match even when notes are not rendered. Shared-feed search needs a
  feed-specific search predicate that omits notes.

**Size:** Medium (M), including privacy hardening and validation.

### 4B. Add explicit tag query parameters

Possible parameters are `tag`, `any_tag`, `all_tag`, and `exclude_tag`.
**Changes**

- Models and migrations: none.
- Routes: unchanged.
- Feed classes: parse repeated values and define precedence with `q` and
  bundles.
- Templates and docs: add syntax and URL-encoding examples.
- Tests: any/all/excluded behavior, repeated keys, casing, reserved
  characters, and composition.

**Compatibility**

- Existing `q=#tag` expressions remain.

**Trade-offs**

- Advantages: easier for simple clients to generate.
- Disadvantages: duplicates the search language and bundle model, adds encoding
  rules, and creates precedence questions.

**Size:** Medium (M).

**Recommendation:** Do not implement. Document `q` and bundles instead.

### 4C. Use bundles as saved feed scopes — recommended

After the separate authorization fix, a user's own feed can use an owned
bundle. Bundles already represent named saved searches with tag, unread, and
shared filters (`bookmarks/models.py:167-211`).

**Changes**

- Models and migrations: none.
- Feed code: authorize the bundle against `feed_token.user`.
- Templates: add a URL builder that selects a token, format, route, and owned
  bundle. This UI is optional after the defect fix.
- Docs: define bundle behavior and note that editing a bundle changes feed
  results.
- Tests: token-only request, owner and non-owner bundle, deleted bundle,
  RSS/Atom parity, and composition with route constraints.

**Compatibility**

- Keep `?bundle=<id>`.
- Existing logged-in bundle feed requests continue to work.
- Token-only requests start working as originally implied by the parser.

**Security**

- Public and cross-user shared feeds must not accept arbitrary bundle IDs.
- Private grant scopes must store the authorized bundle and reject an override.

**Size**

- Authorization defect only: Small (S).
- Optional Settings URL builder: Medium (M).

### 4D. Add a new feed-preset model

A preset stores route, format, and filters.
**Changes**

- Models and migrations: add a user-owned preset table. Create no rows during
  migration.
- Routes and feed classes: resolve a preset and intersect its stored filters
  with mandatory route scope.
- Templates: add preset create, list, copy, edit, and delete controls.
- Docs: define edit behavior and state whether an edit rotates any credential.
- Tests: ownership, invalid filter combinations, URL stability, and proof of
  whether the preset is or is not an authorization boundary.

**Trade-offs**

- Advantages: stable names and a guided UI.
- Disadvantages: duplicates bundles. It is not a security boundary when paired
  with a full-access token.

**Size:** Large (L).

**Recommendation:** Do not implement until bundles are proven insufficient.

### Limit validation hardening

Current code converts `limit` with `int()` and allows an empty value to request
the full queryset (`bookmarks/feeds.py:47-50`). Every new route would inherit
this behavior.

Add one shared validator:

- default: 100;
- minimum: 1;
- proposed maximum: 1000;
- invalid value: 400;
- no empty-value bypass.

This is a separate **Small (S)** hardening item. It does not change
authorization. The maximum is a deployment and compatibility judgment that
requires approval.

## Technical design for the recommended sequence

### Phase 0: Land the adjacent public baseline

- Merge PR #44 after its own review.
- Use its `FeedContext.user`, dynamic feed metadata, public `user` lookup, and
  discovery URL behavior as the starting point.
- Do not duplicate its tests or route semantics in another PR.

### Phase 1: Repair bundle authorization

- Resolve `FeedToken` before a bundle.
- Load a private-feed bundle with `owner=feed_token.user`.
- Reject `bundle` on tokenless feeds.
- Add token-only tests that do not call `force_login`.
- Keep the existing `bundle` query parameter.

### Phase 2: Add Atom

- Separate feed authorization and query construction from rendering.
- Add `Atom1Feed` subclasses or mixins.
- Add `.atom` routes after the current routes.
- Add Atom discovery links and Settings links.
- Parameterize behavior tests so RSS and Atom cannot drift.

### Phase 3: Add named feed tokens

- Alter `FeedToken.user` to a foreign key.
- Add `FeedToken.name`.
- Preserve the key as the primary key.
- Migrate the existing row to `Default feed token`.
- Add user-owned CRUD under Settings > Integrations.
- Do not add scope fields in this phase.

### Phase 4: Align authenticated shared feeds

- Add `user` to `SharedBookmarksFeed`.
- Keep the no-user behavior.
- Reuse PR #44's dynamic title rules.
- Add RSS and Atom tests.

### Phase 5: Decide whether to add private bundle grants

Do not start this phase until the requester answers:

1. Is a bearer URL acceptable for private data?
2. Is one owner-controlled bundle the correct maximum scope?
3. Is an optional intended-recipient label useful even though it does not
   enforce identity?
4. Should disabling `enable_sharing` suspend private grants, or are explicit
   grant deletion and bundle deletion the only kill switches?
5. Is the proposed `limit=1000` maximum acceptable?

If approved, implement option 3C in a separate PR. Request a focused security
review.

## Decisions and recommendations

### Format selection

- Options: distinct routes, query selection, content negotiation, JSON Feed.
- Winner: distinct Atom routes.
- Reason: Django supports Atom directly. Explicit routes are predictable for
  feed readers and caches. Existing RSS URLs remain untouched.

### Multiple-token capability

- Options: named full-access tokens, fixed-scope tokens, saved URL presets.
- Winner: named full-access tokens first.
- Reason: this solves independent revocation with the smallest migration.
  Fixed-scope credentials remain a later security feature.

### Existing token upgrade

- Options: preserve, rotate, or delete.
- Winner: preserve and name `Default feed token`.
- Reason: feed readers depend on stable URLs. No schema requirement justifies
  breaking every subscription.

### Public per-user feeds

- Options: repeat the work, replace its URL shape, or build on PR #44.
- Winner: build on PR #44.
- Reason: it already implements and tests the public behavior requested by
  upstream issues. Reimplementation would create drift.

### Authenticated per-user shared feeds

- Options: keep only the all-users feed or add `?user=`.
- Winner: add `?user=` while preserving the all-users default.
- Reason: it aligns feeds with the existing shared page without exposing
  unshared bookmarks.

### Private cross-user access

- Options: complete library, shared-only, bundle grant, in-app subscription,
  or ordinary token sharing.
- Winner: no private access by default. If approved, use a separate
  owner-issued bundle grant.
- Reason: a fixed bundle limits blast radius. A separate key supports
  independent revocation. Ordinary feed tokens and free query parameters are
  too broad.

### Recipient identity

- Options: secret URL, named recipient, or authenticated timeline.
- Winner for external readers: bearer key with optional intended-recipient
  metadata.
- Reason: common feed readers do not provide a Linkding user session. A name
  improves management but cannot enforce identity.

### Tag filtering

- Options: `q`, bundles, or new explicit tag parameters.
- Winner: keep `q` and bundles.
- Reason: both mechanisms already exist. Another tag syntax adds no distinct
  capability.

### Saved scopes

- Options: bundles or a new feed-preset model.
- Winner: bundles.
- Reason: bundles already store the required filters. First fix their token-only
  authorization.

## Out of scope

- An in-Linkding following timeline, activity stream, or notification system.
- OAuth, delegated authorization, or feed-reader identity protocols.
- JSON Feed in the first implementation.
- A grant for an owner's complete private bookmark library.
- Sharing an ordinary owner feed token with another person.
- A second tag query language.
- A new feed-preset model before bundles are evaluated.
- Changes to bookmark write access.
- Changes to archive asset access.
- Work already implemented by PR #44.

## Validation criteria

The criteria apply to the selected phases.

### Baseline and regression checks

- Run `uv run pytest bookmarks/tests/test_feeds.py -q`.
- Run `uv run pytest bookmarks/tests/test_feeds_performance.py -q`.
- Run `uv run pytest bookmarks/tests/test_settings_integrations_view.py -q`.
- Run `uv run pytest bookmarks/tests/test_bookmark_shared_view.py -q`.
- Run `make lint`.
- Run `make test` before the final implementation PR is ready.

### Bundle authorization fix

- Add a test that requests an owned bundle with only the URL token and no
  authenticated session. It must return the bundle's bookmarks.
- Add a test that uses another user's bundle ID. It must return 404.
- Add a test that sends `bundle` to `/feeds/shared`. It must return 404 or 400,
  as selected in implementation, and must not expose bundle existence.
- Keep every existing bundle test passing.

### Atom

- For each RSS route, add an Atom counterpart test.
- Assert `Content-Type: application/atom+xml`.
- Assert the Atom feed has one entry for each RSS item.
- Assert title, description, URL, publication date, and categories are
  equivalent.
- Assert unknown and revoked keys return 404 before rendering.
- Assert `/feeds/shared.atom?user=<username>` matches PR #44's RSS item set and
  user-qualified metadata.
- Assert feed discovery preserves `user` in both format URLs.
- Run `uv run pytest bookmarks/tests/test_feeds.py bookmarks/tests/test_bookmark_shared_view.py -q`.

### Multiple feed tokens

- Add a migration test that starts from one `FeedToken` row and proves its key,
  user, created date, and URLs remain unchanged.
- Add model and view tests for two tokens owned by one user.
- Prove that deleting token A makes token A return 404 while token B still
  returns 200.
- Prove that one user cannot delete another user's token.
- Prove that a user with no token receives one default token on Integrations.
- Add e2e tests for create, URL copy, and delete.
- Run `uv run pytest bookmarks/tests/test_settings_integrations_view.py bookmarks/tests/test_feeds.py -q`.
- Run `make e2e`.
- Record a computer-use video that shows token creation, both format links, and
  single-token revocation. Put the video in the implementation PR description.

### Authenticated per-user shared feed

- Prove that `?user=alice` returns only Alice's shared bookmarks.
- Prove that Alice's unshared bookmarks never appear.
- Prove that disabling Alice's `enable_sharing` removes her items.
- Prove that an unknown username returns 404.
- Prove that an absent `user` keeps the all-users result.
- Run the same assertions for RSS and Atom.

### Private bundle grants, if approved

- Add model validation for grant owner and bundle owner equality.
- Prove that an empty database exposes no private bookmarks.
- Prove that a grant returns only bookmarks in its stored bundle.
- Prove that `q`, `user`, `bundle`, `unread`, and `shared` cannot broaden or
  alter the grant.
- Prove that notes do not appear in output and cannot be probed through `q`.
- Prove that deleting the grant, source bundle, or owner makes the URL return
  404.
- Prove that another user cannot manage the grant.
- Prove RSS and Atom parity.
- Run `make test`, `make lint`, and `make e2e`.
- Record a computer-use video that shows owner opt-in, the privacy warning,
  bundle selection, URL copy, successful subscription, and immediate
  revocation. Put the video in the implementation PR description.

## Approval request

Approve the recommended phases separately:

1. Bundle authorization fix.
2. Atom with distinct `.atom` routes.
3. Named full-access feed tokens with existing-token preservation.
4. `user` filtering for the authenticated shared feed.
5. Private bundle grants.

Private bundle grants require explicit answers to the five Phase 5 questions.
Implementation must not infer approval of private access from approval of the
lower-risk phases.
