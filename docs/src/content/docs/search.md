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

## Bundle scope

When you open a bundle, searches and bookmark suggestions stay within that bundle.
Pressing Enter in the search field keeps this scope (unless you have selected an autocomplete suggestion).

To search all your bookmarks, activate the **In: &lt;bundle name&gt; ×** chip in the search field.
This immediately submits the text currently in the field, including completed tags, without the bundle's rules.
It keeps your current active or archived view, independent filters, and saved search preferences.
An empty search lists bookmarks under those remaining filters.

The global results URL no longer contains the bundle, and the sidebar no longer selects it.
Use a bundle link to return to scoped search, or use your browser's Back button to restore the previous scoped URL.
The chip is also available when bundles or the sidebar are hidden.

## Legacy Search

A new search engine that supports the above expressions was introduced in linkding v1.44.0.
If you run into any issues with the new search, you can switch back to the old one by enabling legacy search in the settings.
Please report any issues you encounter with the new search on [GitHub](https://github.com/sissbruecker/linkding/issues) so they can be addressed.
This option will be removed in a future version.
