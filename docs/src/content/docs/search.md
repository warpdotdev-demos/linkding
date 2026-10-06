---
title: Search
---

linkding provides a comprehensive search function for finding bookmarks. This guide gives on overview of the search capabilities and provides some examples.

## Search Expressions

Every search query is made up of one or more expressions. An expression can be a single word, a phrase, a tag, or a combination of these using boolean operators. The table below summarizes the different expression types:

| Expression   | Example                            | Description                                                |
|--------------|------------------------------------|------------------------------------------------------------|
| Word         | `history`                          | Search for a single word in title, description, notes, URL |
| Phrase       | `"history of rome"`                | Search for an exact phrase by enclosing it in quotes       |
| Tag          | `#book`                            | Search for a tag                                           |
| AND operator | `#history and #book`               | Both expressions must match                                |
| OR operator  | `#book or #article`                | Either expression must match                               |
| NOT operator | `not #article`                     | Expression must not match                                  |
| Grouping     | `#history and (#book or #article)` | Control evaluation order using parenthesis                 |

When combining multiple words, phrases or tags without an explicit operator, the `and` operator is assumed. For example:
```
history rome #book
```
is equivalent to:
```
history and rome and #book
```

Some additional rules to keep in mind:
- Words, phrases, tags, and operators are all case-insensitive.
- Tags must be prefixed with a `#` symbol. If the *lax* tag search mode is enabled in the settings, the `#` prefix is optional. In that case searching for a word will return both bookmarks containing that word or bookmarks tagged with that word.
- An operator (`and`, `or`, `not`) can not be used as a search term as such. To explicitly search for these words, use a phrase: `"beyond good and evil"`, `"good or bad"`, `"not found"`.

## Examples

Here are some example search queries and their meanings:

```
history rome #book
```
Search bookmarks that contain both "history" and "rome", and are tagged with "book".

```
"history of rome" #book
```
Search bookmarks that contain the exact phrase "history of rome" and are tagged with "book".

```
#article or #book
```
Search bookmarks that are tagged with either "article" or "book".

```
rome (#article or #book)
```
Search bookmarks that contain "rome" and are tagged with either "article" or "book".

```
history rome not #article
```
Search bookmarks that contain both "history" and "rome", but are not tagged with "article".

```
history rome not (#article or #book)
```
Search bookmarks that contain both "history" and "rome", but are not tagged with either "article" or "book".

## Search scope in bundles

Opening a bundle searches within its rules by default. The search box shows
**In: \<bundle name\> ×**, even when the sidebar is hidden. Activate × to search
all bookmarks using the text currently in the input, including unsubmitted edits.
You can also select **All bookmarks** in the bundle list to broaden the submitted
query.

Only the bundle's rules are removed. Your search text, sort order, unread, shared,
and date filters remain in effect. Bookmark autocomplete follows the same scope
and filters.

The search control now shows **All bookmarks** and **Back to \<bundle name\>**.
Later searches and clearing then submitting the query stay outside the bundle.
Clearing text without submitting does not change the results. **Back** reapplies
the bundle to the current input and keeps the other filters; it does not restore
the original query. Selecting another bundle discards the Back link.

Archived has the same controls, labeled **All archived bookmarks**. Active and
archived bookmarks remain separate, and neither view searches other users'
bookmarks. Shared search is unchanged. Scope is kept in the URL, not in an
account-wide preference, so tabs and saved bundle links remain independent.

## Legacy Search

A new search engine that supports the above expressions was introduced in linkding v1.44.0.
If you run into any issues with the new search, you can switch back to the old one by enabling legacy search in the settings.
Please report any issues you encounter with the new search on [GitHub](https://github.com/sissbruecker/linkding/issues) so they can be addressed.
This option will be removed in a future version.
