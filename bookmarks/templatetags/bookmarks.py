import urllib.parse

from django import template

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch

register = template.Library()


def build_global_search_url(search: BookmarkSearch) -> str | None:
    """URL that keeps the current search but drops bundle scope."""
    if not search.bundle:
        return None

    query_params = {
        param: value
        for param, value in search.query_params.items()
        if param != "bundle"
    }
    query_string = urllib.parse.urlencode(query_params)
    return f"?{query_string}" if query_string else "."


@register.inclusion_tag(
    "bookmarks/search.html", name="bookmark_search", takes_context=True
)
def bookmark_search(context, search: BookmarkSearch, mode: str = ""):
    search_form = BookmarkSearchForm(search, editable_fields=["q"])

    if mode == "shared":
        preferences_form = BookmarkSearchForm(search, editable_fields=["sort"])
    else:
        preferences_form = BookmarkSearchForm(
            search, editable_fields=["sort", "shared", "unread"]
        )
    return {
        "request": context["request"],
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "global_search_url": build_global_search_url(search),
    }
