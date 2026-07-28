from urllib.parse import urlencode

from django import template

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch

register = template.Library()


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

    # Build toggle URLs for the global search feature
    # query_params returns only modified (non-default) params; bundle is already an id
    base_params = {k: v for k, v in search.query_params.items() if k != "page"}
    # global_search_url: same params + global_search=1 (remove existing global_search first)
    global_params = {k: v for k, v in base_params.items() if k != "global_search"}
    global_params["global_search"] = "1"
    global_search_url = "?" + urlencode(global_params)
    # bundle_search_url: same params but without global_search
    bundle_params = {k: v for k, v in base_params.items() if k != "global_search"}
    bundle_search_url = ("?" + urlencode(bundle_params)) if bundle_params else "?"

    return {
        "request": context["request"],
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "global_search_url": global_search_url,
        "bundle_search_url": bundle_search_url,
    }
