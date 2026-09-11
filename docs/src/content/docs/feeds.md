---
title: Feeds
---

linkding provides RSS and Atom feeds so that you can follow your bookmarks, or bookmarks shared by other users, in a feed reader.

## Feed URLs

Every feed is available as both RSS and Atom, on separate URLs. The RSS URL is the original URL, the Atom URL has the same path with an added `.atom` extension:

- `/feeds/<feed token>/all` / `/feeds/<feed token>/all.atom` - all of your active (non-archived) bookmarks.
- `/feeds/<feed token>/unread` / `/feeds/<feed token>/unread.atom` - your unread bookmarks.
- `/feeds/<feed token>/shared` / `/feeds/<feed token>/shared.atom` - bookmarks shared by any user that has sharing enabled, including bookmarks that are not publicly shared.
- `/feeds/shared` / `/feeds/shared.atom` - bookmarks shared by any user that has enabled *public* sharing. This URL does not require a feed token and can be shared publicly.

You can find your personal feed URLs, and create or delete feed tokens, on the *Settings > Integrations* page.

## Feed tokens

Feed URLs that expose your own or the sharing-related feeds (`all`, `unread`, `shared`) include a feed token in the URL. **Treat a feed URL like any other credential** - anyone with the URL can read the bookmarks it exposes.

You can create multiple, independently named feed tokens, for example one per device or feed reader. Deleting a feed token immediately invalidates every URL built with that token, without affecting your other tokens. If you upgraded from an older version of linkding, your existing feed URL keeps working unchanged, using a token named *Default feed token*.

The public shared feed (`/feeds/shared`) does not use a feed token, since it's meant to be shared publicly.

## Query parameters

The following query parameters are supported, depending on the feed:

| Parameter | Supported on | Description |
| --- | --- | --- |
| `q` | All feeds | A search query, using the same syntax as the search page. |
| `unread` | `all`, `unread` | Filter for unread (`yes`) or read (`no`) bookmarks. |
| `shared` | `all`, `unread` | Filter for shared (`yes`) or unshared (`no`) bookmarks. |
| `bundle` | `all`, `unread` | Scope the feed to one of your own bundles, by ID. Not supported on the shared feeds. |
| `user` | `shared`, public `shared` | Scope the feed to a single user's shared bookmarks, by username. Returns a 404 response for an unknown username. |
| `limit` | All feeds | The maximum number of bookmarks to include. Defaults to 100. |

For example, to only get shared bookmarks from a specific user in the public shared feed:

```
/feeds/shared?user=jane
```

Combining an unauthorized `bundle` or an unknown `user` with a feed returns a 404 response, the same as an unknown or revoked feed token, so that a feed URL never reveals whether a bundle or username exists.
